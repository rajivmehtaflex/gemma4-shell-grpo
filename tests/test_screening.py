"""Phase 4 screening unit tests (host-safe: no GPU, no grading runs)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from screen_tasks import analyze, group_scores, load_screening, stage_tasks, useful_group  # noqa: E402


def _rec(score, extraction_ok=True, status="ok", truncated=False):
    return {
        "task_score": score,
        "extraction": {"ok": extraction_ok},
        "aggregate_status": status,
        "truncated": truncated,
        "new_tokens": 100,
        "critical_violations": [],
    }


def test_frozen_config_matches_plan():
    cfg = load_screening(REPO / "configs" / "screening.yaml")
    assert cfg["candidates_per_task"] == 8
    assert len(cfg["tasks"]) == 11
    assert len(set(cfg["tasks"])) == 11
    assert cfg["group_seeds"]["screening_1"] != cfg["group_seeds"]["screening_2"]
    th = cfg["thresholds"]
    assert th["min_useful_proportion"] == 0.25
    assert th["min_useful_tasks_both_screenings"] == 3
    assert th["min_families"] == 5
    # PLAN hard rule: final-test tasks are never screened
    from shell_grpo.splits import TASK_TO_SPLIT
    assert all(TASK_TO_SPLIT[t] == "train" for t in cfg["tasks"])


def test_useful_group_rule():
    assert useful_group([_rec(0.0), _rec(1.0), _rec(None), _rec(0.5)])
    assert not useful_group([_rec(0.0)] * 8)          # all-equal zeros
    assert not useful_group([_rec(1.0)] * 8)          # all-equal full passes
    assert not useful_group([_rec(0.7), _rec(None), _rec(None)])  # one distinct reward
    assert not useful_group([])


def test_stage_task_derivation(tmp_path):
    cfg = {"tasks": ["D02", "D03", "D04"]}
    # stage 1 defaults to the frozen list; explicit override wins
    assert stage_tasks(cfg, 1, tmp_path, "") == ["D02", "D03", "D04"]
    assert stage_tasks(cfg, 1, tmp_path, "D03") == ["D03"]
    # stage 2 derives the confirmation set from screening-1 records
    s1 = tmp_path / "screening-1" / "records"
    s1.mkdir(parents=True)
    for i, s in enumerate([0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]):  # useful
        (s1 / f"D02-screen1-{i}.json").write_text(json.dumps(_rec(s)))
    for i in range(8):                                                # all-equal
        (s1 / f"D03-screen1-{i}.json").write_text(json.dumps(_rec(0.0)))
    assert stage_tasks(cfg, 2, tmp_path, "") == ["D02"]
    assert stage_tasks(cfg, 2, tmp_path, "D04") == ["D04"]
    # no screening-1 records -> stage 2 has nothing to derive
    assert stage_tasks(cfg, 2, tmp_path / "empty", "") == []


def _write_stage(out: Path, n: str, tasks_scores: dict[str, list[float]]) -> None:
    d = out / f"screening-{n}"
    (d / "records").mkdir(parents=True, exist_ok=True)
    totals = {"records": 0, "scored": 0, "full_pass": 0, "truncated": 0,
              "infrastructure_error": 0, "useful_tasks": [], "all_equal_tasks": [],
              "mean_score": 0.0, "scoring_coverage": 1.0}
    tasks = {}
    for tid, scores in tasks_scores.items():
        recs = [_rec(s) for s in scores]
        for i, r in enumerate(recs):
            (d / "records" / f"{tid}-screen{n}-{i}.json").write_text(json.dumps(r))
        distinct = sorted(set(scores))
        useful = len(distinct) >= 2
        tasks[tid] = {
            "records": len(recs), "scored": len(scores), "scores": scores,
            "full_pass": sum(1 for s in scores if s == 1.0),
            "partial_progress": 0, "zero": sum(1 for s in scores if s == 0.0),
            "extraction_failures": 0, "truncated": 0, "infrastructure_error": 0,
            "distinct_rewards": distinct, "useful_group": useful,
            "critical_violation_records": 0, "mean_new_tokens": 100,
        }
        totals["records"] += len(recs)
        totals["scored"] += len(scores)
        totals["full_pass"] += tasks[tid]["full_pass"]
        totals["infrastructure_error"] += 0
        if useful:
            totals["useful_tasks"].append(tid)
        if len(distinct) <= 1:
            totals["all_equal_tasks"].append(tid)
    (d / "summary.json").write_text(json.dumps(
        {"stage_seed": 1, "candidates_per_task": 8, "tasks": tasks, "totals": totals}))


def test_analyze_gate_math(tmp_path):
    cfg = load_screening(REPO / "configs" / "screening.yaml")
    frozen = cfg["tasks"]
    # D02/S02 (copy-recursive) useful in both; D03 useful only in screening 1;
    # V01 full-pass-everywhere in screening 1 (easy-covered family); rest zeros.
    s1_scores = {t: ([1.0, 0.0] + [0.0] * 6) if t in ("D02", "S02", "D03")
                 else ([1.0] * 8 if t == "V01" else [0.0] * 8) for t in frozen}
    s2_scores = {t: ([1.0, 0.0] + [0.0] * 6) if t in ("D02", "S02")
                 else ([0.0] * 8) for t in frozen}
    _write_stage(tmp_path, "1", s1_scores)
    _write_stage(tmp_path, "2", s2_scores)

    analyze(tmp_path, cfg)
    a = json.loads((tmp_path / "analysis.json").read_text())
    # V01 is all full passes: NOT useful (all-equal rule) -> easy-covered family
    assert a["useful_screening_1"] == ["D02", "D03", "S02"]
    assert a["useful_in_both"] == ["D02", "S02"]
    assert a["families_in_both"] == ["copy-recursive"]
    th = a["thresholds"]
    assert th["useful_tasks_both"] == 2
    assert th["useful_proportion_met"] is False      # 2/11 < 0.25 and < 3 tasks
    assert th["families_met"] is False               # 1 < 5
    assert th["families_reported"]["copy-recursive"] == "useful"
    assert th["families_reported"]["copy-flat"] == "easy-covered"     # V01, all full passes
    assert th["families_reported"]["move-select"] == "hard-reserve"
    assert a["gate"]["informative_proportion_and_families"] is False
    assert a["gate"]["scoring_coverage_complete"] is True
    assert a["gate"]["both_screenings_complete"] is True
