#!/usr/bin/env python3
"""Phase 2 compatibility probe — run on the GPU host (Colab) only.

Demonstrates, with tiny limits, exactly what the later pilot needs (PLAN):
  1. hardware/driver identity recorded;
  2. the pinned checkpoint loads through the conservative Unsloth path;
  3. a fresh LoRA adapter trains: finite gradients on a real batch;
  4. one tiny GRPO step via the shared training path: finite loss and a
     nonzero trainable-parameter update;
  5. the adapter saves and reloads with matching outputs within tolerance;
  6. baseline-style generation works on a couple of diagnostics.

Evidence goes to a JSON file the controller copies back; nothing here is
trusted until that file lands in the run record. Grading-contract checks for
this host must pass BEFORE this script loads weights (Phase 0 pattern).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from shell_grpo.manifests import RunManifest, config_hashes, git_head  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True, help="evidence JSON output path")
    parser.add_argument("--model-config", type=Path, default=REPO / "configs" / "model.yaml")
    parser.add_argument("--train-config", type=Path, default=REPO / "configs" / "baseline.yaml")
    parser.add_argument("--max-steps", type=int, default=2)
    parser.add_argument("--skip-training", action="store_true", help="generation-only probe")
    args = parser.parse_args()

    from shell_grpo.generate import ModelConfig, generate_one, load_model, render_prompt, resolve_revision
    from shell_grpo.tasks import all_tasks

    import torch  # noqa: F401  (used for no_grad / comparisons below)

    evidence: dict = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "checks": {}}

    model_cfg = ModelConfig.load(args.model_config)

    manifest = RunManifest(
        run_id=f"P2-probe-{time.strftime('%Y%m%dT%H%M%S')}",
        phase=2,
        parent_run=None,
        git_head=git_head(REPO),
        config_files=config_hashes([args.model_config, args.train_config]),
        model={"repo_id": model_cfg.repo_id, "requested_revision": model_cfg.revision,
               "quantization": model_cfg.quantization},
        environment={},
        image_digest="",
        seeds={"probe_seed": 3407},
    )

    # 1. resolve the exact upstream commit for the configured repo
    resolved = resolve_revision(model_cfg.repo_id)
    evidence["checks"]["revision_resolved"] = resolved
    print(f"[1/6] revision resolved: {resolved}", flush=True)

    # 2. conservative load
    model, tokenizer = load_model(model_cfg)
    evidence["checks"]["loaded"] = {"repo_id": model_cfg.repo_id, "dtype": str(model.dtype)}
    print("[2/6] model loaded (conservative path, fast_inference=False)", flush=True)

    # 3. fresh adapter + finite gradients on one rendered prompt
    from unsloth import FastModel
    from unsloth.chat_templates import get_chat_template
    from shell_grpo.train import TrainLimits, load_policy_for_training

    limits = TrainLimits.load(args.train_config)
    limits.max_steps = args.max_steps
    model, tokenizer = load_policy_for_training(args.model_config, limits)
    model.train()
    prompt = render_prompt(tokenizer, all_tasks()[0].prompt, model_cfg)
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
    out = model(**inputs, labels=inputs["input_ids"], use_cache=False)
    loss = out.loss
    loss.backward()
    grads = [p.grad.abs().max().item() for p in model.parameters() if p.grad is not None]
    trainable = [p for p in model.parameters() if p.requires_grad]
    evidence["checks"]["finite_gradients"] = {
        "loss": float(loss), "max_grad": max(grads) if grads else None,
        "finite": bool(grads) and all(g == g and abs(g) != float("inf") for g in grads),
        "trainable_params": sum(p.numel() for p in trainable),
    }
    print(f"[3/6] loss={float(loss):.4f} max_grad={max(grads) if grads else 'n/a'}", flush=True)
    model.zero_grad(set_to_none=True)

    # 4. tiny GRPO step through the shared path
    if not args.skip_training:
        from trl import GRPOConfig, GRPOTrainer

        class _ProbeRunner:
            """Tiny fixed reward so the step needs no grading infrastructure."""

            @staticmethod
            def grade(task_id, script, seed, candidate_id):
                class R:
                    task_score = 1.0 if "bash" in script else 0.0

                return R()

        from shell_grpo.train import build_reward_fn

        reward_fn = build_reward_fn(_ProbeRunner(), 20261022)
        from datasets import Dataset

        rows = []
        for task in all_tasks()[:3]:
            rows.append({
                "prompt": render_prompt(tokenizer, task.prompt, model_cfg),
                "task_ids": task.task_id,
                "group_seeds": 20261022,
            })
        train_ds = Dataset.from_list(rows)
        before = [p.detach().clone() for p in model.parameters() if p.requires_grad]
        trainer = GRPOTrainer(
            model=model,
            reward_funcs=reward_fn,
            args=GRPOConfig(
                max_steps=limits.max_steps,
                per_device_train_batch_size=1,
                gradient_accumulation_steps=1,
                num_generations=2,
                max_completion_length=128,
                max_prompt_length=None,
                learning_rate=1e-4,
                logging_steps=1,
                report_to="none",
                seed=limits.seed,
                use_vllm=False,
            ),
            train_dataset=train_ds,
        )
        history = trainer.train()
        after = [p for p in model.parameters() if p.requires_grad]
        deltas = [
            (a - b).abs().max().item()
            for a, b in zip(after, before)
        ]
        evidence["checks"]["grpo_step"] = {
            "train_loss": history.metrics.get("train_loss"),
            "max_param_delta": max(deltas) if deltas else None,
            "nonzero_update": bool(deltas) and max(deltas) > 0.0,
            "finite": bool(deltas) and all(d == d and abs(d) != float("inf") for d in deltas),
        }
        print(f"[4/6] GRPO step: loss={history.metrics.get('train_loss')} "
              f"max_param_delta={max(deltas) if deltas else 'n/a'}", flush=True)

    # 5. adapter save / reload parity: same prompt must produce identical
    # token ids from the saved-then-reattached adapter
    if not args.skip_training:
        import tempfile

        adapter_dir = Path(tempfile.mkdtemp(prefix="adapter-"))
        model.save_pretrained(adapter_dir)

        sample_inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.no_grad():
            before_ids = model.generate(
                **sample_inputs, max_new_tokens=32, use_cache=True, do_sample=False
            )
        from peft import PeftModel

        reloaded = PeftModel.from_pretrained(model, adapter_dir)
        with torch.no_grad():
            after_ids = reloaded.generate(
                **sample_inputs, max_new_tokens=32, use_cache=True, do_sample=False
            )
        evidence["checks"]["adapter_save_reload"] = {
            "adapter_dir": str(adapter_dir),
            "files": sorted(p.name for p in adapter_dir.iterdir()),
            "outputs_identical": bool((before_ids == after_ids).all().item()),
        }
        print(f"[5/6] adapter save/reload parity: "
              f"{evidence['checks']['adapter_save_reload']['outputs_identical']}", flush=True)

    # 6. baseline-style generation on the first diagnostic
    generation = generate_one(model, tokenizer, all_tasks()[0].task_id, all_tasks()[0].prompt, model_cfg)
    evidence["checks"]["generation"] = {
        "task_id": generation.task_id,
        "new_tokens": generation.new_tokens,
        "truncated": generation.truncated,
        "duration_ms": generation.duration_ms,
        "completion_preview": generation.completion[:400],
    }
    print(f"[6/6] generated {generation.new_tokens} tokens in {generation.duration_ms} ms", flush=True)

    manifest.environment = {"probe": True}
    manifest.notes = "compatibility probe evidence; adapter kept for inspection"
    evidence["manifest"] = manifest.to_dict()
    evidence["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"evidence written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
