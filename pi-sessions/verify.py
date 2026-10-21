#!/usr/bin/env python3
"""Campaign verifier adapter — grades Pi practice candidates via the Phase 1 grader.

Flow (per submitted candidate):
  1. Preflight the task brief, fixture spec and script; hash the script.
  2. Gate on the Phase 1 acceptance evidence: --acceptance-summary must point
     at an acceptance summary.json whose all_passed is true. Until then the
     graded path refuses to run (exit 3).
  3. Stream the script (and any --support files) to the recorded Codespace by
     base64 over `gh codespace ssh`; verify matching SHA-256 on the worker.
  4. Invoke `python -m shell_grpo.cli grade` inside the worker, which executes
     the candidate only inside the restricted grading image.
  5. Retrieve the GradeResult JSON and a tar of the execution evidence; save a
     verification record under pi-sessions/results/<ID>/ with a result ID
     binding task version, script hash, fixture hashes and runner identity.

The candidate is never executed on macOS and its contents are never
interpolated into a shell command — only its base64 encoding is.

Exit codes: 0 verified/failed verdict recorded · 2 preflight · 3 gate ·
4 transfer hash mismatch · 5 infrastructure error.
"""

import argparse
import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import time
from pathlib import Path

CAMPAIGN_ROOT = Path(__file__).resolve().parent
TASK_IDS = [f"S{i:02d}" for i in range(1, 11)]
WORKER_TMP = "/tmp/pi-verify"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def worker_sha(codespace: str, path: str) -> str:
    proc = subprocess.run(
        ["gh", "codespace", "ssh", "-c", codespace, "--", "sha256sum", path],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"hash retrieval failed: {proc.stderr}", file=sys.stderr)
        sys.exit(5)
    return proc.stdout.split()[0]


def worker_run(codespace: str, command: str) -> subprocess.CompletedProcess:
    """Run a script on the worker via stdin (bash -s).

    gh codespace ssh does not preserve argument quoting on multi-word remote
    commands, so the script travels on stdin and only the fixed two words
    `bash -s` cross the command line.
    """
    return subprocess.run(
        ["gh", "codespace", "ssh", "-c", codespace, "--", "bash", "-s"],
        input=command, capture_output=True, text=True,
    )


def stream_to_worker(codespace: str, remote_dir: str, name: str, data: bytes) -> None:
    b64 = base64.b64encode(data).decode()
    script = (
        f"mkdir -p {remote_dir} && "
        f"printf '%s' '{b64}' | base64 -d > {remote_dir}/{name}"
    )
    proc = worker_run(codespace, script)
    if proc.returncode != 0:
        print(f"transfer failed for {name}: {proc.stderr}", file=sys.stderr)
        sys.exit(5)


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
        "script_sha256": sha256_bytes(script.read_bytes()),
    }


