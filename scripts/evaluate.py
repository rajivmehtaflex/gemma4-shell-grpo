#!/usr/bin/env python3
"""Baseline evaluation driver (Phase 2, GPU host).

Loads the untouched checkpoint, generates N samples per diagnostic under the
frozen settings, extracts and grades each completion through the Phase 1
grader, and writes per-candidate evaluation records plus a summary. Raw
completions are preserved privately; records reference them by hash.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def main() -> int:
    import yaml

    from shell_grpo.evaluate import evaluate_completion, summarize_pass_rate
    from shell_grpo.generate import ModelConfig, generate_one, load_model
    from shell_grpo.manifests import RunManifest, config_hashes, git_head
    from shell_grpo.runner import make_runner
    from shell_grpo.tasks import all_tasks, get_task

    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, default=REPO / "configs" / "model.yaml")
    parser.add_argument("--baseline-config", type=Path, default=REPO / "configs" / "baseline.yaml")
    parser.add_argument("--tasks", default="", help="comma-separated subset (default: all)")
    parser.add_argument("--samples", type=int, default=None, help="override samples_per_task")
    parser.add_argument("--revision", default=None, help="override the pinned revision")
    args = parser.parse_args()

    baseline = yaml.safe_load(args.baseline_config.read_text())["baseline"]
    model_cfg = ModelConfig.load(args.model_config)
    if args.revision:
        model_cfg.revision = args.revision
    if baseline.get("max_new_tokens"):
        model_cfg.max_new_tokens = int(baseline["max_new_tokens"])
    samples = args.samples or int(baseline["samples_per_task"])
    seed_base = int(baseline["group_seed_base"])

    out = args.out_dir
    (out / "records").mkdir(parents=True, exist_ok=True)
    raw_dir = out / "raw-completions"

    runner = make_runner(REPO / baseline["grading"]["runner_config"])
    model, tokenizer = load_model(model_cfg)

    wanted = args.tasks.split(",") if args.tasks else [t.task_id for t in all_tasks()]

    manifest = RunManifest(
        run_id=f"P2-baseline-{out.name}",
        phase=2,
        parent_run=None,
        git_head=git_head(REPO),
        config_files=config_hashes([args.model_config, args.baseline_config]),
        model={"repo_id": model_cfg.repo_id, "revision": model_cfg.revision,
               "quantization": model_cfg.quantization},
        environment={},
        image_digest=runner.image_digest,  # engine identity string on namespace hosts
        seeds={"group_seed_base": seed_base, "samples_per_task": samples},
    )
    manifest.write(out / "manifest.json")

    support_map = {
        k: {name: (REPO / "data" / "examples" / "scripts" / k / name).read_bytes()
            for name in names}
        for k, names in (baseline.get("support_files") or {}).items()
    }

    records = []
    records_dir = out / "records"
    for task_id in wanted:
        task = get_task(task_id)
        for sample in range(samples):
            group_seed = seed_base + sample
            rec_path = records_dir / f"{task_id}-{sample}.json"
            if rec_path.exists():
                # resume mode: a prior activation already banked this record
                import types

                data = json.loads(rec_path.read_text())
                records.append(types.SimpleNamespace(**data))
                print(f"[{task_id} #{sample}] resumed score={data.get('task_score')}", flush=True)
                continue
            generation = generate_one(model, tokenizer, task.task_id, task.prompt, model_cfg)
            record = evaluate_completion(
                task, generation, runner,
                candidate_id=f"baseline-{sample}",
                group_seed=group_seed,
                raw_dir=raw_dir,
                support_files=support_map.get(task_id),
            )
            (records_dir / f"{task_id}-{sample}.json").write_text(
                json.dumps(record.to_dict(), indent=2) + "\n"
            )
            records.append(record)
            print(f"[{task_id} #{sample}] score={record.task_score} "
                  f"status={record.aggregate_status}", flush=True)

    summary = summarize_pass_rate(records)
    summary["model"] = {"repo_id": model_cfg.repo_id, "revision": model_cfg.revision}
    summary["samples_per_task"] = samples
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "by_task_mean"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
