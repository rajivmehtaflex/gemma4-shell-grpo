"""Shared verifier checks and fixture scoring models.

Each task module combines these helpers into a per-fixture scoring function.
Preservation checks are gates: a failure records a task-critical violation.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from .contracts import CheckResult
from .fixtures import Entry, FixtureInstance, Snapshot


@dataclass
class VerifyContext:
    instance: FixtureInstance
    post: Snapshot
    exit_code: int
    stdout: bytes
    stderr: bytes

    @property
    def truth(self):
        return self.instance.truth

    @property
    def pre(self) -> Snapshot:
        return self.instance.pre


@dataclass
class FixtureVerdict:
    checks: list[CheckResult] = field(default_factory=list)
    critical_violations: list[str] = field(default_factory=list)
    score: float = 0.0


def _differences(pre: Snapshot, post: Snapshot, scope: str, exclude: tuple[str, ...]):
    """Yield human-readable diffs for entries under scope, minus exclude prefixes."""
    prefixes = tuple(f"{p}/" for p in exclude)
    names = {
        n
        for n in set(pre) | set(post)
        if n.startswith(scope) and not any(n.startswith(x) for x in prefixes)
    }
    for name in sorted(names):
        before, after = pre.get(name), post.get(name)
        if before is None and after is not None:
            yield f"created: {name}"
        elif before is not None and after is None:
            yield f"removed: {name}"
        elif before.to_dict() != after.to_dict():
            yield f"changed: {name}"


def check_unchanged(
    ctx: VerifyContext, scope: str = "", exclude: tuple[str, ...] = ()
) -> CheckResult:
    """Gate: every entry under scope (default: whole instance) is byte-identical."""
    diffs = _differences(ctx.pre, ctx.post, scope, exclude)
    first = list(diffs)
    return CheckResult(
        name=f"preserved:{scope or 'instance'}",
        passed=not first,
        required=True,
        detail="; ".join(first[:12]) if first else "unchanged",
    )


def gate_preservation(ctx: VerifyContext, scope: str = "") -> bool:
    result = check_unchanged(ctx, scope)
    return result.passed


def violation_if_changed(
    ctx: VerifyContext, verdict: FixtureVerdict, scope: str = "", label: str = "input"
) -> bool:
    """Record a task-critical violation when the protected scope changed."""
    diffs = list(_differences(ctx.pre, ctx.post, scope, ()))
    if diffs:
        verdict.critical_violations.append(f"{label}_mutated: {'; '.join(diffs[:8])}")
        return True
    return False


def check_stdout_exact(ctx: VerifyContext, expected: bytes | None) -> CheckResult:
    if expected is None:
        raise ValueError("expected stdout not declared for this fixture")
    return CheckResult(
        name="stdout_exact",
        passed=ctx.stdout == expected,
        required=True,
        detail=(
            f"expected {len(expected)}B, got {len(ctx.stdout)}B"
            if ctx.stdout != expected
            else "match"
        ),
    )


def check_stdout_empty(ctx: VerifyContext) -> CheckResult:
    return CheckResult(
        name="stdout_empty",
        passed=ctx.stdout == b"",
        required=True,
        detail=f"{len(ctx.stdout)}B on stdout" if ctx.stdout else "empty",
    )


def check_stderr_nonempty(ctx: VerifyContext) -> CheckResult:
    return CheckResult(
        name="stderr_nonempty",
        passed=ctx.stderr.strip() != b"",
        required=True,
        detail="nonempty" if ctx.stderr.strip() else "empty stderr",
    )


def check_exit_equals(ctx: VerifyContext, code: int) -> CheckResult:
    return CheckResult(
        name=f"exit_{code}",
        passed=ctx.exit_code == code,
        required=True,
        detail=f"exit={ctx.exit_code}",
    )


def check_exit_nonzero(ctx: VerifyContext) -> CheckResult:
    return CheckResult(
        name="exit_nonzero",
        passed=ctx.exit_code != 0,
        required=True,
        detail=f"exit={ctx.exit_code}",
    )


# ---------------------------------------------------------------------------
# Composite fixture scoring models
# ---------------------------------------------------------------------------


def score_simple(
    ctx: VerifyContext,
    expected_stdout: bytes | None,
    *,
    expects_failure: bool = False,
    expected_exit: int | None = None,
    scope: str = "",
) -> FixtureVerdict:
    """All-or-nothing fixture: exact stdout + exit convention + full preservation.

    Used for counting/listing/empty fixtures. For failure fixtures the checks
    are: expected exit code, empty stdout, nonempty stderr, zero mutation.
    """
    verdict = FixtureVerdict()
    if expects_failure:
        if expected_exit is None:
            verdict.checks.append(check_exit_nonzero(ctx))
        else:
            verdict.checks.append(check_exit_equals(ctx, expected_exit))
        verdict.checks.append(check_stdout_empty(ctx))
        verdict.checks.append(check_stderr_nonempty(ctx))
        mutated = violation_if_changed(ctx, verdict, scope, label="mutation")
        if mutated:
            verdict.score = 0.0
            return verdict
        verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
        return verdict
    verdict.checks.append(check_stdout_exact(ctx, expected_stdout))
    verdict.checks.append(check_exit_equals(ctx, expected_exit or 0))
    mutated = violation_if_changed(ctx, verdict, scope, label="input")
    if mutated:
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


def _dir_entries_under(snapshot: Snapshot, prefix: str) -> dict[str, Entry]:
    clean = prefix.rstrip("/") + "/"
    return {
        name[len(clean):]: entry
        for name, entry in snapshot.items()
        if name.startswith(clean)
    }


def score_copied_fraction(
    ctx: VerifyContext,
    dest_prefix: str,
    required: dict[str, str],
    *,
    source_scope: str = "",
    extra_is_critical: bool = True,
) -> FixtureVerdict:
    """Fraction of required files present at dest with exact bytes.

    Critical (score 0): extra entries in the destination, source mutation,
    or a missing destination directory. Preservation is a gate, never a
    positive reward component.
    """
    verdict = FixtureVerdict()
    mutated = violation_if_changed(ctx, verdict, source_scope, label="source")
    dest = _dir_entries_under(ctx.post, dest_prefix)
    missing_dir = dest_prefix not in ctx.pre or ctx.pre[dest_prefix].kind != "dir"
    if missing_dir:
        verdict.checks.append(
            CheckResult("dest_dir_present", False, True, "destination absent in fixture")
        )
        verdict.score = 0.0
        return verdict
    copied = 0
    failures = []
    for relpath, sha in sorted(required.items()):
        entry = dest.get(relpath)
        if entry is not None and entry.kind == "file" and entry.sha256 == sha:
            copied += 1
        else:
            state = "absent" if entry is None else "wrong-bytes" if entry.kind == "file" else entry.kind
            failures.append(f"{relpath}: {state}")
    verdict.checks.append(
        CheckResult(
            "required_files_copied",
            copied == len(required),
            True,
            f"{copied}/{len(required)} copied correctly"
            + ("; " + "; ".join(failures[:8]) if failures else ""),
        )
    )
    extras = sorted(set(dest) - set(required))
    if extras:
        if extra_is_critical:
            verdict.critical_violations.append(
                f"extra_dest_entries: {', '.join(extras[:8])}"
            )
        verdict.checks.append(
            CheckResult("no_extra_dest_entries", False, True, ", ".join(extras[:8]))
        )
    else:
        verdict.checks.append(CheckResult("no_extra_dest_entries", True, True, "none"))
    if mutated:
        verdict.score = 0.0
        return verdict
    if extras and extra_is_critical:
        verdict.score = 0.0
        return verdict
    verdict.score = copied / len(required) if required else 1.0
    return verdict


def score_text_output(
    ctx: VerifyContext,
    expected_lines: list[bytes],
    *,
    totals_weight: float = 0.8,
    order_weight: float = 0.2,
    scope: str = "",
) -> FixtureVerdict:
    """Line-based output (TSV aggregation): totals fraction weighted against order.

    Every expected key with a correct full line counts toward the totals
    fraction; the output must additionally be in the expected (byte-sorted)
    order and contain no extra lines. Extra fabricated keys are critical.
    """
    verdict = FixtureVerdict()
    mutated = violation_if_changed(ctx, verdict, scope, label="input")
    actual = ctx.stdout.split(b"\n")
    if actual and actual[-1] == b"":
        actual = actual[:-1]
    expected_set = {line.split(b"\t", 1)[0] if b"\t" in line else line for line in expected_lines}
    actual_keys = [line.split(b"\t", 1)[0] if b"\t" in line else line for line in actual]
    extras = sorted(set(actual_keys) - expected_set)
    if extras:
        verdict.critical_violations.append(f"fabricated_keys: {', '.join(e.decode('utf-8', 'replace') for e in extras[:8])}")
    correct = sum(1 for line in actual if line in set(expected_lines))
    totals_fraction = correct / len(expected_lines) if expected_lines else (1.0 if not actual else 0.0)
    order_ok = actual == expected_lines
    verdict.checks.append(
        CheckResult(
            "key_totals",
            correct == len(expected_lines) and not extras,
            True,
            f"{correct}/{len(expected_lines)} correct lines",
        )
    )
    verdict.checks.append(
        CheckResult("output_order", order_ok, True, "byte order" if order_ok else "order/exactness mismatch")
    )
    if mutated:
        verdict.score = 0.0
        return verdict
    if extras:
        verdict.score = 0.0
        return verdict
    verdict.score = min(
        1.0, totals_fraction * totals_weight + (1.0 if order_ok else 0.0) * order_weight
    )
    return verdict


def score_csv_roundtrip(
    ctx: VerifyContext,
    expected_rows: list[list[str]],
    *,
    scope: str = "",
) -> FixtureVerdict:
    """Independent-parser check for S07: parse output as CSV and compare values."""
    verdict = FixtureVerdict()
    mutated = violation_if_changed(ctx, verdict, scope, label="input")
    text = ctx.stdout.decode("utf-8", "replace")
    header_ok = text.split("\n", 1)[0] == "id,name"
    verdict.checks.append(CheckResult("header_exact", header_ok, True, text.split("\n", 1)[0][:40]))
    verdict.checks.append(
        CheckResult("lf_only", b"\r" not in ctx.stdout, True, "no CR bytes" if b"\r" not in ctx.stdout else "CR found")
    )
    rows = []
    parse_error = None
    try:
        reader = csv.reader(io.StringIO(text, newline=""))
        for row in reader:
            rows.append(row)
    except csv.Error as exc:
        parse_error = str(exc)
    if parse_error is not None:
        verdict.checks.append(CheckResult("parses_as_csv", False, True, parse_error))
    else:
        verdict.checks.append(CheckResult("parses_as_csv", True, True, "ok"))
    data_rows = rows[1:] if rows and header_ok else rows
    correct = 0
    for idx, expected in enumerate(expected_rows):
        if idx < len(data_rows) and data_rows[idx][:2] == expected:
            correct += 1
    count_ok = len(data_rows) == len(expected_rows)
    verdict.checks.append(
        CheckResult(
            "row_values",
            correct == len(expected_rows) and count_ok,
            True,
            f"{correct}/{len(expected_rows)} rows correct"
            + ("" if count_ok else f"; got {len(data_rows)} rows"),
        )
    )
    if mutated:
        verdict.score = 0.0
        return verdict
    if parse_error is not None or not header_ok or b"\r" in ctx.stdout or not count_ok:
        # Structural failures cap the score below full even with some correct rows.
        if parse_error is not None:
            verdict.score = 0.0
            return verdict
        verdict.score = min(0.5, correct / len(expected_rows) if expected_rows else 0.0)
        return verdict
    verdict.score = correct / len(expected_rows) if expected_rows else 1.0
    return verdict


def all_required_passed(verdict: FixtureVerdict) -> bool:
    return all(c.passed for c in verdict.checks if c.required)
