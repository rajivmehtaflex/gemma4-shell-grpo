# Project state

Updated: 2026-10-19 (Asia/Kolkata)

## Current milestone

Phase 0 repository setup is complete. Before this revision, checkpoint `5f225c3969639029ea281fcf40b1b73ea97da97b` matched fetched `origin/main`; GitHub private visibility was verified. This documentation revision deepens the measurement, dataset, reward and recovery contracts. Phase 1 is next and has not started. The containing revision's commit/push is verified externally after publication; no self-referential commit SHA is embedded here.

No model loading, Pi-log ingestion, generated-script execution, GPU provisioning, or training has occurred in this repository.

## Decisions

- Original Gemma 4 E4B instruction checkpoint; direct GRPO; no SFT stage.
- CPU-first preparation and grading, GPU only for model-dependent work.
- Separate private GitHub repository: `rajivmehtaflex/gemma4-shell-grpo`, using the active authenticated GitHub account.
- One generated script per exercise initially.
- Proposed fast stack is Unsloth + TRL, accelerated rollout integration conditional on compatibility evidence.
- Commit and push at every milestone and machine handoff.
- First CPU deliverable: five fully verified exercises before expanding to the diagnostic suite. Pilot scope stays within local file/quoting tasks, text transformations and short script repair.
- Candidates in a GRPO group share fixture seeds but execute on separate clean state. Preservation checks are gates; positive reward requires functional progress.
- Proposed acceptance target: +5 percentage points in held-out task-level pass rate, paired 95% interval above zero, and no increase in observed critical violations. Freeze before training; a small pilot may remain inconclusive.
- Matched training-backend comparison comes first; deployment quantization/runtime results are tracked separately.

## Pending before their dependent phases

- Phase 1: choose CPU runtime/container engine and confirm Linux execution isolation requirements.
- Phase 2: confirm the intended fast stack, GPU provider/type and isolation capabilities, session budget, exact upstream model/tokenizer revisions, and tested dependency versions. Proposed conservative path: Unsloth + TRL, fresh LoRA, `fast_inference=False`; accelerated rollout generation is optional.
- Phase 2: select durable private artifact storage and retention policy; this must exist before the first GPU run.
- Phase 3: identify Pi session locations, relevant projects, and whether their original environments can be recreated.
- Phase 5: finalize training hyperparameters and checkpoint cadence from measured compatibility/screening evidence.

These decisions do not prevent Phase 1 CPU design and implementation.

## Next action

Refine Phase 1 into executable CPU tasks, select the Linux grading runtime, then implement contracts and five complete exercises with positive/negative/repeatability evidence. Expand toward 20 diagnostics only after these pass. Consult PLAN.md. GPU provisioning is not needed yet.

## Provenance

Reference notebook supplied by the user: `/Users/rajivmehtapy/Desktop/notebook5ffcd6ec70.ipynb` (Gemma 3/GSM8K GRPO tutorial; source only, not executed or copied into this repository).

Existing files in the parent workspace describe other projects with SFT prerequisites. Those project-specific workflows are not inherited by this new direct-GRPO project.

## Evidence ledger

- 2026-10-19: Parent workspace has no Git repository. Dedicated project directory selected.
- 2026-10-19: GitHub authentication verified; active identity is `rajivmehtaflex`.
- 2026-10-19: Roadmap and artifact/handoff contracts drafted. Implementation phases remain queued.
- 2026-10-19: Private repository created at https://github.com/rajivmehtaflex/gemma4-shell-grpo; initial planning commit `6594b80` pushed and remote SHA verified. This state update is a subsequent documentation checkpoint.
- 2026-10-19: Existing clean repo reused; fetched local/remote checkpoint `5f225c3` and private visibility verified. No duplicate repository created.
- 2026-10-19: Checked current Unsloth training/RL guide and TRL documentation through Context7. Unsloth documents a conservative Gemma 4 RL path with `fast_inference=False`; this is documentation evidence, not a tested E4B runtime or VRAM claim.
- 2026-10-19: Revised the existing nine-phase plan with raw-source provenance, wrong-script grader checks, matched controls, reward group fixture identity, statistical uncertainty and fresh-process recovery evidence. No implementation or model experiment performed.
