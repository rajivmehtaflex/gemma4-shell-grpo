"""Contract tests: schema round-trips, invalid records, precedence, seeds."""

import pytest

from shell_grpo.contracts import (
    SCHEMA_VERSION,
    CheckResult,
    ContractError,
    FixtureResult,
    GradeResult,
    TaskRecord,
    aggregate_status,
    derive_fixture_seeds,
    validate_grade_result,
)


def test_aggregate_precedence_order():
    assert aggregate_status(["ok", "runtime_error"]) == "runtime_error"
    assert aggregate_status(["ok", "infrastructure_error"]) == "infrastructure_error"
    assert aggregate_status(["resource_limit", "runtime_error"]) == "resource_limit"
    assert aggregate_status(["ok", "ok"]) == "ok"
    assert aggregate_status(["invalid_script"]) == "invalid_script"


def test_aggregate_empty_is_error():
    with pytest.raises(ContractError):
        aggregate_status([])


def test_task_record_round_trip():
    record = TaskRecord(
        task_id="D01",
        family_id="file-select-count",
        source_cluster_id="d01-cluster",
        prompt=[{"role": "user", "content": "count files"}],
        fixture_id="D01-fixtures-v1",
        verifier_id="D01-verifier-v1",
        invocation="solution.sh <directory>",
        split="development_pool",
        provenance={"source": "authored"},
        fixtures_declared=[{"fixture_id": "d01-main", "progress": True, "weight": 0.5}],
    )
    data = record.to_dict()
    restored = TaskRecord.from_dict(data)
    assert restored.to_dict() == data
    assert restored.schema_version == SCHEMA_VERSION


def test_task_record_rejects_bad_schema_version():
    with pytest.raises(ContractError):
        TaskRecord(
            task_id="X",
            family_id="f",
            source_cluster_id="s",
            prompt=[{"role": "user", "content": "p"}],
            fixture_id="fx",
            verifier_id="vx",
            invocation="i",
            split="development_pool",
            provenance={},
            schema_version="9.9.9",
        )


def test_task_record_rejects_empty_prompt():
    with pytest.raises(ContractError):
        TaskRecord(
            task_id="X",
            family_id="f",
            source_cluster_id="s",
            prompt=[],
            fixture_id="fx",
            verifier_id="vx",
            invocation="i",
            split="development_pool",
            provenance={},
        )


def test_grade_result_rejects_mismatched_aggregate():
    fixture = FixtureResult(
        fixture_id="a", seed=1, fixture_sha256="0" * 64, status="ok", score=1.0
    )
    with pytest.raises(ContractError):
        GradeResult(
            schema_version=SCHEMA_VERSION,
            task_id="T",
            group_id="g",
            candidate_id="c",
            script_sha256="0" * 64,
            fixture_sha256s={},
            checks=[],
            critical_violations=[],
            fixture_results=[fixture],
            aggregate_status="infrastructure_error",
            task_score=1.0,
        )


def test_grade_result_rejects_score_with_unresolved_infra():
    fixture = FixtureResult(
        fixture_id="a", seed=1, fixture_sha256="0" * 64,
        status="infrastructure_error", score=None,
    )
    with pytest.raises(ContractError):
        GradeResult(
            schema_version=SCHEMA_VERSION,
            task_id="T",
            group_id="g",
            candidate_id="c",
            script_sha256="0" * 64,
            fixture_sha256s={},
            checks=[],
            critical_violations=[],
            fixture_results=[fixture],
            aggregate_status="infrastructure_error",
            task_score=0.5,
        )


def test_fixture_result_rejects_scored_infrastructure_error():
    with pytest.raises(ContractError):
        FixtureResult(
            fixture_id="a", seed=1, fixture_sha256="0" * 64,
            status="infrastructure_error", score=0.5,
        )


def test_fixture_result_rejects_unknown_status():
    with pytest.raises(ContractError):
        FixtureResult(
            fixture_id="a", seed=1, fixture_sha256="0" * 64, status="passed", score=1.0
        )


def test_grade_result_round_trip_preserves_everything():
    result = GradeResult(
        schema_version=SCHEMA_VERSION,
        task_id="D03",
        group_id="g1",
        candidate_id="ref",
        script_sha256="a" * 64,
        fixture_sha256s={"d03-main": "b" * 64},
        checks=[CheckResult("d03-main:stdout_exact", True, True, "match")],
        critical_violations=[],
        fixture_results=[
            FixtureResult(
                fixture_id="d03-main", seed=42, fixture_sha256="b" * 64,
                status="ok", score=1.0,
                checks=[CheckResult("stdout_exact", True, True, "match")],
                exit_code=0, duration_ms=15,
            )
        ],
        aggregate_status="ok",
        task_score=1.0,
    )
    restored = GradeResult.from_dict(result.to_dict())
    assert restored.to_dict() == result.to_dict()
    validate_grade_result(restored)


def test_derive_fixture_seeds_deterministic_and_group_sensitive():
    a = derive_fixture_seeds("D01", 7, ["f1", "f2"])
    b = derive_fixture_seeds("D01", 7, ["f1", "f2"])
    c = derive_fixture_seeds("D01", 8, ["f1", "f2"])
    d = derive_fixture_seeds("D02", 7, ["f1", "f2"])
    assert a == b
    assert a != c
    assert a["f1"] != d["f1"]
    assert a["f1"] != a["f2"]
