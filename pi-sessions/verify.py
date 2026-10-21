#!/usr/bin/env python3
"""Campaign verifier adapter — bridges Pi practice sessions to the Phase 1 grader.

Status: GATED SKELETON. The Codespace transfer and grader-invocation steps become
executable only after the Phase 0 orchestration gates and the Phase 1 grader
acceptance checks pass (see PLAN.md). Until then this tool performs only the
controller-side preflight below and refuses to run the graded path.

Contract implemented on activation (never before the gates):
  1. Snapshot and hash the submitted script.
  2. Transfer it to the recorded Codespace and confirm matching bytes on the worker.
  3. Invoke the locked Phase 1 grader inside its restricted environment.
  4. Retrieve the GradeResult and execution evidence.
  5. Save a unique result ID linking task version, script hash, fixture hashes,
     and runner version under pi-sessions/results/.

It must never execute the candidate on macOS and never interpolate candidate
contents into controller commands. Infrastructure failures remain unscorable
under the existing retry protocol.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

CAMPAIGN_ROOT = Path(__file__).resolve().parent
TASK_IDS = [f"S{i:02d}" for i in range(1, 11)]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def preflight(task_id: str, script: Path) -> dict:
    brief = CAMPAIGN_ROOT / "tasks" / f"{task_id}.md"
    fixture = CAMPAIGN_ROOT / "fixtures" / f"{task_id}.md"
    problems = []
    if not brief.is_file():
        problems.append(f"missing task brief: {brief}")
    if not fixture.is_file():
        problems.append(f"missing fixture spec: {fixture}")
    if not script.is_file():
        problems.append(f"missing candidate script: {script}")
    if problems:
        for p in problems:
            print(f"preflight: {p}", file=sys.stderr)
        sys.exit(2)
    return {
        "task_id": task_id,
        "task_brief": str(brief.relative_to(CAMPAIGN_ROOT)),
        "fixture_spec": str(fixture.relative_to(CAMPAIGN_ROOT)),
        "script_path": str(script.resolve()),
        "script_sha256": sha256_file(script),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pi practice-session verifier adapter")
    parser.add_argument("task_id", choices=TASK_IDS)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--codespace", required=True, help="recorded Codespace ID")
    args = parser.parse_args()

    record = preflight(args.task_id, args.script)
    record["codespace"] = args.codespace

    print(json.dumps(record, indent=2))
    print(
        "GATED: Codespace transfer and grader invocation activate only after the "
        "Phase 0 orchestration gates and Phase 1 grader acceptance checks pass "
        "(PLAN.md). No candidate was executed.",
        file=sys.stderr,
    )
    sys.exit(3)


if __name__ == "__main__":
    main()
