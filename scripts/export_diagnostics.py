#!/usr/bin/env python3
"""Export the 20 authored diagnostic TaskRecords to data/examples/diagnostics.jsonl.

Run from the repository root after any task-definition change:
    python3 scripts/export_diagnostics.py
The output is the frozen task-record manifest for Phase 1 (authored
diagnostics; no Pi-derived data). Every line is a TaskRecord JSON object.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from shell_grpo.tasks import all_tasks  # noqa: E402

OUT = REPO / "data" / "examples" / "diagnostics.jsonl"


def main() -> None:
    lines = []
    for task in all_tasks():
        lines.append(json.dumps(task.record().to_dict(), ensure_ascii=False))
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} records to {OUT}")


if __name__ == "__main__":
    main()