def next_result_index(task_id: str) -> int:
    results = CAMPAIGN_ROOT / "results" / task_id
    if not results.is_dir():
        return 1
    existing = list(results.glob("verification-*.json"))
    return max((int(p.stem.split("-")[1]) for p in existing), default=0) + 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Pi practice-session verifier adapter")
    parser.add_argument("task_id", choices=TASK_IDS)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--codespace", required=True, help="recorded Codespace ID")
    parser.add_argument(
        "--acceptance-summary", required=True, type=Path,
        help="path to the Phase 1 acceptance summary.json (gate)",
    )
    parser.add_argument("--seed", type=int, default=20261021,
                        help="campaign group seed (fixed for comparability)")
    parser.add_argument("--candidate-id", default=None)
    parser.add_argument(
        "--support", action="append", default=[],
        help="support file streamed beside the script, as name=path (repeatable)",
    )
    args = parser.parse_args()

    record = preflight(args.task_id, args.script)
    record["codespace"] = args.codespace

    # Gate: Phase 1 acceptance evidence must exist and pass.
    if not args.acceptance_summary.is_file():
        print(
            f"GATED: acceptance summary not found: {args.acceptance_summary}. "
            "Run scripts/acceptance.py in the Codespace first. No candidate was executed.",
            file=sys.stderr,
        )
        sys.exit(3)
    summary = json.loads(args.acceptance_summary.read_text())
    if not summary.get("all_passed"):
        print(
            "GATED: Phase 1 acceptance has not passed yet (all_passed is false). "
            "No candidate was executed.",
            file=sys.stderr,
        )
        sys.exit(3)

    script_bytes = args.script.read_bytes()
    supports = {}
    for item in args.support:
        name, _, path = item.partition("=")
        supports[name] = Path(path).read_bytes()

    remote_dir = f"{WORKER_TMP}/{args.task_id}"
    stream_to_worker(args.codespace, remote_dir, "solution.sh", script_bytes)
    for name, data in supports.items():
        stream_to_worker(args.codespace, remote_dir, name, data)
    for name, data in [("solution.sh", script_bytes), *supports.items()]:
        remote_hash = worker_sha(args.codespace, f"{remote_dir}/{name}")
        if remote_hash != sha256_bytes(data):
            print(
                f"transfer hash mismatch for {name}: local {sha256_bytes(data)[:12]} "
                f"remote {remote_hash[:12]}",
                file=sys.stderr,
            )
            sys.exit(4)

    candidate_id = args.candidate_id or f"{record['script_sha256'][:12]}"
    support_flags = "".join(
        f" --support {name}={remote_dir}/{name}" for name in supports
    )
    grade_script_text = (
        "set -e\n"
        "cd /workspaces/gemma4-shell-grpo\n"
        "PYTHONPATH=src .venv/bin/python -m shell_grpo.cli "
        f"grade --task {args.task_id} --script {remote_dir}/solution.sh "
        f"--seed {args.seed} --candidate-id {candidate_id} --group-id pi-campaign "
        f"--out-dir {remote_dir}/out --config configs/runner.yaml{support_flags}\n"
    )
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    proc = worker_run(args.codespace, grade_script_text)
    if proc.returncode != 0:
        print(f"grade invocation failed (exit {proc.returncode}): {proc.stderr}", file=sys.stderr)
        sys.exit(5)
    try:
        grade_result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("grade output was not valid JSON", file=sys.stderr)
        print(proc.stdout[-2000:], file=sys.stderr)
        sys.exit(5)

    index = next_result_index(args.task_id)

    # Retrieve the execution evidence tar.
    tar_proc = worker_run(
        args.codespace,
        f"cd {remote_dir} && tar czf - out 2>/dev/null | base64",
    )
    evidence_path = None
    if tar_proc.returncode == 0 and tar_proc.stdout.strip():
        raw = base64.b64decode("".join(tar_proc.stdout.split()))
        out_dir = CAMPAIGN_ROOT / "results" / args.task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = out_dir / f"grade-evidence-{index:03d}.tgz"
        evidence_path.write_bytes(raw)

    verified = (
        grade_result["aggregate_status"] == "ok" and grade_result["task_score"] == 1.0
    )
    # `index` counts existing verification records; the evidence tar and the
    # record share it so a rerun after an invalidated attempt gets a new pair.
    record_out = {
        "result_id": (
            f"{args.task_id}-cand-{record['script_sha256'][:12]}-"
            f"{grade_result.get('runner_version', 'unknown')}-{index:03d}"
        ),
        "verified_utc": started,
        "seed": args.seed,
        "candidate_id": candidate_id,
        "verification": "verified" if verified else "failed",
        "task_score": grade_result["task_score"],
        "aggregate_status": grade_result["aggregate_status"],
        "critical_violations": grade_result["critical_violations"],
        "failed_checks": [
            f"{fr['fixture_id']}:{c['name']} ({c['detail']})"
            for fr in grade_result["fixture_results"]
            for c in fr["checks"]
            if c["required"] and not c["passed"]
        ],
        "fixture_sha256s": grade_result["fixture_sha256s"],
        "runner_version": grade_result["runner_version"],
        "image_digest": grade_result["image_digest"],
        "grade_result": grade_result,
        "evidence_tar": str(evidence_path.relative_to(CAMPAIGN_ROOT))
        if evidence_path
        else None,
        **{k: v for k, v in record.items() if k != "script_path"},
    }
    out_dir = CAMPAIGN_ROOT / "results" / args.task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"verification-{index:03d}.json"
    out_path.write_text(json.dumps(record_out, indent=2))

    print(json.dumps({
        "task_id": args.task_id,
        "result_id": record_out["result_id"],
        "verification": record_out["verification"],
        "task_score": record_out["task_score"],
        "aggregate_status": record_out["aggregate_status"],
        "record": str(out_path),
    }, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
