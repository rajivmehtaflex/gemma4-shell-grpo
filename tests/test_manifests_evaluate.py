"""Manifest and evaluation-record wiring tests (host-safe, no torch/docker)."""

import json

from shell_grpo.evaluate import EvaluationRecord, extract_script, summarize_pass_rate
from shell_grpo.manifests import RunManifest, config_hashes, sha256_file


def test_config_hashes_are_content_bound(tmp_path):
    a = tmp_path / "a.yaml"
    a.write_text("x: 1\n")
    b = tmp_path / "b.yaml"
    b.write_text("y: 2\n")
    hashes = config_hashes([a, b, tmp_path / "missing.yaml"])
    assert set(hashes) == {str(a), str(b)}
    first = config_hashes([a])
    a.write_text("x: 2\n")
    assert config_hashes([a]) != first


def test_manifest_round_trip(tmp_path):
    manifest = RunManifest(
        run_id="P2-test",
        phase=2,
        parent_run=None,
        git_head="0" * 40,
        config_files={"configs/model.yaml": "a" * 64},
        model={"repo_id": "unsloth/gemma-4-E4B-it", "revision": "abc"},
        environment={"torch": "2.9.0"},
        image_digest="sha256:2a1fc68e",
        seeds={"group_seed_base": 20261022},
        hardware={"gpu_name": "NVIDIA L4"},
    )
    path = manifest.write(tmp_path / "manifest.json")
    loaded = json.loads(path.read_text())
    assert loaded["run_id"] == "P2-test"
    assert loaded["model"]["revision"] == "abc"
    assert loaded["hardware"]["gpu_name"] == "NVIDIA L4"


def test_sha256_file_stable(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"payload")
    assert len(sha256_file(p)) == 64


def _record(task_id, score, status, extraction_ok=True, criticals=(), truncated=False):
    script = "#!/bin/bash\necho 1\n" if extraction_ok else None
    return EvaluationRecord(
        task_id=task_id,
        candidate_id="c",
        model={"repo_id": "r", "revision": "v"},
        generation_settings={},
        prompt_sha256="0" * 64,
        raw_completion_ref="/tmp/x.txt",
        completion_sha256="1" * 64,
        extraction={"ok": extraction_ok, "reason": "" if extraction_ok else "none", "n_blocks": 1},
        script=script,
        script_sha256="2" * 64 if script else None,
        grade_result=None,
        task_score=score,
        aggregate_status=status,
        critical_violations=list(criticals),
        truncated=truncated,
        new_tokens=42,
        generation_ms=100,
    )


def test_summarize_pass_rate_counts_full_passes_and_failures():
    records = [
        _record("D01", 1.0, "ok"),
        _record("D01", 0.0, "ok"),
        _record("D02", 0.5, "ok"),
        _record("D03", None, "infrastructure_error"),
        _record("D04", 0.0, "ok", extraction_ok=False),
        _record("D05", 0.0, "ok", criticals=("input_mutated: x",), truncated=True),
    ]
    summary = summarize_pass_rate(records)
    assert summary["records"] == 6
    assert summary["full_pass"] == 1
    assert summary["full_pass_rate"] == pytest_approx(1 / 6)
    assert summary["unscorable"] == 1
    assert summary["extraction_failures"] == 1
    assert summary["critical_violation_records"] == 1
    assert summary["truncated"] == 1


def pytest_approx(value):
    import pytest

    return pytest.approx(value)


def test_extraction_result_hash_in_dict():
    result = extract_script("```bash\necho 1\n```")
    assert result.to_dict()["script_sha256"] is not None
    assert len(result.to_dict()["script_sha256"]) == 64
