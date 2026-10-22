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
