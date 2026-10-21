"""Frozen reward-rule tests: every boundary example from PLAN.md Phase 1."""

import pytest

from shell_grpo.contracts import CheckResult, FixtureResult
from shell_grpo.rewards import score_task

W = {"a": 1.0, "b": 1.0}


def fx(fixture_id, status, score, checks=None):
    return FixtureResult(
        fixture_id=fixture_id,
        seed=1,
        fixture_sha256="0" * 64,
        status=status,
        score=score,
        checks=checks or [],
    )


def test_ok_ok_full_reward():
    status, score = score_task([fx("a", "ok", 1.0), fx("b", "ok", 1.0)], [], ["b"], W)
    assert (status, score) == ("ok", 1.0)


def test_plan_example_ok_then_runtime_error_is_runtime_error_with_partial_reward():
    results = [fx("a", "ok", 1.0), fx("b", "runtime_error", 0.0)]
    status, score = score_task(results, [], ["a"], W)
    assert status == "runtime_error"
    assert score == 0.5


def test_plan_example_ok_then_infrastructure_error_is_unscorable():
    results = [fx("a", "ok", 1.0), fx("b", "infrastructure_error", None)]
    status, score = score_task(results, [], ["a"], W)
    assert status == "infrastructure_error"
    assert score is None


def test_critical_violation_zeroes_task_regardless_of_scores():
    results = [fx("a", "ok", 1.0), fx("b", "ok", 1.0)]
    status, score = score_task(results, ["source_mutated: x"], ["b"], W)
    assert status == "ok"
    assert score == 0.0


def test_no_progress_on_nonempty_fixture_zeroes_noop_script():
    # A no-op passes the empty fixture and the decoy zero fixture but fails
    # both declared progress fixtures -> task reward zero.
    results = [
        fx("empty", "ok", 1.0),
        fx("decoy", "ok", 1.0),
        fx("main", "ok", 0.0),
        fx("main2", "ok", 0.0),
    ]
    status, score = score_task(results, [], ["main", "main2"], W)
    assert score == 0.0


def test_hardcoded_zero_answer_with_progress_fixture_scored_earns_partial():
    # Passing one progress fixture is functional progress: partial reward stands.
    results = [
        fx("empty", "ok", 1.0),
        fx("decoy", "ok", 1.0),
        fx("main", "ok", 1.0),
        fx("main2", "ok", 0.0),
    ]
    status, score = score_task(results, [], ["main", "main2"], W)
    assert status == "ok"
    assert score == pytest.approx(0.75)


def test_weights_change_the_average():
    results = [fx("a", "ok", 1.0), fx("b", "ok", 0.0)]
    _, score = score_task(results, [], ["a"], {"a": 3.0, "b": 1.0})
    assert score == pytest.approx(0.75)


def test_all_fixtures_resource_limit_zeroes_score_keeps_status():
    results = [fx("a", "resource_limit", 0.0), fx("b", "resource_limit", 0.0)]
    status, score = score_task(results, [], ["a"], W)
    assert status == "resource_limit"
    assert score == 0.0


def test_mixed_ok_and_resource_limit_keeps_partial():
    results = [fx("a", "ok", 1.0), fx("b", "resource_limit", 0.0)]
    status, score = score_task(results, [], ["a"], W)
    assert status == "resource_limit"
    assert score == pytest.approx(0.5)


def test_invalid_script_all_fixtures_zero():
    results = [fx("a", "invalid_script", 0.0), fx("b", "invalid_script", 0.0)]
    status, score = score_task(results, [], ["a"], W)
    assert status == "invalid_script"
    assert score == 0.0


def test_progress_gate_ignores_non_ok_fixture_scores():
    results = [fx("main", "runtime_error", 0.0), fx("empty", "ok", 1.0)]
    _, score = score_task(results, [], ["main"], W)
    assert score == 0.0


def test_full_reward_requires_required_checks_via_fixture_scores():
    # A fixture that failed a required check cannot carry score 1.0; the
    # runner never produces this combination, and validate_grade_result
    # rejects it if it ever appears.
    from shell_grpo.contracts import GradeResult, validate_grade_result

    bad = FixtureResult(
        fixture_id="a",
        seed=1,
        fixture_sha256="0" * 64,
        status="ok",
        score=1.0,
        checks=[CheckResult("stdout_exact", False, True, "mismatch")],
    )
    result = GradeResult(
        schema_version="1.0.0",
        task_id="t",
        group_id="g",
        candidate_id="c",
        script_sha256="0" * 64,
        fixture_sha256s={},
        checks=[],
        critical_violations=[],
        fixture_results=[bad],
        aggregate_status="ok",
        task_score=1.0,
    )
    with pytest.raises(Exception):
        validate_grade_result(result)
