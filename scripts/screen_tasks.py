#!/usr/bin/env python3
"""Phase 4 screening driver: difficulty screening of the TRAIN pool with the
untouched policy (GPU host).

Stage 1: every frozen screening task x 8 candidates, one shared group seed
         (candidates share fixture seeds, receive fresh state).
Stage 2: the confirmation rule's task set (useful in stage 1) resampled under
         a second independent group seed with fresh generations.
Analyze: joint metrics and frozen-threshold gate booleans into analysis.json.

Records and raw completions are resume-safe: an existing record file for the
same (task, candidate) is kept, so runtime recycles never duplicate or lose
completed work.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def load_screening(path: Path) -> dict:
    import yaml

    return yaml.safe_load(Path(path).read_text())["screening"]


def group_scores(records: list[dict]) -> list[float]:
    return [r["task_score"] for r in records if r.get("task_score") is not None]


def useful_group(records: list[dict]) -> bool:
    """Frozen rule: >=2 distinct non-null functional rewards in the group."""
    return len(set(group_scores(records))) >= 2


def _task_records(records_dir: Path, task_id: str) -> list[dict]:
    return [json.loads(p.read_text())
            for p in sorted(Path(records_dir).glob(f"{task_id}-screen*.json"))]


def stage_tasks(cfg: dict, stage: int, out_dir: Path, override: str) -> list[str]:
    frozen = list(cfg["tasks"])
    if override:
        return override.split(",")
    if stage == 1:
        return frozen
    # stage 2 default: the confirmation rule's set, derived from stage-1 records
    s1_records = out_dir / "screening-1" / "records"
    if not s1_records.is_dir():
        return []
    return sorted(tid for tid in frozen if useful_group(_task_records(s1_records, tid)))


def run_stage(
    stage: int,
    cfg: dict,
    out_dir: Path,
    model_cfg_path: Path,
    override_tasks: str,
    revision: str | None,
) -> int:
    from shell_grpo.evaluate import evaluate_completion
    from shell_grpo.generate import ModelConfig, generate_one, load_model
    from shell_grpo.manifests import RunManifest, config_hashes, git_head
    from shell_grpo.runner import make_runner
    from shell_grpo.splits import TASK_TO_SPLIT
    from shell_grpo.tasks import get_task

    seed = int(cfg["group_seeds"][f"screening_{stage}"])
    n_cand = int(cfg["candidates_per_task"])
    max_new = int(cfg["max_new_tokens"])

    model_cfg = ModelConfig.load(model_cfg_path)
    model_cfg.max_new_tokens = max_new
    if revision:
        model_cfg.revision = revision

    stage_dir = out_dir / f"screening-{stage}"
    records_dir = stage_dir / "records"
    raw_dir = stage_dir / "raw-completions"
    records_dir.mkdir(parents=True, exist_ok=True)

    runner = make_runner(REPO / cfg["grading"]["runner_config"])

    wanted = stage_tasks(cfg, stage, out_dir, override_tasks)
    if not wanted:
        print("no tasks to screen (stage 2 requires screening-1 records or --tasks)", flush=True)
        return 1
    for tid in wanted:
        if TASK_TO_SPLIT.get(tid) != "train":
            print(f"REFUSING {tid}: screening is restricted to the train pool", flush=True)
            return 1

    model, tokenizer = load_model(model_cfg)

    manifest = RunManifest(
        run_id=f"P4-screening-{stage}",
        phase=4,
        parent_run="P2-20261022B",
        git_head=git_head(REPO),
        config_files=config_hashes([model_cfg_path, REPO / "configs" / "screening.yaml"]),
        model={"repo_id": model_cfg.repo_id, "revision": model_cfg.revision,
               "quantization": model_cfg.quantization},
        environment={},
        image_digest=runner.image_digest,
        seeds={"screening_seed": seed, "candidates_per_task": n_cand,
               "max_new_tokens": max_new, "stage": stage, "tasks": wanted},
    )
    manifest.write(stage_dir / "manifest.json")

    for task_id in wanted:
        task = get_task(task_id)
        for cand in range(n_cand):
            rec_path = records_dir / f"{task_id}-screen{stage}-{cand}.json"
            if rec_path.exists():
                print(f"[{task_id} #{cand}] resumed score="
                      f"{json.loads(rec_path.read_text()).get('task_score')}", flush=True)
                continue
            generation = generate_one(model, tokenizer, task.task_id, task.prompt, model_cfg)
            record = evaluate_completion(
                task, generation, runner,
                candidate_id=f"screen{stage}-{cand}",
                group_seed=seed,  # shared by the whole group; fresh state per run
                raw_dir=raw_dir,
            )
            rec_path.write_text(json.dumps(record.to_dict(), indent=2) + "\n")
            print(f"[{task_id} #{cand}] score={record.task_score} "
                  f"status={record.aggregate_status} trunc={record.truncated}", flush=True)

    summarize_stage(stage_dir, records_dir, wanted, n_cand, seed)
    return 0


def summarize_stage(stage_dir: Path, records_dir: Path, wanted: list[str], n_cand: int, seed: int) -> None:
    by_task: dict[str, list[dict]] = {tid: _task_records(records_dir, tid) for tid in wanted}
    summary: dict = {"stage_seed": seed, "candidates_per_task": n_cand, "tasks": {}}
    all_scores: list[float] = []
    for tid in wanted:
        recs = by_task[tid]
        scores = group_scores(recs)
        all_scores += scores
        summary["tasks"][tid] = {
            "records": len(recs),
            "scored": len(scores),
            "scores": scores,
            "full_pass": sum(1 for s in scores if s == 1.0),
            "partial_progress": sum(1 for s in scores if s is not None and 0.0 < s < 1.0),
            "zero": sum(1 for s in scores if s == 0.0),
            "extraction_failures": sum(1 for r in recs if not r["extraction"]["ok"]),
            "truncated": sum(1 for r in recs if r.get("truncated")),
            "infrastructure_error": sum(1 for r in recs if r.get("aggregate_status") == "infrastructure_error"),
            "distinct_rewards": sorted(set(scores)),
            "useful_group": useful_group(recs),
            "critical_violation_records": sum(1 for r in recs if r.get("critical_violations")),
            "mean_new_tokens": (sum(r.get("new_tokens", 0) for r in recs) / len(recs)) if recs else None,
        }
    total_records = sum(v["records"] for v in summary["tasks"].values())
    total_infra = sum(v["infrastructure_error"] for v in summary["tasks"].values())
    summary["totals"] = {
        "records": total_records,
        "scored": sum(v["scored"] for v in summary["tasks"].values()),
        "full_pass": sum(v["full_pass"] for v in summary["tasks"].values()),
        "truncated": sum(v["truncated"] for v in summary["tasks"].values()),
        "infrastructure_error": total_infra,
        "useful_tasks": sorted(t for t, v in summary["tasks"].items() if v["useful_group"]),
        "all_equal_tasks": sorted(
            t for t, v in summary["tasks"].items()
            if v["records"] == n_cand and len(v["distinct_rewards"]) <= 1
        ),
        "mean_score": (sum(all_scores) / len(all_scores)) if all_scores else None,
        "scoring_coverage": (1.0 - total_infra / total_records) if total_records else None,
    }
    (stage_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["totals"], indent=2), flush=True)


def analyze(out_dir: Path, cfg: dict) -> int:
    from shell_grpo.splits import component_for
    from shell_grpo.tasks import get_task

    s1 = json.loads((out_dir / "screening-1" / "summary.json").read_text())
    s2_path = out_dir / "screening-2" / "summary.json"
    s2 = json.loads(s2_path.read_text()) if s2_path.exists() else None

    th = cfg["thresholds"]
    useful1 = set(s1["totals"]["useful_tasks"])
    useful2 = set(s2["totals"]["useful_tasks"]) if s2 else set()
    both = sorted(useful1 & useful2) if s2 else []
    families_both = sorted({get_task(t).family_id for t in both})

    family_state: dict[str, dict] = {}
    for tid in cfg["tasks"]:
        fam = get_task(tid).family_id
        entry = family_state.setdefault(fam, {"tasks": [], "state": "hard-reserve"})
        entry["tasks"].append(tid)
        if tid in both:
            entry["state"] = "useful"
    for fam, entry in family_state.items():
        if entry["state"] == "useful":
            continue
        had_full = any(
            s1["tasks"][t]["full_pass"] > 0 or (s2 and s2["tasks"][t]["full_pass"] > 0)
            for t in entry["tasks"]
        )
        entry["state"] = "easy-covered" if had_full else "hard-reserve"

    thresholds_met = {
        "useful_tasks_both": len(both),
        "min_useful_tasks_both_screenings": th["min_useful_tasks_both_screenings"],
        "useful_proportion": len(both) / len(cfg["tasks"]),
        "useful_proportion_met": (len(both) / len(cfg["tasks"])) >= th["min_useful_proportion"],
        "families_both": len(families_both),
        "min_families": th["min_families"],
        "families_met": len(families_both) >= th["min_families"],
        "families_reported": {f: v["state"] for f, v in sorted(family_state.items())},
        "scoring_coverage_1": s1["totals"]["scoring_coverage"],
        "scoring_coverage_2": s2["totals"]["scoring_coverage"] if s2 else None,
        "infrastructure_errors_1": s1["totals"]["infrastructure_error"],
        "infrastructure_errors_2": s2["totals"]["infrastructure_error"] if s2 else None,
    }

    analysis = {
        "useful_screening_1": sorted(useful1),
        "useful_screening_2": sorted(useful2) if s2 else None,
        "useful_in_both": both,
        "families_in_both": families_both,
        "per_task": {
            "task": [], "family": [], "component": [],
            "useful1": [], "useful2": [], "scores1": [], "scores2": [],
        },
        "thresholds": thresholds_met,
        "gate": None,
    }
    for tid in cfg["tasks"]:
        p = analysis["per_task"]
        p["task"].append(tid)
        p["family"].append(get_task(tid).family_id)
        p["component"].append(component_for(tid))
        p["useful1"].append(tid in useful1)
        p["useful2"].append(bool(s2) and tid in useful2)
        p["scores1"].append(s1["tasks"][tid]["scores"])
        p["scores2"].append(s2["tasks"][tid]["scores"] if s2 else None)

    analysis["gate"] = {
        "informative_proportion_and_families": (
            thresholds_met["useful_proportion_met"] and thresholds_met["families_met"]
        ),
        "family_coverage_reported": True,
        "scoring_coverage_complete": (
            s1["totals"]["infrastructure_error"] == 0
            and (s2 is None or s2["totals"]["infrastructure_error"] == 0)
        ),
        "both_screenings_complete": s2 is not None,
    }
    (out_dir / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n")
    print(json.dumps(analysis["thresholds"], indent=2))
    print(json.dumps(analysis["gate"], indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["stage", "analyze"])
    parser.add_argument("--stage", type=int, default=1)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--screening-config", type=Path,
                        default=REPO / "configs" / "screening.yaml")
    parser.add_argument("--model-config", type=Path, default=REPO / "configs" / "model.yaml")
    parser.add_argument("--tasks", default="", help="comma-separated subset override")
    parser.add_argument("--revision", default=None)
    args = parser.parse_args()

    cfg = load_screening(args.screening_config)
    if args.action == "analyze":
        return analyze(args.out_dir, cfg)
    return run_stage(args.stage, cfg, args.out_dir, args.model_config,
                     args.tasks, args.revision)


if __name__ == "__main__":
    raise SystemExit(main())
