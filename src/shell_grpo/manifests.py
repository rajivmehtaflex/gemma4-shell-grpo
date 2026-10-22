"""Run manifests: the identity record every phase run publishes (DESIGN.md).

A manifest binds the exact code, model, config, environment and hardware a run
used. No credentials. Config hashes are content SHA-256s so a manifest can be
verified against the files it names.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(repo: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def config_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(p): sha256_file(p) for p in paths if Path(p).is_file()}


def gpu_identity() -> dict:
    """Best-effort hardware record; every field may be absent on CPU hosts."""
    info: dict = {
        "machine": platform.machine(),
        "cpu_count": platform.system() and __import__("os").cpu_count(),
        "platform": platform.platform(),
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["gpu_total_memory_bytes"] = props.total_memory
            info["gpu_count"] = torch.cuda.device_count()
            info["cuda_version"] = torch.version.cuda
    except Exception as exc:  # torch absent or broken — record why
        info["torch_error"] = str(exc)
    return info


@dataclass
class RunManifest:
    run_id: str
    phase: int
    parent_run: str | None
    git_head: str
    config_files: dict  # path -> sha256
    model: dict  # repo_id, revision, quantization, template...
    environment: dict  # lock hash, key package versions
    image_digest: str  # grading image used for scoring
    seeds: dict
    hardware: dict = field(default_factory=gpu_identity)
    started_utc: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    artifacts: list = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        return path
