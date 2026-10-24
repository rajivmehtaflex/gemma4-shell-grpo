"""Split integrity: whole components, no leakage, honest counts."""

import pytest

from shell_grpo.splits import (
    COMPONENTS,
    SPLITS,
    all_components,
    check_integrity,
    component_for,
    split_counts,
    split_for,
)
from shell_grpo.tasks import all_tasks

EXPECTED_COUNTS = {"train": 13, "validation": 9, "test": 12}


def test_every_registered_task_has_exactly_one_component():
    tasks = all_tasks()
    problems = check_integrity([t.task_id for t in tasks])
    assert problems == []
    assert len(tasks) == 34
    for task in tasks:
        comp = component_for(task.task_id)
        assert comp in COMPONENTS
        assert split_for(task.task_id) in SPLITS


def test_components_are_whole_and_single_split():
    for comp, spec in all_components().items():
        assert spec["split"] in SPLITS
        # all tasks of one family land in the same split (whole-component rule)
        for family in spec["families"]:
            same_family = [
                s for other in COMPONENTS.values() if family in other["families"]
                for s in [other["split"]]
            ]
            assert set(same_family) == {spec["split"]}, family


def test_diagnostics_never_in_test():
    for comp, spec in COMPONENTS.items():
        if spec["origin"] == "dev-diagnostic":
            assert spec["split"] != "test", comp


def test_held_out_families_are_disjoint_from_development_families():
    test_families = {
        f for spec in COMPONENTS.values() if spec["split"] == "test"
        for f in spec["families"]
    }
    dev_families = {
        f for spec in COMPONENTS.values() if spec["split"] != "test"
        for f in spec["families"]
    }
    assert not (test_families & dev_families)


def test_actual_counts_reported_not_forced():
    tasks = [t.task_id for t in all_tasks()]
    counts = split_counts(tasks)
    assert counts == EXPECTED_COUNTS
    # 60/20/20 is aspirational; components are never split to meet it
    total = sum(counts.values())
    shares = [counts[s] / total for s in SPLITS]
    assert all(0.2 < s < 0.45 for s in shares), shares


def test_validation_holds_the_partial_credit_components():
    # Checkpoint-selection signal: the components where the baseline earns
    # partial reward (D01, D05 families) sit in validation.
    assert split_for("D01") == "validation"
    assert split_for("D05") == "validation"
    assert split_for("S06") == "validation"  # same component as D05


def test_task_records_carry_their_split_after_builder(tmp_path):
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"))
    import importlib

    builder = importlib.import_module("build_dataset")
    out = builder.build_release("test-release", 1, all_tasks())
    lines = (out / "bank.jsonl").read_text().splitlines()
    records = [json.loads(line) for line in lines]
    assert len(records) == 34
    for record in records:
        assert record["split"] == split_for(record["task_id"])
        assert record["component"] == component_for(record["task_id"])
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["split_task_counts"] == EXPECTED_COUNTS
    assert len(manifest["bank_sha256"]) == 64


import json  # noqa: E402  (used above; placed late to keep imports near use)
