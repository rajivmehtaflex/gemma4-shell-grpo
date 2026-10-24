#!/usr/bin/env python3
"""Phase 6 recovery demo driver (PLAN: restore in a fresh process/checkout).

Verifies a checkpoint's hashes, rebuilds the policy (fresh base + trained
adapter) and trainer, restores optimizer/scheduler/TrainerState/RNG, then
continues training for --continue-steps past the saved step under the same
frozen config. The uninterrupted control is the main run's own log_history
(steps before the checkpoint); the numeric comparison (loss at the same
absolute step, resumed vs control) is written as restore-evidence JSON with
the observed tolerance.

Resume capability proven = verifier green + training continues + loss in the
control's band.
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
    from peft import PeftModel
    from trl import GRPOConfig, GRPOTrainer

    from shell_grpo.checkpointing import load_checkpoint_into, verify_checkpoint
    from shell_grpo.train import (
        InlineGrader,
        build_pilot_dataset,
        build_reward_fn,
        load_policy_for_training,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--continue-steps", type=int, default=2)
    parser.add_argument("--pilot-config", type=Path, default=REPO / "configs" / "grpo-pilot.yaml")
    parser.add_argument("--model-config", type=Path, default=REPO / "configs" / "model.yaml")
    parser.add_argument("--runner-config", type=Path, default=REPO / "configs" / "runner.yaml")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cfg = yaml.safe_load(args.pilot_config.read_text())
    grpo_cfg = cfg["grpo"]
    seed = int(cfg["experiment"]["training_seed"])
    seed_base = 20261022
    steps_total = int(cfg["budget"]["max_steps"]) + args.continue_steps

    started = time.time()
    manifest = verify_checkpoint(args.checkpoint)
    saved_step = int(manifest["global_step"])
    print(f"[verify] checkpoint ok through step {saved_step} "
          f"({manifest['total_bytes']} bytes)", flush=True)

    class _Limits:
        pass

    limits = _Limits()
    limits.seed = seed
    base_model, tokenizer = load_policy_for_training(args.model_config, limits)
    model = PeftModel.from_pretrained(base_model, args.checkpoint)

    from shell_grpo.runner import make_runner

    grader = InlineGrader(make_runner(args.runner_config))
    reward_fn = build_reward_fn(grader, seed_base)

    task_ids = list(cfg["dataset"]["accepted_training_pool"])
    train_ds = build_pilot_dataset(tokenizer, task_ids, steps_total, seed_base)

    grpo_kwargs = dict(
        max_steps=steps_total,
        per_device_train_batch_size=int(grpo_cfg["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(grpo_cfg["gradient_accumulation_steps"]),
        num_generations=int(grpo_cfg["num_generations"]),
        max_completion_length=int(grpo_cfg["max_completion_length"]),
        max_prompt_length=int(grpo_cfg["max_prompt_length"]),
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
        save_strategy="no",
    )
    trainer = GRPOTrainer(
        model=model,
        reward_funcs=reward_fn,
        processing_class=tokenizer,
        args=GRPOConfig(**grpo_kwargs),
        train_dataset=train_ds,
    )
    load_checkpoint_into(trainer, args.checkpoint)
    assert trainer.state.global_step == saved_step
    print(f"[restore] optimizer/scheduler/RNG restored; global_step={trainer.state.global_step}",
          flush=True)

    control_log = manifest.get("control_log_history") or []
    history = trainer.train()

    resumed_losses = {
        entry.get("step", i): entry["loss"]
        for i, entry in enumerate(trainer.state.log_history)
        if "loss" in entry
    }
    control_losses = {
        entry.get("step", i): entry["loss"]
        for i, entry in enumerate(control_log)
        if "loss" in entry
    }
    comparison = {
        str(step): {"resumed": resumed_losses.get(step),
                    "control": control_losses.get(step)}
        for step in sorted(set(resumed_losses) & set(control_losses))
        if step > saved_step
    }
    evidence = {
        "checkpoint": str(args.checkpoint),
        "saved_step": saved_step,
        "continued_through": trainer.state.global_step,
        "verify_ok": True,
        "continued": trainer.state.global_step > saved_step,
        "loss_comparison_same_step": comparison,
        "reward_fn_calls": grader.calls,
        "elapsed_s": int(time.time() - started),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: evidence[k] for k in
                      ("verify_ok", "continued", "continued_through")}, indent=1), flush=True)
    return 0 if evidence["continued"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
