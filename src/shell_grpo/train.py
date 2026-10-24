"""Minimal shared GRPO training entry (PLAN Phase 2).

One training path reused by the compatibility probe, screening, pilot and
main runs; runs differ only in limits. Direct GRPO from the original
instruction checkpoint with a FRESH LoRA adapter — no SFT stage, no
previously trained adapter. Conservative path only: fast_inference=False.

Runs exclusively on the GPU host; torch/unsloth/trl imports are local.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class TrainLimits:
    max_steps: int
    per_device_train_batch_size: int
    gradient_accumulation_steps: int
    num_generations: int  # GRPO group size G
    max_completion_length: int
    max_prompt_length: int
    learning_rate: float
    beta: float = 0.0  # TRL default: no KL; group-relative advantage suffices
    seed: int = 3407

    @classmethod
    def load(cls, path: Path) -> "TrainLimits":
        raw = yaml.safe_load(Path(path).read_text())["grpo_train"]
        return cls(**raw)


def build_reward_fn(runner, group_seed_base: int):
    """Reward = extracted script's task score under the Phase 1 grader.

    Uses the frozen scoring rules including the scoring-failure protocol:
    infrastructure errors surface as their own status so the run can halt
    for repair instead of labeling them as model failure (the halt/invalidate
    wiring lands with Phase 6; here every record is preserved either way).
    """
    from .evaluate import extract_script

    def shell_task_reward(completions, prompts=None, **kwargs):
        rewards = []
        for index, completion in enumerate(completions):
            task_id = kwargs["task_ids"][index]
            group_seed = kwargs["group_seeds"][index]
            extraction = extract_script(completion)
            if not extraction.ok:
                rewards.append(0.0)
                continue
            result = runner.grade(
                task_id, extraction.script, group_seed, candidate_id=f"train-{index}"
            )
            rewards.append(float(result.task_score or 0.0))
        return rewards

    return shell_task_reward


def load_policy_for_training(model_cfg_path: Path, train_limits: TrainLimits):
    """Fresh LoRA on the untouched instruction checkpoint (no SFT adapter)."""
    from unsloth import FastModel
    from unsloth.chat_templates import get_chat_template

    cfg_raw = yaml.safe_load(Path(model_cfg_path).read_text())
    model, tokenizer = FastModel.from_pretrained(
        model_name=cfg_raw["model"]["training_checkpoint"]["repo_id"],
        max_seq_length=cfg_raw["limits"]["max_seq_length"],
        load_in_4bit=True,
        full_finetuning=False,
        fast_inference=False,  # Gemma 4 RL is not vLLM-supported; conservative path
    )
    tokenizer = get_chat_template(tokenizer, chat_template=cfg_raw["template"]["chat_template"])
    from .generate import _mirror_token_attrs

    tokenizer = _mirror_token_attrs(tokenizer)
    lora = cfg_raw["grpo"]["lora"]
    model = FastModel.get_peft_model(
        model,
        finetune_vision_layers=False,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=lora["r"],
        lora_alpha=lora["alpha"],
        lora_dropout=lora["dropout"],
        bias="none",
        random_state=train_limits.seed,
    )
    return model, tokenizer


class InlineGrader:
    """Adapts the Phase 1 grader to the reward-fn interface (`runner.grade`).

    Runs the namespace engine INLINE on the training host — the frozen
    Phase 6 routing (Modal gVisor passed the isolation proof). One grade per
    candidate, synchronous, inside the reward function.
    """

    def __init__(self, runner):
        self.runner = runner
        self.calls = 0

    def grade(self, task_id: str, script: str, seed: int, candidate_id: str):
        from .runner import grade_script

        self.calls += 1
        return grade_script(
            task_id, script, seed, self.runner,
            candidate_id=candidate_id, group_id=f"train-{task_id}",
        )


def build_pilot_dataset(tokenizer, task_ids: list[str], steps: int, seed_base: int,
                        dataset_factory=None):
    """Frozen sampling (grpo-pilot.yaml): uniform over the accepted pool, one
    task per step, group fixture seed rotating per row: 20261022 + row index.

    Rows cycle the pool to reach `steps`; `task_ids` order is the frozen pool
    order, so the sequence is deterministic given the trainer seed.
    ``dataset_factory`` injects a stand-in for ``datasets.Dataset`` on hosts
    without the HF stack (tests); the GPU path uses the real thing.
    """
    if dataset_factory is None:
        from datasets import Dataset
    else:
        Dataset = dataset_factory

    from .generate import render_prompt
    from .tasks import get_task

    rows = []
    for step in range(steps):
        task = get_task(task_ids[step % len(task_ids)])
        # cfg=None renders the frozen thinking template default (generate.py)
        rows.append({
            "prompt": render_prompt(tokenizer, task.prompt, None),
            "task_ids": task.task_id,
            "group_seeds": seed_base + step,
        })
    return Dataset.from_list(rows)


class StopConditionCallback:
    """Frozen grpo-pilot.yaml stop conditions, checked after every step.

    Halts by raising SettingWithCopyWarning-free StopTraining flag through
    ``trainer.control.should_training_stop``. Reasons are recorded for the
    run record; the last good checkpoint is always kept.
    """

    def __init__(self, reward_sink: list, *, max_loss: float = 20.0,
                 zero_reward_steps: int = 3, high_loss_steps: int = 2):
        import logging

        self.log = logging.getLogger("stop-conditions")
        self.reward_sink = reward_sink      # mean reward per step (appended by reward fn)
        self.losses: list[float] = []
        self.reason: str | None = None
        self.max_loss = max_loss
        self.zero_reward_steps = zero_reward_steps
        self.high_loss_steps = high_loss_steps

    def _halt(self, control, reason: str) -> None:
        self.reason = reason
        self.log.warning("STOP CONDITION: %s", reason)
        control.should_training_stop = True
        control.should_save = True

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs and "loss" in logs:
            self.losses.append(float(logs["loss"]))
        if self.losses:
            last = self.losses[-1]
            if last != last or last in (float("inf"), float("-inf")):
                self._halt(control, f"loss NaN/Inf at step {state.global_step}")
                return
        if len(self.losses) >= self.high_loss_steps and all(
            l > self.max_loss for l in self.losses[-self.high_loss_steps:]
        ):
            self._halt(control, f"loss > {self.max_loss} for {self.high_loss_steps} consecutive "
                                f"steps at step {state.global_step}")
            return
        if len(self.reward_sink) >= self.zero_reward_steps and all(
            r == 0.0 for r in self.reward_sink[-self.zero_reward_steps:]
        ):
            self._halt(control, f"mean reward exactly 0.0 for {self.zero_reward_steps} consecutive "
                                f"steps at step {state.global_step}")
