"""Typed contracts for the shell-grpo grader.

Frozen before runner implementation (PLAN.md Phase 1 interface). Everything the
runner, verifiers and rewards modules exchange passes through the schemas and
validation in this module. Stdlib only by design: the schemas must be loadable
on any machine without a project environment.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = "1.0.0"
REWARD_VERSION = "r1"

#: Execution statuses, frozen by PLAN.md Phase 1.
VALID_STATUSES = (
    "ok",
    "invalid_script",
    "runtime_error",
    "resource_limit",
    "infrastructure_error",
)

#: Aggregate precedence: the first status present in this order wins.
STATUS_PRECEDENCE = (
    "infrastructure_error",
    "invalid_script",
    "resource_limit",
    "runtime_error",
    "ok",
)

#: Max retries for a genuine infrastructure error on one fixture:
#: the exact saved script/fixture runs at most 3 times (1 + 2 retries).
INFRASTRUCTURE_ATTEMPTS = 3


class ContractError(ValueError):
    """Raised when a record violates the frozen schema or invariants."""


def aggregate_status(statuses: list[str]) -> str:
    """First status present in STATUS_PRECEDENCE; empty list is an error."""
    present = set(statuses)
    if not present:
        raise ContractError("aggregate_status called with no fixture statuses")
    for status in STATUS_PRECEDENCE:
        if status in present:
            return status
    raise ContractError(f"unknown statuses: {sorted(present)}")


def _check_str(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{name} must be a nonempty string, got {value!r}")


def _opt_float(value: Any, name: str) -> None:
    if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        raise ContractError(f"{name} must be null or a number, got {value!r}")
    if value is not None and not 0.0 <= float(value) <= 1.0:
        raise ContractError(f"{name} must be within [0, 1], got {value}")


@dataclass
class CheckResult:
    """One named behavioral check for one fixture."""

    name: str
    passed: bool
    required: bool = True
    detail: str = ""

    def __post_init__(self) -> None:
        _check_str(self.name, "CheckResult.name")
        if not isinstance(self.passed, bool):
            raise ContractError("CheckResult.passed must be bool")
        if not isinstance(self.required, bool):
            raise ContractError("CheckResult.required must be bool")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "required": self.required,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckResult":
        return cls(
            name=data["name"],
            passed=data["passed"],
            required=data.get("required", True),
            detail=data.get("detail", ""),
        )


@dataclass
class FixtureResult:
    """Execution and scoring evidence for one fixture of one candidate."""

    fixture_id: str
    seed: int
    fixture_sha256: str
    status: str
    score: float | None
    checks: list[CheckResult] = field(default_factory=list)
    critical_violations: list[str] = field(default_factory=list)
    exit_code: int | None = None
    stdout_sha256: str | None = None
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    duration_ms: int = 0
    attempts: int = 1
    artifacts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _check_str(self.fixture_id, "FixtureResult.fixture_id")
        if not isinstance(self.seed, int):
            raise ContractError("FixtureResult.seed must be int")
        _check_str(self.fixture_sha256, "FixtureResult.fixture_sha256")
        if self.status not in VALID_STATUSES:
            raise ContractError(f"FixtureResult.status invalid: {self.status!r}")
        _opt_float(self.score, "FixtureResult.score")
        if self.status == "infrastructure_error" and self.score is not None:
            raise ContractError("unresolved infrastructure_error must have null score")

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "seed": self.seed,
            "fixture_sha256": self.fixture_sha256,
            "status": self.status,
            "score": self.score,
            "checks": [c.to_dict() for c in self.checks],
            "critical_violations": list(self.critical_violations),
            "exit_code": self.exit_code,
            "stdout_sha256": self.stdout_sha256,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "duration_ms": self.duration_ms,
            "attempts": self.attempts,
            "artifacts": list(self.artifacts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FixtureResult":
        return cls(
            fixture_id=data["fixture_id"],
            seed=data["seed"],
            fixture_sha256=data["fixture_sha256"],
            status=data["status"],
            score=data["score"],
            checks=[CheckResult.from_dict(c) for c in data.get("checks", [])],
            critical_violations=list(data.get("critical_violations", [])),
            exit_code=data.get("exit_code"),
            stdout_sha256=data.get("stdout_sha256"),
            stdout_bytes=data.get("stdout_bytes", 0),
            stderr_bytes=data.get("stderr_bytes", 0),
            duration_ms=data.get("duration_ms", 0),
            attempts=data.get("attempts", 1),
            artifacts=list(data.get("artifacts", [])),
        )


@dataclass
class TaskRecord:
    """Static identity of one diagnostic exercise (DESIGN.md task contract)."""

    task_id: str
    family_id: str
    source_cluster_id: str
    prompt: list[dict[str, str]]
    fixture_id: str
    verifier_id: str
    invocation: str
    split: str
    provenance: dict[str, Any]
    schema_version: str = SCHEMA_VERSION
    reward_version: str = REWARD_VERSION
    fixtures_declared: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _check_str(self.task_id, "TaskRecord.task_id")
        _check_str(self.family_id, "TaskRecord.family_id")
        _check_str(self.source_cluster_id, "TaskRecord.source_cluster_id")
        _check_str(self.fixture_id, "TaskRecord.fixture_id")
        _check_str(self.verifier_id, "TaskRecord.verifier_id")
        _check_str(self.split, "TaskRecord.split")
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError(
                f"TaskRecord schema_version {self.schema_version!r} != {SCHEMA_VERSION!r}"
            )
        if not isinstance(self.prompt, list) or not self.prompt:
            raise ContractError("TaskRecord.prompt must be a nonempty list of messages")
        for message in self.prompt:
            if set(message) < {"role", "content"}:
                raise ContractError("TaskRecord.prompt messages need role and content")
        if self.reward_version != REWARD_VERSION:
            raise ContractError(
                f"TaskRecord reward_version {self.reward_version!r} != {REWARD_VERSION!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "family_id": self.family_id,
            "source_cluster_id": self.source_cluster_id,
            "prompt": [dict(m) for m in self.prompt],
            "fixture_id": self.fixture_id,
            "verifier_id": self.verifier_id,
            "invocation": self.invocation,
            "split": self.split,
            "provenance": dict(self.provenance),
            "reward_version": self.reward_version,
            "fixtures_declared": [dict(f) for f in self.fixtures_declared],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRecord":
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            task_id=data["task_id"],
            family_id=data["family_id"],
            source_cluster_id=data["source_cluster_id"],
            prompt=[dict(m) for m in data["prompt"]],
            fixture_id=data["fixture_id"],
            verifier_id=data["verifier_id"],
            invocation=data["invocation"],
            split=data["split"],
            provenance=dict(data.get("provenance", {})),
            reward_version=data.get("reward_version", REWARD_VERSION),
            fixtures_declared=[dict(f) for f in data.get("fixtures_declared", [])],
        )


@dataclass
class GradeResult:
    """Full scoring record for one candidate script on one task."""

    schema_version: str
    task_id: str
    group_id: str
    candidate_id: str
    script_sha256: str
    fixture_sha256s: dict[str, str]
    checks: list[CheckResult]
    critical_violations: list[str]
    fixture_results: list[FixtureResult]
    aggregate_status: str
    task_score: float | None
    reward_version: str = REWARD_VERSION
    runner_version: str = ""
    image_digest: str = ""
    artifacts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        _check_str(self.task_id, "GradeResult.task_id")
        _check_str(self.group_id, "GradeResult.group_id")
        _check_str(self.candidate_id, "GradeResult.candidate_id")
        _check_str(self.script_sha256, "GradeResult.script_sha256")
        if self.schema_version != SCHEMA_VERSION:
            raise ContractError(
                f"GradeResult schema_version {self.schema_version!r} != {SCHEMA_VERSION!r}"
            )
        if self.aggregate_status not in VALID_STATUSES:
            raise ContractError(f"aggregate_status invalid: {self.aggregate_status!r}")
        _opt_float(self.task_score, "GradeResult.task_score")
        statuses = [f.status for f in self.fixture_results]
        if statuses and self.aggregate_status != aggregate_status(statuses):
            raise ContractError(
                f"aggregate_status {self.aggregate_status!r} does not match "
                f"fixture precedence for {statuses!r}"
            )
        if "infrastructure_error" in statuses and self.task_score is not None:
            raise ContractError("unresolved infrastructure error requires null task_score")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "group_id": self.group_id,
            "candidate_id": self.candidate_id,
            "script_sha256": self.script_sha256,
            "fixture_sha256s": dict(self.fixture_sha256s),
            "checks": [c.to_dict() for c in self.checks],
            "critical_violations": list(self.critical_violations),
            "fixture_results": [f.to_dict() for f in self.fixture_results],
            "aggregate_status": self.aggregate_status,
            "task_score": self.task_score,
            "reward_version": self.reward_version,
            "runner_version": self.runner_version,
            "image_digest": self.image_digest,
            "artifacts": list(self.artifacts),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GradeResult":
        return cls(
            schema_version=data["schema_version"],
            task_id=data["task_id"],
            group_id=data["group_id"],
            candidate_id=data["candidate_id"],
            script_sha256=data["script_sha256"],
            fixture_sha256s=dict(data.get("fixture_sha256s", {})),
            checks=[CheckResult.from_dict(c) for c in data.get("checks", [])],
            critical_violations=list(data.get("critical_violations", [])),
            fixture_results=[FixtureResult.from_dict(f) for f in data.get("fixture_results", [])],
            aggregate_status=data["aggregate_status"],
            task_score=data["task_score"],
            reward_version=data.get("reward_version", REWARD_VERSION),
            runner_version=data.get("runner_version", ""),
            image_digest=data.get("image_digest", ""),
            artifacts=list(data.get("artifacts", [])),
        )


def validate_grade_result(result: GradeResult) -> None:
    """Adversarial invariant check beyond __post_init__ (used by the harness)."""
    for fixture in result.fixture_results:
        if fixture.status == "infrastructure_error":
            if fixture.score is not None:
                raise ContractError("fixture infrastructure_error must carry null score")
            continue
        if fixture.status == "ok":
            failed_required = [c for c in fixture.checks if c.required and not c.passed]
            if fixture.score == 1.0 and failed_required:
                raise ContractError(
                    f"fixture {fixture.fixture_id}: score 1.0 with failed required checks"
                )
        else:
            if fixture.score not in (None, 0.0) and fixture.status in (
                "invalid_script",
                "runtime_error",
                "resource_limit",
            ):
                # Non-ok fixtures may only be unscored (pre-check) or zero.
                raise ContractError(
                    f"fixture {fixture.fixture_id}: non-ok status {fixture.status} "
                    f"cannot carry score {fixture.score}"
                )
    if result.aggregate_status == "infrastructure_error" and result.task_score is not None:
        raise ContractError("aggregate infrastructure_error requires null task_score")


def derive_fixture_seeds(task_id: str, group_seed: int, fixture_ids: list[str]) -> dict[str, int]:
    """Deterministic per-fixture seeds derived from the group seed.

    Every candidate in one GRPO group passes the same group_seed and therefore
    receives the same fixture-seed set; different groups derive different sets.
    """
    seeds: dict[str, int] = {}
    for fixture_id in fixture_ids:
        digest = hmac.new(
            str(group_seed).encode(), f"{task_id}:{fixture_id}".encode(), hashlib.sha256
        ).hexdigest()
        seeds[fixture_id] = int(digest[:16], 16)
    return seeds


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
