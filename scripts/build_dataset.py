"""Dataset builder: assembles the reviewed task bank with split assignment.

Reads the registered tasks, assigns each to its connected component's split
(splits.py is the source of truth), and writes a versioned release:
  data/dataset/<release>/bank.jsonl    one TaskRecord per line + "split"
  data/dataset/<release>/manifest.json release identity, counts, hashes
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

OUT_DIR = REPO / "data" / "dataset"


def build_release(release: str, seed: int, registry_tasks) -> Path:
    from shell_grpo.splits import (
        all_components,
        check_integrity,
        component_for,
        split_counts,
        split_for,
    )

    known = [t.task_id for t in registry_tasks]
    problems = check_integrity(known)
    if problems:
        raise SystemExit("split integrity violations:\n  " + "\n  ".join(problems))

    out = OUT_DIR / release
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for task in registry_tasks:
        record = task.record().to_dict()
        record["split"] = split_for(task.task_id)
        record["component"] = component_for(task.task_id)
        lines.append(json.dumps(record, ensure_ascii=False))
    bank = out / "bank.jsonl"
    bank.write_text("\n".join(lines) + "\n")

    counts = split_counts(known)
    manifest = {
        "release": release,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "authored-only (reports/source-preflight.md, yield 0/5)",
        "bank_sha256": hashlib.sha256(bank.read_bytes()).hexdigest(),
        "task_count": len(known),
        "split_task_counts": counts,
        "component_count": len(all_components()),
        "seed": seed,
        "reward_version": "r1",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return out


def main() -> None:
    import yaml

    from shell_grpo.tasks import all_tasks

    cfg = yaml.safe_load((REPO / "configs" / "dataset.yaml").read_text())
    release = cfg["release"]["id"]
    seed = int(cfg["release"]["seed"])
    out = build_release(release, seed, all_tasks())
    print(f"release {release} written to {out}")
    print((out / "manifest.json").read_text())


if __name__ == "__main__":
    main()
