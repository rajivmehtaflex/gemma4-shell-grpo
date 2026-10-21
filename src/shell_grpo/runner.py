"""Restricted Docker runner and the grading driver (grade_script).

Pattern proven in reports/runtime-capabilities.md: the candidate executes as a
non-root uid inside a network-less container with explicit memory/pids/cpu
bounds, a read-only root filesystem, and only the fixture instance (rw) plus
the candidate script (ro) mounted. The verifier lives outside every
candidate-visible path. Candidate scripts never execute on the host.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .contracts import (
    INFRASTRUCTURE_ATTEMPTS,
    SCHEMA_VERSION,
    CheckResult,
    FixtureResult,
    GradeResult,
    derive_fixture_seeds,
    sha256_bytes,
)
from .fixtures import (
    FixtureInstance,
    build_instance,
    remove_tree,
    snapshot_tree,
)
from .rewards import finalize as finalize_reward
from .verifiers import FixtureVerdict, VerifyContext, score_simple
from .tasks.base import get_task

RUNNER_VERSION = "runner-1.0.0"

_DEFAULTS = {
    "image": "shell-grpo/grader:1.0.0",
    "user": "1000:1000",
    "memory": "256m",
    "memory_swap": "256m",
    "pids_limit": "128",
    "cpus": "1.0",
    "time_limit_seconds": 20,
    "syntax_check_seconds": 10,
    "output_cap_bytes": 1048576,
    "env": {"LANG": "C", "LC_ALL": "C", "TZ": "UTC"},
}


@dataclass
class RunnerConfig:
    image: str = _DEFAULTS["image"]
    user: str = _DEFAULTS["user"]
    memory: str = _DEFAULTS["memory"]
    memory_swap: str = _DEFAULTS["memory_swap"]
    pids_limit: str = _DEFAULTS["pids_limit"]
    cpus: str = _DEFAULTS["cpus"]
    time_limit_seconds: int = _DEFAULTS["time_limit_seconds"]
    syntax_check_seconds: int = _DEFAULTS["syntax_check_seconds"]
    output_cap_bytes: int = _DEFAULTS["output_cap_bytes"]
    env: dict = field(default_factory=lambda: dict(_DEFAULTS["env"]))

    @classmethod
    def load(cls, path: Path | None) -> "RunnerConfig":
        if path is None:
            return cls()
        import yaml

        raw = yaml.safe_load(path.read_text()) or {}
        section = raw.get("runner", raw)
        known = {k: v for k, v in section.items() if k in _DEFAULTS}
        env = section.get("env", _DEFAULTS["env"])
        cfg = cls(**known)
        if isinstance(env, dict):
            cfg.env = {str(k): str(v) for k, v in env.items()}
        return cfg


@dataclass
class Outcome:
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    duration_ms: int
    killed_by: str | None = None  # timeout | oom | output_cap
    infrastructure_error: str | None = None
    stdout_sha256: str | None = None


class RestrictedRunner:
    def __init__(self, config: RunnerConfig | None = None, work_root: Path | None = None):
        self.config = config or RunnerConfig()
        self.work_root = work_root or Path(
            os.environ.get("SHELL_GRPO_WORK", "/tmp/shell-grpo-grader")
        )
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.image_digest = ""
        probe = self._docker(["image", "inspect", "-f", "{{.Id}}", self.config.image])
        if probe.returncode == 0:
            self.image_digest = probe.stdout.decode().strip()

    # -- docker plumbing ---------------------------------------------------

    def _docker(self, args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["docker", *args], capture_output=True, timeout=timeout, check=False
        )

    def _base_flags(self, name: str, instance_dir: Path, cand_dir: Path) -> list[str]:
        cfg = self.config
        flags = [
            "run",
            "--name", name,
            "--network", "none",
            "-u", cfg.user,
            "--memory", cfg.memory,
            "--memory-swap", cfg.memory_swap,
            "--pids-limit", cfg.pids_limit,
            "--cpus", cfg.cpus,
            "--read-only",
            "--tmpfs", f"/tmp:rw,size=8m,uid={cfg.user.split(':')[0]}",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--ulimit", "fsize=33554432",
            "--ulimit", "nofile=256",
            "--ulimit", "nproc=128",
            "-w", "/work",
        ]
        for key, value in sorted(cfg.env.items()):
            flags += ["-e", f"{key}={value}"]
        flags += ["-e", "HOME=/tmp"]
        flags += ["-v", f"{instance_dir}:/work", "-v", f"{cand_dir}:/candidate:ro"]
        return flags

    # -- execution ---------------------------------------------------------

    def _prepare_candidate(self, script: bytes, support: dict[str, bytes] | None) -> Path:
        cand = self.work_root / f"cand-{uuid.uuid4().hex[:12]}"
        cand.mkdir()
        path = cand / "script.sh"
        path.write_bytes(script)
        os.chmod(path, 0o555)
        for rel, data in (support or {}).items():
            target = cand / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            os.chmod(target, 0o444)
        return cand

    def _capture(self, name: str, instance: FixtureInstance, cand: Path, args: list[str],
                 timeout: int, out_dir: Path | None) -> Outcome:
        cmd = self._base_flags(name, instance.root, cand) + [
            self.config.image, "bash", "/candidate/script.sh", *args
        ]
        started = time.monotonic()
        stdout_fh = tempfile_spill()
        stderr_fh = tempfile_spill()
        proc = None
        killed_by = None
        try:
            proc = subprocess.Popen(
                cmd, stdout=stdout_fh.handle, stderr=stderr_fh.handle, stdin=subprocess.DEVNULL
            )
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                killed_by = "timeout"
                self._docker(["kill", name], timeout=30)
                proc.wait(timeout=60)
        finally:
            duration_ms = int((time.monotonic() - started) * 1000)
            for fh in (stdout_fh, stderr_fh):
                fh.handle.flush()
        stdout_true = stdout_fh.path.stat().st_size
        stderr_true = stderr_fh.path.stat().st_size
        stdout_bytes = read_capped(stdout_fh.path, self.config.output_cap_bytes)
        stderr_bytes = read_capped(stderr_fh.path, self.config.output_cap_bytes)
        stdout_fh.close()
        stderr_fh.close()

        info = self._docker(
            ["inspect", "-f", "{{.State.OOMKilled}} {{.State.ExitCode}}", name], timeout=30
        )
        exit_code = None
        oom = False
        if info.returncode == 0 and info.stdout.strip():
            oom_s, code_s = info.stdout.decode().split()
            oom = oom_s.strip() == "true"
            exit_code = int(code_s)
        else:
            return Outcome(
                exit_code=None, stdout=stdout_bytes, stderr=stderr_bytes,
                duration_ms=duration_ms,
                infrastructure_error="container inspect failed after run (daemon error?)",
            )

        outcome = Outcome(
            exit_code=exit_code,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
            duration_ms=duration_ms,
            killed_by=killed_by,
            stdout_sha256=sha256_bytes(stdout_bytes),
        )
        if oom and killed_by is None:
            outcome.killed_by = "oom"
        if (
            len(stdout_bytes) > self.config.output_cap_bytes
            or len(stderr_bytes) > self.config.output_cap_bytes
        ):
            outcome.killed_by = "output_cap"
        if out_dir is not None:
            evidence = out_dir / f"exec-{name}.json"
            evidence.write_text(
                json.dumps(
                    {
                        "exit_code": outcome.exit_code,
                        "killed_by": outcome.killed_by,
                        "duration_ms": outcome.duration_ms,
                        "stdout_sha256": outcome.stdout_sha256,
                        "stdout_bytes": len(outcome.stdout),
                        "stdout_bytes_uncapped": stdout_true,
                        "stderr_bytes": len(outcome.stderr),
                        "stderr_bytes_uncapped": stderr_true,
                        "argv": args,
                        "stdout_preview": outcome.stdout[:4096].decode("utf-8", "replace"),
                        "stderr_preview": outcome.stderr[:4096].decode("utf-8", "replace"),
                    },
                    indent=2,
                )
            )
        return outcome

    def run_fixture(
        self,
        script: bytes,
        instance: FixtureInstance,
        support: dict[str, bytes] | None = None,
        out_dir: Path | None = None,
    ) -> Outcome:
        cand = self._prepare_candidate(script, support)
        name = f"sgrader-{uuid.uuid4().hex[:12]}"
        try:
            outcome = self._capture(
                name, instance, cand, instance.truth.argv,
                self.config.time_limit_seconds, out_dir,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            outcome = Outcome(
                exit_code=None, stdout=b"", stderr=b"", duration_ms=0,
                infrastructure_error=f"docker invocation failed: {exc}",
            )
        finally:
            self._docker(["rm", "-f", name], timeout=30)
            shutil.rmtree(cand, ignore_errors=True)
        return outcome

    def syntax_check(self, script: bytes) -> tuple[bool, str]:
        """bash -n inside the same restricted container; no fixture involved."""
        cand = self._prepare_candidate(script, None)
        try:
            name = f"sgrader-syntax-{uuid.uuid4().hex[:12]}"
            instance_dir = self.work_root / f"syntax-{uuid.uuid4().hex[:8]}"
            instance_dir.mkdir()
            cmd = self._base_flags(name, instance_dir, cand) + [
                self.config.image, "bash", "-n", "/candidate/script.sh"
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True,
                                      timeout=self.config.syntax_check_seconds, check=False)
                if proc.returncode != 0 and _looks_like_daemon_error(proc.returncode, proc.stderr):
                    return True, ""  # infrastructure problems are handled by the caller
                if proc.returncode != 0:
                    detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
                    return False, detail[-1] if detail else f"bash -n exit {proc.returncode}"
                return True, ""
            finally:
                self._docker(["rm", "-f", name], timeout=30)
                remove_tree(instance_dir)
        finally:
            shutil.rmtree(cand, ignore_errors=True)


def _looks_like_daemon_error(exit_code: int, stderr: bytes) -> bool:
    if exit_code == 125:
        return True
    lowered = stderr.lstrip()
    if lowered.startswith(b"docker: "):
        return True
    return b"Cannot connect to the Docker daemon" in stderr


def tempfile_spill() -> "_Spill":
    return _Spill()


def read_capped(path: Path, cap: int) -> bytes:
    """Read at most cap+1 bytes so an over-cap file can never exhaust memory."""
    with open(path, "rb") as fh:
        data = fh.read(cap + 1)
    path.unlink(missing_ok=True)
    return data


class _Spill:
    """Spool subprocess output to a temp file (avoids pipe deadlocks)."""

    def __init__(self):
        import tempfile

        self.fd, self.name = tempfile.mkstemp(prefix="sgrpo-out-")
        self.path = Path(self.name)
        self.handle = os.fdopen(self.fd, "wb")

    def close(self) -> None:
        self.handle.close()
        self.path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# grade_script
# ---------------------------------------------------------------------------


def _script_defect(script_bytes: bytes) -> str | None:
    """Cheap textual invalid_script checks before any execution."""
    if not script_bytes.strip():
        return "empty script"
    try:
        text = script_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return "script is not valid UTF-8"
    if "\x00" in text:
        return "script contains NUL bytes"
    return None


def grade_script(
    task_id: str,
    script: bytes | str,
    group_seed: int,
    runner: RestrictedRunner,
    *,
    candidate_id: str = "candidate",
    group_id: str = "group",
    out_dir: Path | None = None,
    support_files: dict[str, bytes] | None = None,
) -> GradeResult:
    if isinstance(script, str):
        script_bytes = script.encode("utf-8")
    else:
        script_bytes = script
    task = get_task(task_id)
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    def base_result(status: str, score: float | None, checks: list[CheckResult]) -> GradeResult:
        result = GradeResult(
            schema_version=SCHEMA_VERSION,
            task_id=task_id,
            group_id=group_id,
            candidate_id=candidate_id,
            script_sha256=sha256_bytes(script_bytes),
            fixture_sha256s={},
            checks=checks,
            critical_violations=[],
            fixture_results=[],
            aggregate_status=status,
            task_score=score,
            runner_version=RUNNER_VERSION,
            image_digest=runner.image_digest,
            artifacts=[],
        )
        return result

    defect = _script_defect(script_bytes)
    if defect is None:
        parses, detail = runner.syntax_check(script_bytes)
        if not parses:
            defect = detail or "bash -n failed"

    if defect is not None:
        result = base_result(
            "invalid_script", 0.0,
            [CheckResult("script_parses", False, True, defect)],
        )
        return result

    seeds = derive_fixture_seeds(task_id, group_seed, task.fixture_ids())
    fixture_results: list[FixtureResult] = []
    criticals: list[str] = []
    flattened_checks: list[CheckResult] = []
    fixture_hashes: dict[str, str] = {}

    for case in task.fixtures:
        attempt = 0
        while True:
            attempt += 1
            instance = build_instance(
                case.fixture_id, seeds[case.fixture_id],
                runner.work_root / f"inst-{case.fixture_id}-{attempt}-{uuid.uuid4().hex[:8]}",
                case.build,
            )
            fixture_hashes[case.fixture_id] = instance.fixture_sha256
            attempt_dir = out_dir / f"fixture-{case.fixture_id}" if out_dir else None
            outcome = runner.run_fixture(
                script_bytes, instance, support_files, attempt_dir
            )
            post = snapshot_tree(instance.root)

            if outcome.infrastructure_error is not None:
                if attempt < INFRASTRUCTURE_ATTEMPTS:
                    remove_tree(instance.root)
                    continue
                fixture_results.append(
                    FixtureResult(
                        fixture_id=case.fixture_id,
                        seed=seeds[case.fixture_id],
                        fixture_sha256=instance.fixture_sha256,
                        status="infrastructure_error",
                        score=None,
                        exit_code=None,
                        attempts=attempt,
                        artifacts=[outcome.infrastructure_error],
                    )
                )
                remove_tree(instance.root)
                break

            ctx = VerifyContext(
                instance=instance,
                post=post,
                exit_code=outcome.exit_code if outcome.exit_code is not None else -1,
                stdout=outcome.stdout,
                stderr=outcome.stderr,
            )

            if outcome.killed_by is not None:
                verdict = FixtureVerdict()
                violation_if_changed_scope(ctx, verdict)
                status = "resource_limit"
                score = 0.0
                checks = [CheckResult(
                    f"limit:{outcome.killed_by}", False, True,
                    f"killed by {outcome.killed_by}", 
                )]
            elif outcome.exit_code != 0 and not instance.truth.expects_failure:
                verdict = FixtureVerdict()
                violation_if_changed_scope(ctx, verdict)
                status = "runtime_error"
                score = 0.0
                tail = outcome.stderr.decode("utf-8", "replace").strip().splitlines()
                checks = [CheckResult(
                    "exit_0", False, True,
                    f"exit={outcome.exit_code}; stderr: {tail[-1][:120] if tail else ''}",
                )]
            else:
                if case.verify is not None:
                    verdict = case.verify(ctx)
                else:
                    verdict = score_simple(
                        ctx,
                        instance.truth.expected_stdout,
                        expects_failure=instance.truth.expects_failure,
                        expected_exit=instance.truth.expected_exit,
                    )
                status = "ok"
                score = verdict.score
                checks = verdict.checks

            fixture_results.append(
                FixtureResult(
                    fixture_id=case.fixture_id,
                    seed=seeds[case.fixture_id],
                    fixture_sha256=instance.fixture_sha256,
                    status=status,
                    score=score,
                    checks=checks,
                    critical_violations=list(verdict.critical_violations),
                    exit_code=outcome.exit_code,
                    stdout_sha256=outcome.stdout_sha256,
                    stdout_bytes=len(outcome.stdout),
                    stderr_bytes=len(outcome.stderr),
                    duration_ms=outcome.duration_ms,
                    attempts=attempt,
                    artifacts=[str(p) for p in [attempt_dir] if attempt_dir],
                )
            )
            criticals.extend(verdict.critical_violations)
            for check in checks:
                flattened_checks.append(
                    CheckResult(
                        name=f"{case.fixture_id}:{check.name}",
                        passed=check.passed,
                        required=check.required,
                        detail=check.detail,
                    )
                )
            remove_tree(instance.root)
            break

    result = base_result("ok", None, flattened_checks)
    result.fixture_results = fixture_results
    result.critical_violations = criticals
    result.fixture_sha256s = fixture_hashes
    if out_dir is not None:
        result.artifacts = [str(out_dir)]
    finalize_reward(result, task.progress_ids(), task.weights())
    return result


def violation_if_changed_scope(ctx: VerifyContext, verdict: FixtureVerdict) -> None:
    """Preservation gate applied even when execution failed outright."""
    from .verifiers import violation_if_changed

    violation_if_changed(ctx, verdict, "", label="input")
