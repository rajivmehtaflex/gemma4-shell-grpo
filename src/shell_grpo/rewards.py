"""Frozen reward aggregation (PLAN.md Phase 1, reward-version r1).

Rules, in order:
1. Any fixture with an unresolved infrastructure error makes the task
   unscorable: aggregate status infrastructure_error, task score null.
2. Otherwise aggregate status is the first fixture status present in
   STATUS_PRECEDENCE.
3. Once every fixture is scored: a task-critical violation, or no required
   functional progress on the declared progress fixtures, makes the task
   reward zero.
4. Otherwise the task score is the declared weighted fixture average, capped
   at one. Full reward (1.0) requires every required check across all
   fixtures to pass; fixture scores already encode this.
"""

from __future__ import annotations

from .contracts import STATUS_PRECEDENCE, FixtureResult, GradeResult, aggregate_status


def is_unscorable(fixture_results: list[FixtureResult]) -> bool:
    return any(f.status == "infrastructure_error" for f in fixture_results)


def score_task(
    fixture_results: list[FixtureResult],
    critical_violations: list[str],
    progress_fixture_ids: list[str],
    weights: dict[str, float],
) -> tuple[str, float | None]:
    """Return (aggregate_status, task_score_or_None) under reward version r1."""
    if is_unscorable(fixture_results):
        return "infrastructure_error", None
    if not fixture_results:
        raise ValueError("score_task requires at least one fixture result")
    status = aggregate_status([f.status for f in fixture_results])
    if critical_violations:
        return status, 0.0
    scored = [f for f in fixture_results if f.score is not None]
    progress_scores = [
        f.score
        for f in scored
        if f.fixture_id in progress_fixture_ids and f.status == "ok"
    ]
    if progress_fixture_ids and not any((s or 0.0) > 0.0 for s in progress_scores):
        # No required functional progress on the declared nonempty fixtures.
        return status, 0.0
    total_weight = sum(weights.get(f.fixture_id, 1.0) for f in fixture_results)
    if total_weight <= 0:
        raise ValueError("fixture weights must sum to a positive number")
    weighted = sum(
        (f.score or 0.0) * weights.get(f.fixture_id, 1.0) for f in fixture_results
    )
    score = min(1.0, weighted / total_weight)
    return status, score


def finalize(result: GradeResult, progress_fixture_ids: list[str], weights: dict[str, float]) -> None:
    """Compute aggregate status + task score on a result and update it in place."""
    if is_unscorable(result.fixture_results):
        result.aggregate_status = "infrastructure_error"
        result.task_score = None
        return
    result.aggregate_status = aggregate_status([f.status for f in result.fixture_results])
    _, score = score_task(
        result.fixture_results, result.critical_violations, progress_fixture_ids, weights
    )
    result.task_score = score
