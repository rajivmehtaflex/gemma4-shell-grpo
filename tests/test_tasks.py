"""Registry invariants across all 20 diagnostics."""

import hashlib
from pathlib import Path

import pytest

from shell_grpo.contracts import validate_grade_result
from shell_grpo.tasks import all_tasks, get_task

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "data" / "examples" / "scripts"

EXPECTED_TASKS = [
    "D01", "D02", "D03", "D04", "D05",
    "S01", "S02", "S03", "S04", "S05",
    "S06", "S07", "S08", "S09", "S10",
    "T1a", "T1b", "T2a", "T2b", "T3a",
    "T3b", "T4a", "T4b", "T5a", "T5b",
    "T6a", "T6b",
    "V01", "V02", "V03", "V04", "V05",
]


def test_expected_tasks_registered():
    assert [t.task_id for t in all_tasks()] == EXPECTED_TASKS


def test_each_task_has_progress_fixture_and_valid_weights():
    for task in all_tasks():
        assert task.progress_ids(), f"{task.task_id} lacks a progress fixture"
        total = sum(task.weights().values())
        assert abs(total - 1.0) < 1e-6, f"{task.task_id} weights sum to {total}"
        ids = task.fixture_ids()
        assert len(ids) == len(set(ids)), f"{task.task_id} has duplicate fixture ids"
        for case in task.fixtures:
            assert callable(case.build), f"{task.task_id}/{case.fixture_id}: build not callable"


def test_every_fixture_builds_deterministically(tmp_path):
    """Builders are pure Python: construct every fixture twice and compare.

    This exercises each builder on the dev host (no candidate execution)
    and pins down that the same seed reproduces the same tree hash.
    """
    from shell_grpo.contracts import derive_fixture_seeds
    from shell_grpo.fixtures import build_instance, remove_tree

    for task in all_tasks():
        seeds = derive_fixture_seeds(task.task_id, 7, task.fixture_ids())
        for case in task.fixtures:
            a = build_instance(case.fixture_id, seeds[case.fixture_id], tmp_path / "a", case.build)
            b = build_instance(case.fixture_id, seeds[case.fixture_id], tmp_path / "b", case.build)
            assert a.fixture_sha256 == b.fixture_sha256, f"{task.task_id}/{case.fixture_id}"
            assert isinstance(a.truth.argv, list)
            if not a.truth.expects_failure and case.verify is None:
                assert a.truth.expected_stdout is not None, (
                    f"{task.task_id}/{case.fixture_id}: simple fixture lacks expected stdout"
                )
            remove_tree(a.root)
            remove_tree(b.root)


def test_unique_fixture_ids_across_tasks():
    seen = set()
    for task in all_tasks():
        for fixture_id in task.fixture_ids():
            assert fixture_id not in seen, f"fixture id reused: {fixture_id}"
            seen.add(fixture_id)


def test_task_records_validate():
    for task in all_tasks():
        record = task.record()
        expected_split = "held_out_test" if task.task_id.startswith("T") else "development_pool"
        assert record.split == expected_split, task.task_id
        assert record.provenance["source"] == "authored"
        assert len(record.fixtures_declared) == len(task.fixtures)
    held_out_families = {t.family_id for t in all_tasks() if t.task_id.startswith("T")}
    dev_families = {t.family_id for t in all_tasks() if not t.task_id.startswith("T")}
    assert not (held_out_families & dev_families), "family leakage between pools"


def test_every_declared_script_exists_and_passes_bash_n():
    import subprocess

    for task in all_tasks():
        names = [task.reference, task.alternate] + [w.filename for w in task.wrongs]
        for name in names:
            path = SCRIPTS / task.task_id / name
            assert path.is_file(), f"missing script {path}"
            proc = subprocess.run(["bash", "-n", str(path)], capture_output=True)
            assert proc.returncode == 0, f"bash -n failed for {path}: {proc.stderr}"


def test_families_cover_three_initial_families():
    families = {t.family_id for t in all_tasks()}
    assert "file-select-count" in families
    assert "copy-recursive" in families
    assert "text-aggregate" in families
    assert "repair-copy" in families
    assert "repair-count" in families


def test_get_task_unknown_raises():
    with pytest.raises(KeyError):
        get_task("ZZZ")
