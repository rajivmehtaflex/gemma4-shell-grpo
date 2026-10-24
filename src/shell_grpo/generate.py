"""Generation entry point: the single path used by baseline, screening, pilot
and main runs (PLAN Phase 2). Conservative Unsloth/transformers path only —
no accelerated rollout backend is trusted until separate parity evidence
exists (PLAN Phase 2, last checklist item).

Heavy imports (torch/unsloth/transformers) are function-local so the module
loads on any machine for config handling and tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModelConfig:
    deployment_alias: str
    repo_id: str
    revision: str
    quantization: str
    chat_template: str
    enable_thinking: bool
    max_seq_length: int
    max_new_tokens: int
    temperature: float
    top_p: float
    top_k: int
    do_sample: bool = True
    strip_bos: bool = True
    fast_inference: bool = False
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "ModelConfig":
        raw = yaml.safe_load(Path(path).read_text())
        mc = raw["model"]
        tc, lc, dc = raw["template"], raw["limits"], raw["decoding"]
        return cls(
            deployment_alias=mc["deployment_alias"],
            repo_id=mc["training_checkpoint"]["repo_id"],
            revision=mc["training_checkpoint"]["revision"],
            quantization=mc.get("quantization", ""),
            chat_template=tc["chat_template"],
            enable_thinking=tc["enable_thinking"],
            max_seq_length=lc["max_seq_length"],
            max_new_tokens=lc["max_new_tokens"],
            temperature=dc["temperature"],
            top_p=dc["top_p"],
            top_k=dc["top_k"],
            do_sample=dc.get("do_sample", True),
            strip_bos=tc.get("strip_bos", True),
            fast_inference=mc.get("fast_inference", False),
            raw=raw,
        )


def resolve_revision(repo_id: str, token: str | None = None) -> dict:
    """Pin the mutable ref to an exact commit via the Hub API (GPU host)."""
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(repo_id=repo_id, filename="config.json", token=token)
    import json

    cfg = json.loads(Path(path).read_text())
    commit = Path(path).parent.name  # snapshots/<commit>/config.json
    return {"repo_id": repo_id, "resolved_commit": commit, "architectures": cfg.get("architectures")}


def _mirror_token_attrs(processor):
    """TRL and generate() expect pad/eos attributes the multimodal processor
    does not expose; mirror them from the inner text tokenizer (probe finding
    2026-10-22)."""
    inner = getattr(processor, "tokenizer", processor)
    for attr in ("pad_token_id", "eos_token_id", "bos_token_id",
                 "pad_token", "eos_token", "bos_token", "padding_side"):
        if not hasattr(processor, attr) and hasattr(inner, attr):
            setattr(processor, attr, getattr(inner, attr))
    if getattr(processor, "pad_token_id", None) is None:
        processor.pad_token_id = getattr(processor, "eos_token_id", None)
    return processor

def load_model(cfg: ModelConfig):
    """Conservative loader: Unsloth FastModel, 4-bit QLoRA base, no vLLM."""
    from unsloth import FastModel

    model, tokenizer = FastModel.from_pretrained(
        model_name=cfg.repo_id,
        max_seq_length=cfg.max_seq_length,
        load_in_4bit=True,
        full_finetuning=False,
        fast_inference=cfg.fast_inference,  # must stay False for Gemma 4 RL
    )
    return model, _mirror_token_attrs(tokenizer)


def render_prompt(tokenizer, user_content: str, cfg: ModelConfig) -> str:
    """Render the Gemma 4 thinking chat template, frozen byte-for-byte.

    The exact string below is what google's processor produced for a
    text-only conversation on the Colab probe (2026-10-22) before its
    multimodal routing rejected the call; Unsloth's get_chat_template
    patching re-routes even the inner tokenizer, so the format is built
    directly and asserted by tests/test_extraction.py.
    """
    if getattr(cfg, "enable_thinking", True):
        system = "<|turn>system\n<|think|>\n<turn|>\n"
    else:
        system = ""
    # The processor renders exactly this (observed via the inner tokenizer,
    # Colab probe 2026-10-22): a <bos> prefix (stripped per config; training
    # re-adds it) and NO thought-channel prefix — the model emits the
    # <|channel>thought block itself.
    return f"{system}<|turn>user\n{user_content}<turn|>\n<|turn>model\n"


@dataclass
class GenerationRecord:
    task_id: str
    prompt_sha256: str
    completion: str
    prompt_text: str
    new_tokens: int
    finish_reason: str | None
    duration_ms: int
    truncated: bool
    settings: dict


def generate_one(model, tokenizer, task_id: str, user_content: str, cfg: ModelConfig) -> GenerationRecord:
    import torch

    prompt_text = render_prompt(tokenizer, user_content, cfg)
    import hashlib

    # Gemma4Processor's first positional parameter is images; text must be
    # passed by keyword (probe finding, 2026-10-22).
    inputs = tokenizer(text=prompt_text, return_tensors="pt", add_special_tokens=False).to("cuda")
    started = time.monotonic()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=cfg.max_new_tokens,
            use_cache=True,  # Gemma 4: use_cache=False corrupts E2B/E4B attention
            do_sample=cfg.do_sample,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            top_k=cfg.top_k,
        )
    duration_ms = int((time.monotonic() - started) * 1000)
    completion_ids = out[0][inputs["input_ids"].shape[1]:]
    completion = tokenizer.decode(completion_ids, skip_special_tokens=False)
    return GenerationRecord(
        task_id=task_id,
        prompt_sha256=hashlib.sha256(prompt_text.encode()).hexdigest(),
        completion=completion,
        prompt_text=prompt_text,
        new_tokens=int(completion_ids.shape[0]),
        finish_reason="length" if completion_ids.shape[0] >= cfg.max_new_tokens else "stop",
        duration_ms=duration_ms,
        truncated=completion_ids.shape[0] >= cfg.max_new_tokens,
        settings={
            "temperature": cfg.temperature, "top_p": cfg.top_p, "top_k": cfg.top_k,
            "do_sample": cfg.do_sample, "max_new_tokens": cfg.max_new_tokens,
            "max_seq_length": cfg.max_seq_length, "enable_thinking": cfg.enable_thinking,
            "repo_id": cfg.repo_id, "revision": cfg.revision,
        },
    )


def generation_config_from_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text())
