# Phase 4 screening report — training-difficulty screening with the untouched policy

Date: 2026-10-23/24 · Frozen config: `configs/screening.yaml` (committed pre-sampling at `1e83fdd`) · Code at screening time: `09cdd8b` (stage 1), `63ff97d` (stage 2, split-pipeline generation) · Model: `unsloth/gemma-4-E4B-it@4e22d7e5`, thinking template, temp 1.0 / top_p 0.95 / top_k 64, max_new_tokens 2048

## What ran

- **Screening 1** (seed 410001): all 11 train-pool tasks × 8 candidates = **88 generations, graded inline on Modal L4** (gVisor sandbox; namespace grading engine re-proved on that host first: D01/S07/D02/S02 references + no-op all green). Runtime `gemma4-p4`, stopped after completion; ~$9 of the $12 credit consumed.
- **Screening 2** (seed 410002): the confirmation round on the 5 tasks useful in screening 1 (D02, S03, S05, S08, V01) × 8 fresh candidates = **40 generations on RunPod A40** (~$2 cash). This host blocks user namespaces and DinD, so Phase 4 introduced the **split pipeline** (`screen_tasks.py --no-grade` + `grade` action, `f5344b3`): raw completions + extracted scripts recorded on the GPU host, grading performed on the Codespace's Docker engine (the original 241/241 Phase 1 contract). Both legs hash-verified end to end.
- **Scoring coverage: 1.0 in both screenings — every attempted candidate has a scored outcome, zero infrastructure errors, nothing halted.** (Grader repairs made this honest: `42f1e8d` instance-tree chown, `e1e6505`/`09cdd8b` marker-based engine-failure classification; two stage-1 records regraded with provenance fields.)

## Screening metrics

| Metric | Screening 1 (88) | Screening 2 (40) |
|---|---|---|
| Full passes (score 1.0) | 17 | 10 |
| Mean task score (scored) | 0.324 | 0.433 |
| Extraction failures | 25 (V03: 8/8, V04: 4/8) | 12 (S05: 4, S08: 3) |
| Truncated at 2048 | 7 | 6 (S05: 5) |
| Critical-violation records | 10 | 6 |
| Infrastructure errors | 0 | 0 |

All-equal groups (screening 1): D03 all-zero, D04 all-perfect, S02 all-zero, S04 all-zero, V03 no scored records — listed and inspected, not assumed fixable. D04/V04 are already solved (easy-covered, keep for coverage); D03/S02/S04 are zero-progress (hard reserve); **V03 is a full extraction failure (16/16 candidates across both stages produced no extractable block)** — flagged as a prompt/contract interaction to re-author, not a difficulty signal.

## Frozen-threshold gate

| Threshold | Required | Measured | Verdict |
|---|---|---|---|
| Useful tasks in BOTH screenings (≥2 distinct functional rewards each) | ≥25% of 11 (≥3 tasks) | **4/11 = 36.4%** — D02, S03, S05, V01 | **MET** |
| Independent families among confirmed tasks | ≥5 | **4** (copy-recursive, move-select, text-aggregate, copy-flat) | **NOT MET (by one)** |
| Category coverage | every train family reported | all 8 reported (4 useful / 2 easy-covered / 2 hard-reserve) | MET |
| Scoring coverage | every candidate scored | 128/128 across both stages | MET |

Per-task detail (distinct scores per stage): D02 [0,1]/[0,1] · S03 [0,0.93]/[0,0.57,1.0] · S05 [0,0.87]/[0,0.59,0.96] · V01 [0,1]/[0,1] · S08 [0,0.76,0.88]/[0] (unconfirmed — useful once, all-zero under the second seed) · D04 [1]/— and V04 [1]/— easy-covered · D03/S02/S04 all-zero both stages · V03 no scored records.

## Gate outcome and implications

The predeclared readiness heuristic is **not fully met: 4 of the required 5 families confirmed** (the proportion threshold passed at 36%). Per PLAN Phase 4, the honest readings are:

1. **Train on the confirmed four families** (D02, S03, S05, V01 = 4 tasks/4 families) as the pilot core — this is a documented deviation from the ≥5-family heuristic, defensible because each confirmed task is informative under two independent seeds and the confirmed families cover three task *categories* (copy, move, aggregate).
2. **Author 1–2 additional train-pool tasks in a new family** and screen them (one extra activation, ~1.5h GPU ≈ $1–2) to satisfy the heuristic as written before freezing.
3. Drop S08 to reserve (unconfirmed) and keep D04/V04 as easy coverage inside training mix.

Recommendation: option 2 is cheap and preserves the predeclared gate as written; option 1 is defensible if the pilot budget matters more. This choice belongs to Phase 5 freezing and is recorded as the open decision.

## Operational record

- Providers/cost: Modal L4 ~$9 (credit), RunPod A40 ~$2 (cash), Codespace grading free; total cash ~$2 vs the $10/month ceiling. All machines torn down and verified empty (Modal app stopped, RunPod `pod list` empty, spend/hr 0).
- Evidence: stage summaries + per-candidate records + raw completions in `runs/P4-20261023T1100/` (private), tarballs hash-verified (`07a9e073…` stage-2) in `artifacts/P4-20261023T1100/`, and continuously mirrored to the private HF repo (`p4-screening/` prefix).
- New operational findings recorded: RunPod CPU-class pods get no SSH proxy; RunPod GPU pods block userns+DinD (grading must be split or run elsewhere); RunPod 50GB+ container disk required for the ~16GB checkpoint (15GB default hits ENOSPC); Modal gVisor passes the full namespace grading contract including the chown path.

## Addendum — phase 5 family top-up (2026-10-24): gate now MET as written

After the 4/5-family outcome above, one new train family was authored and screened under the same frozen thresholds/seeds: **W01/W02 (manifest-verify** — sha256 manifest verification/generation; hashing is a solution pattern distinct from every existing family). W01/W02 passed the Phase 1 acceptance harness on the Docker grader first (all expectations, 3 repeats deterministic), then screened: 2 tasks × 8 candidates × both seeds (32 generations on RunPod A40 via the split pipeline; grading on the Codespace Docker engine). **Both W tasks are useful in both screenings** (W01 distinct scores {0.0, 0.3, 1.0} s1 / {0.0, 1.0} s2; W02 {0.5, 1.0} in both).

Merged 13-task gate (config `configs/screening-v2.yaml`, analysis in `runs/P5-topup/analysis-13task.json`):

- **Useful in both screenings: 6/13 = 46.2% (≥25% — MET)**: D02, S03, S05, V01, W01, W02
- **Independent families: 5/5 (MET)**: copy-recursive, move-select, text-aggregate, copy-flat, manifest-verify
- Scoring coverage 1.0 across all 160 records (104 s1 / 56 s2); 0 infrastructure errors
- Family coverage: 4 useful / 2 easy-covered (repair-copy D04+S08, text-slice V04) / 3 hard-reserve (file-list-nul S04, repair-listing V03, and D03/S02 zeros within their families)

The phase 4 readiness heuristic is **satisfied as written**. Accepted training pool for the Phase 5 freeze: the 6 confirmed tasks + easy coverage (D04, V04); hard-reserve tasks stay out. S08 remains unconfirmed (useful s1, all-zero s2) and stays in easy-covered/repair-copy only as coverage. Top-up cost: ~$1 RunPod cash.
