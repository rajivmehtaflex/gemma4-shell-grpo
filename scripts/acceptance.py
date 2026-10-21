#!/usr/bin/env python3
"""Phase 1 acceptance harness: positive / negative / repeatability checks.

For every registered diagnostic task:
  * reference and alternate solutions must earn task_score 1.0 with
    aggregate status ok, on every one of N repeats, with identical results
    across repeats (ignoring timing and artifact paths);
  * wrong-noop (the no-op) must earn 0.0 on every repeat, identically;
  * every other declared wrong script runs once and must match its declared
    expectation: "zero" -> task_score == 0.0, "partial" -> 0 < score < 1.

Runs only where Docker and the grading image exist (the Codespace). Writes
one GradeResult JSON per execution plus summary.json / summary.md.
Exit status 0 only if every expectation holds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from shell_grpo.contracts import ContractError, validate_grade_result  # noqa: E402
from shell_grpo.runner import RestrictedRunner, RunnerConfig, grade_script  # noqa: E402
from shell_grpo.tasks import all_tasks, get_task  # noqa: E402

SCRIPTS = REPO / "data" / "examples" / "scripts"


def group_seed_for(task_id: str) -> int:
    return int(hashlib.sha256(f"phase1-acceptance:{task_id}".encode()).hexdigest()[:8], 16)


def strip_volatile(result_dict: dict) -> dict:
    data = json.loads(json.dumps(result_dict))
    data.pop("artifacts", None)
    data.pop("candidate_id", None)
    for fr in data.get("fixture_results", []):
        fr.pop("duration_ms", None)
        fr.pop("artifacts", None)
    return data


def git_identity() -> dict:
    def run(args):
        try:
            return subprocess.run(args, capture_output=True, text=True, cwd=REPO).stdout.strip()
        except OSError:
            return ""

    return {
        "head": run(["git", "rev-parse", "HEAD"]),
        "dirty": bool(run(["git", "status", "--porcelain"])),
    }


def image_versions(runner: RestrictedRunner) -> str:
    proc = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", runner.config.image,
         "cat", "/usr/share/shell-grpo/versions.txt"],
        capture_output=True, text=True,
    )
    return proc.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="", help="comma-separated subset (default: all)")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=REPO / "configs" / "runner.yaml")
    args = parser.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    runner = RestrictedRunner(RunnerConfig.load(args.config))
    tasks = all_tasks()
    if args.tasks:
        wanted = set(args.tasks.split(","))
        tasks = [t for t in tasks if t.task_id in wanted]

    summary = {
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git": git_identity(),
        "image": runner.config.image,
        "image_digest": runner.image_digest,
        "image_versions": image_versions(runner),
        "repeats": args.repeats,
        "tasks": {},
        "failures": [],
    }
    rows = []

    for task in tasks:
        seed = group_seed_for(task.task_id)
        task_dir = out / task.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        entry = {"group_seed": seed, "candidates": {}}
        summary["tasks"][task.task_id] = entry

        def run_candidate(name: str, expect: str, repeats: int) -> None:
            script = (SCRIPTS / task.task_id / name).read_bytes()
            results = []
            for rep in range(1, repeats + 1):
                started = time.monotonic()
                result = grade_script(
                    task.task_id, script, seed, runner,
                    candidate_id=f"{name}#{rep}", group_id=f"acc-{task.task_id}",
                    out_dir=task_dir / f"{name}-rep{rep}",
                )
                elapsed = time.monotonic() - started
                try:
                    validate_grade_result(result)
                except ContractError as exc:
                    summary["failures"].append(
                        f"{task.task_id}/{name}#{rep}: contract violation: {exc}"
                    )
                data = result.to_dict()
                (task_dir / f"{name}-rep{rep}.json").write_text(json.dumps(data, indent=2))
                results.append(data)
                rows.append((task.task_id, name, rep, data["aggregate_status"],
                             data["task_score"], f"{elapsed:.1f}s"))
            scores = [r["task_score"] for r in results]
            statuses = [r["aggregate_status"] for r in results]
            stripped = [strip_volatile(r) for r in results]
            identical = all(s == stripped[0] for s in stripped)
            verdict = {
                "expect": expect, "scores": scores, "statuses": statuses,
                "identical_across_repeats": identical,
                "criticals": sorted({c for r in results for c in r["critical_violations"]}),
            }
            entry["candidates"][name] = verdict
            problems = []
            if expect == "full":
                if any(s != 1.0 for s in scores) or any(st != "ok" for st in statuses):
                    problems.append(f"expected full reward, got {scores} {statuses}")
            elif expect == "zero":
                if any(s != 0.0 for s in scores):
                    problems.append(f"expected zero reward, got {scores}")
            elif expect == "partial":
                if any(s is None or not (0.0 < s < 1.0) for s in scores):
                    problems.append(f"expected partial reward in (0,1), got {scores}")
            if repeats > 1 and not identical:
                problems.append("results differ across repeats")
            for problem in problems:
                summary["failures"].append(f"{task.task_id}/{name}: {problem}")
                verdict.setdefault("problems", []).append(problem)

        run_candidate(task.reference, "full", args.repeats)
        run_candidate(task.alternate, "full", args.repeats)
        for wrong in task.wrongs:
            repeats = args.repeats if wrong.filename == "wrong-noop.sh" else 1
            run_candidate(wrong.filename, wrong.expect, repeats)
        print(f"[{task.task_id}] done; failures so far: {len(summary['failures'])}", flush=True)

    summary["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    summary["all_passed"] = not summary["failures"]
    summary["executions"] = len(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    lines = [
        "# Phase 1 acceptance summary", "",
        f"- Executions: {len(rows)} grade runs across {len(tasks)} tasks, "
        f"{args.repeats} repeats for reference/alternate/no-op",
        f"- Git HEAD: `{summary['git']['head']}` dirty={summary['git']['dirty']}",
        f"- Image: `{summary['image']}` digest `{summary['image_digest']}`",
        f"- All passed: **{summary['all_passed']}**", "",
        "| Task | Candidate | Expect | Scores | Statuses | Identical | Problems |",
        "|---|---|---|---|---|---|---|",
    ]
    for task_id, entry in summary["tasks"].items():
        for name, verdict in entry["candidates"].items():
            lines.append(
                f"| {task_id} | {name} | {verdict['expect']} | "
                f"{verdict['scores']} | {','.join(sorted(set(verdict['statuses'])))} | "
                f"{verdict['identical_across_repeats']} | "
                f"{'; '.join(verdict.get('problems', [])) or '—'} |"
            )
    if summary["failures"]:
        lines += ["", "## Failures", ""] + [f"- {f}" for f in summary["failures"]]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"all_passed={summary['all_passed']} failures={len(summary['failures'])}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
