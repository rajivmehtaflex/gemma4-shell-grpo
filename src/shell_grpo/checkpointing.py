"""Full training-checkpoint save/restore (PLAN Phase 6).

A saved adapter alone is NOT a training resume checkpoint (HANDOFF.md). Each
checkpoint here captures: the trained weights (adapter + config via
``trainer.save_model``), optimizer state, LR-scheduler state, the
``TrainerState`` (global step + log history), and the full RNG state
(python/numpy/CPU-torch/CUDA). A SHA-256 manifest pins every file so a
restore can verify integrity before touching trainer state.

The layout matches the HF ``Trainer`` checkpoint convention
(``trainer_state.json`` + ``optimizer.pt`` + ``scheduler.pt`` + model dir), so
``trainer.train(resume_from_checkpoint=...)`` works on the same directory.

torch is imported function-local: the module loads on any host for tests.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _capture_rng() -> dict:
    import numpy as np
    import torch

    state = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["cuda"] = torch.cuda.get_rng_state_all()
    return state


def _restore_rng(state: dict) -> None:
    import numpy as np
    import torch

    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"].cpu())
    if "cuda" in state and torch.cuda.is_available():
        torch.cuda.set_rng_state_all([s.cpu() for s in state["cuda"]])


def save_checkpoint(
    trainer,
    out_dir: Path,
    *,
    manifest_extra: dict | None = None,
) -> dict:
    """Write a full resume checkpoint + SHA-256 manifest. Returns the manifest."""
    import torch

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    trainer.save_model(str(out_dir))  # adapter weights + config (Unsloth/peft path)
    torch.save(trainer.optimizer.state_dict(), out_dir / "optimizer.pt")
    torch.save(trainer.lr_scheduler.state_dict(), out_dir / "scheduler.pt")
    trainer.state.save_to_json(str(out_dir / "trainer_state.json"))
    torch.save(_capture_rng(), out_dir / "rng_state.pth")

    files = sorted(
        p for p in out_dir.iterdir() if p.is_file() and p.name != "manifest.json"
    )
    manifest = {
        "global_step": int(trainer.state.global_step),
        "files": {p.name: _sha256(p) for p in files},
        "total_bytes": sum(p.stat().st_size for p in files),
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def verify_checkpoint(ckpt_dir: Path) -> dict:
    """Check every manifest file's SHA-256. Raises on any mismatch."""
    ckpt_dir = Path(ckpt_dir)
    manifest = json.loads((ckpt_dir / "manifest.json").read_text())
    problems = []
    for name, expected in manifest["files"].items():
        path = ckpt_dir / name
        if not path.exists():
            problems.append(f"missing: {name}")
            continue
        if _sha256(path) != expected:
            problems.append(f"hash mismatch: {name}")
    if problems:
        raise RuntimeError(f"checkpoint verification failed: {problems}")
    return manifest


def load_checkpoint_into(trainer, ckpt_dir: Path) -> dict:
    """Verify + restore optimizer/scheduler/trainer-state/RNG into a trainer
    whose MODEL was already loaded from ``ckpt_dir`` (fresh base + adapter).

    Returns the verified manifest (global_step included).
    """
    import torch

    ckpt_dir = Path(ckpt_dir)
    manifest = verify_checkpoint(ckpt_dir)

    trainer.optimizer.load_state_dict(torch.load(ckpt_dir / "optimizer.pt", weights_only=False))
    trainer.lr_scheduler.load_state_dict(torch.load(ckpt_dir / "scheduler.pt", weights_only=False))
    trainer.state.load_from_json(str(ckpt_dir / "trainer_state.json"))
    _restore_rng(torch.load(ckpt_dir / "rng_state.pth", weights_only=False))
    return manifest
