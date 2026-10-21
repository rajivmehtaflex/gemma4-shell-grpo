"""CLI for grading candidate scripts (used by the acceptance harness and the
pi-sessions verify adapter). Never executes candidates outside the restricted
runner; requires Docker.

Usage:
  python -m shell_grpo.cli grade --task D01 --script ref.sh [--seed 0]
      [--candidate-id id] [--group-id id] [--out-dir dir] [--config path]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import SCHEMA_VERSION, validate_grade_result
from .runner import RestrictedRunner, RunnerConfig, grade_script


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shell-grpo")
    sub = parser.add_subparsers(dest="command", required=True)

    grade = sub.add_parser("grade", help="grade one script against one task")
    grade.add_argument("--task", required=True)
    grade.add_argument("--script", required=True, type=Path)
    grade.add_argument("--seed", type=int, default=0)
    grade.add_argument("--candidate-id", default="candidate")
    grade.add_argument("--group-id", default="group")
    grade.add_argument("--out-dir", type=Path, default=None)
    grade.add_argument("--config", type=Path, default=None)
    grade.add_argument(
        "--support", action="append", default=[],
        help="support file for the candidate dir, as name=path (repeatable)",
    )

    list_tasks = sub.add_parser("list-tasks", help="list registered diagnostic tasks")

    args = parser.parse_args(argv)

    if args.command == "list-tasks":
        from .tasks import all_tasks

        for task in all_tasks():
            print(
                f"{task.task_id}\t{task.family_id}\t"
                f"fixtures={len(task.fixtures)}\tprogress={task.progress_ids()}"
            )
        return 0

    from .tasks import get_task  # noqa: F401  (registers tasks)

    support: dict[str, bytes] = {}
    for item in args.support:
        name, _, path = item.partition("=")
        support[name] = Path(path).read_bytes()

    runner = RestrictedRunner(RunnerConfig.load(args.config))
    result = grade_script(
        args.task,
        args.script.read_bytes(),
        args.seed,
        runner,
        candidate_id=args.candidate_id,
        group_id=args.group_id,
        out_dir=args.out_dir,
        support_files=support,
    )
    validate_grade_result(result)
    json.dump(result.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
