"""Phase 6 checkpointing unit tests (host-safe; torch skipped if absent)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from shell_grpo.checkpointing import _sha256, verify_checkpoint  # noqa: E402
from shell_grpo.train import InlineGrader, build_pilot_dataset  # noqa: E402


def test_verify_detects_hash_mismatch_and_missing(tmp_path):
    f = tmp_path / "weights.bin"
    f.write_bytes(b"payload")
    manifest = {"global_step": 4, "files": {"weights.bin": _sha256(f)}, "total_bytes": 7}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    verify_checkpoint(tmp_path)  # ok

    manifest["files"]["weights.bin"] = "0" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    try:
        verify_checkpoint(tmp_path)
        raise AssertionError("expected mismatch to raise")
    except RuntimeError as exc:
        assert "hash mismatch" in str(exc)

    manifest["files"]["ghost.bin"] = "0" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    try:
        verify_checkpoint(tmp_path)
        raise AssertionError("expected missing-file to raise")
    except RuntimeError as exc:
        assert "missing" in str(exc)


def test_pilot_dataset_rows_frozen_semantics():
    class FakeDataset(list):
        @classmethod
        def from_list(cls, rows):
            return cls(rows)

    tasks = ["D02", "S03", "S05", "V01", "W01", "W02", "D04", "V04"]
    ds = build_pilot_dataset(None, tasks, 12, 20261022, dataset_factory=FakeDataset)
    assert len(ds) == 12
    # frozen pool order cycles; seed rotates per row
    assert ds[0]["task_ids"] == "D02" and ds[0]["group_seeds"] == 20261022
    assert ds[7]["task_ids"] == "V04" and ds[7]["group_seeds"] == 20261029
    assert ds[8]["task_ids"] == "D02" and ds[8]["group_seeds"] == 20261030
    assert ds[11]["group_seeds"] == 20261033
    # frozen thinking-template prefix in every prompt
    assert ds[0]["prompt"].startswith("<|turn>system\n<|think|>\n<turn|>\n<|turn>user\n")


def test_inline_grader_delegates(tmp_path):
    class FakeResult:
        task_score = 0.5

    class FakeRunner:
        def __init__(self):
            self.seen = []

        def grade_call(self, task_id, script, seed, candidate_id):
            self.seen.append((task_id, script, seed, candidate_id))
            return FakeResult()

    class Adapter(FakeRunner):
        pass

    # InlineGrader.grade must route through grade_script; use a monkeypatched
    # grade_script to avoid grading infra on the host.
    import shell_grpo.runner as R

    seen = []

    def fake_grade_script(task_id, script, seed, runner, **kw):
        seen.append((task_id, script, seed, kw["candidate_id"]))
        return FakeResult()

    original = R.grade_script
    R.grade_script = fake_grade_script
    try:
        g = InlineGrader(object())
        result = g.grade("D02", "echo hi", 20261022, "train-0")
        assert result.task_score == 0.5
        assert g.calls == 1
        assert seen == [("D02", "echo hi", 20261022, "train-0")]
    finally:
        R.grade_script = original


def test_frozen_pilot_config_stops_and_cadence():
    import yaml

    cfg = yaml.safe_load((REPO / "configs" / "grpo-pilot.yaml").read_text())
    assert cfg["budget"]["max_steps"] == 12
    assert cfg["budget"]["checkpoint_every_steps"] == 4
    assert cfg["grpo"]["num_generations"] == 8
    assert cfg["grpo"]["per_device_train_batch_size"] == 8
    assert len(cfg["dataset"]["accepted_training_pool"]) == 8
    assert len(cfg["evaluation"]["validation_tasks"]) == 9
