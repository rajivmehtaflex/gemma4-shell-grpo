"""Restricted-runner tests. Docker-dependent: run only in the Codespace.

These tests execute reference and wrong scripts inside the grading image —
never on the development host.
"""

import shutil
from pathlib import Path

import pytest

from shell_grpo.contracts import validate_grade_result
from shell_grpo.runner import RestrictedRunner, RunnerConfig, grade_script
from shell_grpo.tasks import get_task

pytestmark = pytest.mark.docker


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _script(task_id: str, name: str) -> bytes:
    return (_repo_root() / "data" / "examples" / "scripts" / task_id / name).read_bytes()


@pytest.fixture(scope="module")
def runner(tmp_path_factory):
    try:
        instance = RestrictedRunner(RunnerConfig())
    except Exception as exc:  # pragma: no cover - no docker on host
        pytest.skip(f"docker unavailable: {exc}")
    return instance


@pytest.fixture(scope="module")
def out_root(tmp_path_factory):
    return tmp_path_factory.mktemp("grade-out")


def test_reference_passes_d01(runner, out_root):
    result = grade_script(
        "D01", _script("D01", "reference.sh"), 1, runner,
        candidate_id="ref", group_id="g", out_dir=out_root / "d01-ref",
    )
    validate_grade_result(result)
    assert result.aggregate_status == "ok"
    assert result.task_score == 1.0
    assert all(f.status == "ok" for f in result.fixture_results)


def test_reference_passes_d04(runner, out_root):
    result = grade_script(
        "D04", _script("D04", "reference.sh"), 2, runner,
        candidate_id="ref", group_id="g", out_dir=out_root / "d04-ref",
    )
    validate_grade_result(result)
    assert result.task_score == 1.0


def test_reference_passes_s07_with_parse_equivalence(runner, out_root):
    result = grade_script(
        "S07", _script("S07", "alternate.sh"), 3, runner,
        candidate_id="alt", group_id="g", out_dir=out_root / "s07-alt",
    )
    validate_grade_result(result)
    assert result.task_score == 1.0


def test_hardcoded_zero_answer_scores_zero_on_d01(runner, out_root):
    result = grade_script(
        "D01", _script("D01", "wrong-hardcode.sh"), 1, runner,
        candidate_id="hard", group_id="g", out_dir=out_root / "d01-hard",
    )
    validate_grade_result(result)
    assert result.task_score == 0.0


def test_empty_script_is_invalid(runner, out_root):
    result = grade_script(
        "D01", b"", 1, runner,
        candidate_id="empty", group_id="g", out_dir=out_root / "d01-empty",
    )
    assert result.aggregate_status == "invalid_script"
    assert result.task_score == 0.0


def test_syntax_error_is_invalid_script(runner, out_root):
    result = grade_script(
        "D01", b"#!/bin/bash\nthen fi do done\n", 1, runner,
        candidate_id="bad", group_id="g", out_dir=out_root / "d01-bad",
    )
    assert result.aggregate_status == "invalid_script"


def test_timeout_is_resource_limit(runner, out_root):
    script = b"#!/bin/bash\nsleep 60\n"
    config = RunnerConfig(time_limit_seconds=3)
    result = grade_script(
        "D01", script, 1, RestrictedRunner(config),
        candidate_id="slow", group_id="g", out_dir=out_root / "d01-slow",
    )
    validate_grade_result(result)
    assert result.aggregate_status == "resource_limit"
    assert result.task_score == 0.0


def test_fork_bomb_is_resource_limit(runner, out_root):
    script = b"#!/bin/bash\nwhile true; do bash -c ': & bash -c \": & \"; done\n"
    config = RunnerConfig(time_limit_seconds=6, pids_limit="32")
    result = grade_script(
        "D01", script, 1, RestrictedRunner(config),
        candidate_id="fork", group_id="g", out_dir=out_root / "d01-fork",
    )
    validate_grade_result(result)
    assert result.aggregate_status in ("resource_limit", "runtime_error")
    assert result.task_score == 0.0


def test_mutation_is_critical_on_d03(runner, out_root):
    script = (
        b"#!/bin/bash\n"
        b'awk -F\'\\t\' \'{ sum[$1] += $2 } END { for (k in sum) print k "\\t" sum[k] }\' "$1" '
        b"| LC_ALL=C sort -t \"$(printf '\\t')\" -k1,1\n"
        b'echo tampered >> "$1"\n'
    )
    result = grade_script(
        "D03", script, 1, runner,
        candidate_id="mutate", group_id="g", out_dir=out_root / "d03-mutate",
    )
    validate_grade_result(result)
    assert result.task_score == 0.0
    assert any("input_mutated" in v for v in result.critical_violations)


def test_repeatability_same_seed_same_result(runner, out_root):
    a = grade_script(
        "D01", _script("D01", "alternate.sh"), 99, runner,
        candidate_id="rep", group_id="g", out_dir=out_root / "d01-rep-a",
    )
    b = grade_script(
        "D01", _script("D01", "alternate.sh"), 99, runner,
        candidate_id="rep", group_id="g", out_dir=out_root / "d01-rep-b",
    )
    a_dict, b_dict = a.to_dict(), b.to_dict()
    for d in (a_dict, b_dict):
        d.pop("artifacts")
        for fr in d["fixture_results"]:
            fr.pop("duration_ms")
            fr.pop("artifacts")
    assert a_dict == b_dict


def test_group_seed_changes_fixtures(runner, out_root):
    a = grade_script(
        "D01", _script("D01", "reference.sh"), 1, runner,
        candidate_id="s1", group_id="ga", out_dir=out_root / "d01-seed1",
    )
    b = grade_script(
        "D01", _script("D01", "reference.sh"), 2, runner,
        candidate_id="s2", group_id="gb", out_dir=out_root / "d01-seed2",
    )
    assert a.task_score == 1.0
    assert b.task_score == 1.0
    seeds_a = {f.fixture_id: f.seed for f in a.fixture_results}
    seeds_b = {f.fixture_id: f.seed for f in b.fixture_results}
    assert seeds_a != seeds_b
