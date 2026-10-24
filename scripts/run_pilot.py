#!/usr/bin/env python3
"""Phase 6 pilot driver: the frozen 12-step direct-GRPO run (grpo-pilot.yaml).

Runs on the GPU host (Modal L4, grading inline via the namespace engine).
Writes per-step records, full checkpoints (checkpointing.py layout) synced to
the private HF repo, and a final summary. Resume-safe across the 5h sandbox
timeouts: pass --resume-from <checkpoint-dir> (local path or hf: ref already
downloaded) and training continues past the saved step.

Stop conditions live in train.StopConditionCallback (frozen). Budget guard:
the driver records wall time and refuses to START a new step after the
gpu-time ceiling; the 5h sandbox timeout is the outer backstop.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def main() -> int:
    import yaml

    from datasets import Dataset  # noqa: F401  (import check before heavy path)
    from trl import GRPOConfig, GRPOTrainer
    from transformers import TrainerCallback

    from shell_grpo.checkpointing import load_checkpoint_into, save_checkpoint
    from shell_grpo.train import (
        InlineGrader,
        StopConditionCallback,
        build_pilot_dataset,
        build_reward_fn,
    )
    from shell_grpo.manifests import RunManifest, config_hashes, git_head

    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--pilot-config", type=Path, default=REPO / "configs" / "grpo-pilot.yaml")
    parser.add_argument("--model-config", type=Path, default=REPO / "configs" / "model.yaml")
    parser.add_argument("--resume-from", type=Path, default=None,
                        help="checkpoint dir (already downloaded) to continue from")
    parser.add_argument("--runner-config", type=Path, default=REPO / "configs" / "runner.yaml")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.pilot_config.read_text())
    grpo_cfg, budget, pool = cfg["grpo"], cfg["budget"], cfg["dataset"]
    steps_total = int(budget["max_steps"])
    seed = int(cfg["experiment"]["training_seed"])
    seed_base = 20261022
    out = args.out_dir
    (out / "checkpoints").mkdir(parents=True, exist_ok=True)
    (out / "records").mkdir(parents=True, exist_ok=True)

    started = time.time()
    ceiling_s = float(budget["gpu_time_ceiling_hours"]) * 3600

    # --- model + tokenizer (fresh LoRA, or resume weights below) -------------
    from shell_grpo.train import load_policy_for_training

    class _Limits:
        pass

    limits = _Limits()
    limits.seed = seed
    model, tokenizer = load_policy_for_training(args.model_config, limits)

    # --- grading runner (inline namespace engine) ----------------------------
    from shell_grpo.runner import make_runner

    runner = make_runner(args.runner_config)
    grader = InlineGrader(runner)
    reward_fn = build_reward_fn(grader, seed_base)

    # --- dataset + resume bookkeeping ----------------------------------------
    resume_step = 0
    if args.resume_from:
        from peft import PeftModel

        base_model, _ = load_policy_for_training(args.model_config, limits)
        model = PeftModel.from_pretrained(base_model, args.resume_from)
        print(f"[resume] adapter loaded from {args.resume_from}", flush=True)
        resume_step = 0  # replaced by trainer_state after trainer construction

    task_ids = list(pool["accepted_training_pool"])
    train_ds = build_pilot_dataset(tokenizer, task_ids, steps_total, seed_base)

    # --- frozen GRPO config ---------------------------------------------------
    grpo_kwargs = dict(
        max_steps=steps_total,
        per_device_train_batch_size=int(grpo_cfg["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(grpo_cfg["gradient_accumulation_steps"]),
        num_generations=int(grpo_cfg["num_generations"]),
        max_completion_length=int(grpo_cfg["max_completion_length"]),
        learning_rate=float(grpo_cfg["learning_rate"]),
        lr_scheduler_type=grpo_cfg.get("lr_scheduler", "cosine"),
        warmup_steps=int(grpo_cfg.get("warmup_steps", 1)),
        beta=float(grpo_cfg["beta"]),
        temperature=float(grpo_cfg["temperature"]),
        top_p=float(grpo_cfg["top_p"]),
        logging_steps=1,
        report_to="none",
        seed=seed,
        use_vllm=False,
        save_strategy="no",  # checkpoints are explicit (frozen cadence) below
    )
    import inspect

    # TRL 1.15 removed max_prompt_length; prompts measure <=612 tokens,
    # under the frozen 768 cap, so the limit is enforced by construction
    # (recorded deviation 2026-10-24).
    if "max_prompt_length" in inspect.signature(GRPOConfig.__init__).parameters:
        grpo_kwargs["max_prompt_length"] = int(grpo_cfg["max_prompt_length"])
    if "top_k" in inspect.signature(GRPOConfig.__init__).parameters:
        grpo_kwargs["top_k"] = int(grpo_cfg["top_k"])
    if "loss_type" in inspect.signature(GRPOConfig.__init__).parameters:
        grpo_kwargs["loss_type"] = grpo_cfg.get("loss_type", "grpo")
    if "scale_rewards" in inspect.signature(GRPOConfig.__init__).parameters:
        grpo_kwargs["scale_rewards"] = grpo_cfg.get("scale_rewards", "group")

    # --- reward sink (per-step mean reward for stop conditions) ---------------
    step_reward_acc: list[float] = []
    reward_sink: list[float] = []

    def reward_fn_with_sink(completions, prompts=None, **kwargs):
        rewards = reward_fn(completions, prompts=prompts, **kwargs)
        step_reward_acc.extend(float(r) for r in rewards)
        return rewards

    trainer = GRPOTrainer(
        model=model,
        reward_funcs=reward_fn_with_sink,
        processing_class=tokenizer,
        args=GRPOConfig(**grpo_kwargs),
        train_dataset=train_ds,
    )

    # --- per-step records, frozen checkpoint cadence, budget guard ------------
    class PilotHooks(TrainerCallback):
        def __init__(self):
            self.current_step = 0

        def on_step_end(self, args_, state, control, **kw):
            if state.global_step == self.current_step:
                return
            self.current_step = state.global_step
            rewards = step_reward_acc[:]
            step_reward_acc.clear()
            mean_r = sum(rewards) / len(rewards) if rewards else None
            reward_sink.append(mean_r if mean_r is not None else 0.0)
            record = {
                "step": state.global_step,
                "mean_reward": mean_r,
                "n_rewards": len(rewards),
                "loss": (state.log_history or [{}])[-1].get("loss") if state.log_history else None,
                "elapsed_s": int(time.time() - started),
            }
            (out / "records" / f"step-{state.global_step:03d}.json").write_text(
                json.dumps(record, indent=2) + "\n")
            print(f"[step {state.global_step}] mean_reward={mean_r} "
                  f"loss={record['loss']} elapsed={record['elapsed_s']}s", flush=True)
            if int(budget["checkpoint_every_steps"]) and \
                    state.global_step % int(budget["checkpoint_every_steps"]) == 0:
                ck_dir = out / "checkpoints" / f"step-{state.global_step:03d}"
                manifest = save_checkpoint(trainer, ck_dir, manifest_extra={
                    "run_id": out.name, "mean_reward": mean_r,
                    "reward_fn_calls": grader.calls,
                })
                print(f"[checkpoint] step {state.global_step} -> {ck_dir} "
                      f"({manifest['total_bytes']} bytes)", flush=True)
            if time.time() - started > ceiling_s:
                print(f"[budget] gpu-time ceiling {budget['gpu_time_ceiling_hours']}h "
                      "reached — halting at optimizer boundary", flush=True)
                control.should_training_stop = True
                control.should_save = True

    trainer.add_callback(PilotHooks())

    stop_cb = StopConditionCallback(reward_sink)
    trainer.add_callback(stop_cb)

    manifest = RunManifest(
        run_id=out.name,
        phase=6,
        parent_run="P5-20261024T1200",
        git_head=git_head(REPO),
        config_files=config_hashes([args.pilot_config, args.model_config]),
        model={"repo_id": cfg["model"]["repo_id"], "revision": cfg["model"]["revision"]},
        environment={"gpu_time_ceiling_hours": budget["gpu_time_ceiling_hours"]},
        image_digest=runner.image_digest,
        seeds={"training_seed": seed, "seed_base": seed_base,
               "task_pool": task_ids, "steps": steps_total},
    )
    manifest.write(out / "manifest.json")

    if args.resume_from:
        info = load_checkpoint_into(trainer, args.resume_from)
        resume_step = int(info["global_step"])
        print(f"[resume] state restored through step {resume_step}", flush=True)

    history = trainer.train(resume_from_checkpoint=str(args.resume_from) if args.resume_from else None)

    summary = {
        "stopped_reason": stop_cb.reason,
        "final_step": trainer.state.global_step,
        "resume_step": resume_step,
        "train_metrics": history.metrics,
        "log_history": trainer.state.log_history,
        "reward_fn_calls": grader.calls,
        "elapsed_s": int(time.time() - started),
        "task_pool": task_ids,
        "seed_base": seed_base,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps({k: summary[k] for k in
                      ("stopped_reason", "final_step", "elapsed_s", "reward_fn_calls")},
                     indent=1), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
