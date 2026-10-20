# Project state

Updated: 2026-10-20 (Asia/Kolkata)

## Current milestone

Phase 0 repository setup is complete. The repository was subsequently made public at the user's request. The current documentation update incorporates the 12 review findings into PLAN.md and moves a small source/runtime preflight ahead of Phase 1 implementation. Preflight, Phase 1 and all model experiments remain unstarted. Publication of this revision is verified after its commit; this file does not embed its own containing commit SHA.

No model loading, Pi-log ingestion, generated-script execution, GPU provisioning, or training has occurred in this repository.

## Decisions

- Original Gemma 4 E4B instruction checkpoint; direct GRPO; no SFT stage.
- CPU-first preparation and grading, GPU only for model-dependent work.
- Separate public GitHub repository: `rajivmehtaflex/gemma4-shell-grpo`, using the active authenticated GitHub account.
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
- Before Phase 1 implementation: identify user-designated representative Pi sessions and assess source viability and reconstructable state; full extraction remains Phase 3.
- Phase 5: finalize training hyperparameters and checkpoint cadence from measured compatibility/screening evidence.

Source feasibility and the runner capability contract must be recorded before Phase 1 implementation. GPU-specific choices remain deferred until their dependent phases.

## Next action

Perform the small Pi-source and runtime-capability preflight in PLAN.md Phase 0. Then specify the five Phase 1 exercises, typed schemas, reward examples and failure handling before CPU implementation. Expand toward 20 diagnostics only after the five pass. No GPU provisioning is needed.

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

- 2026-10-20: Updated PLAN.md to address all 12 review findings at the planning level, including earlier source preflight, shared Phase 2 training/evaluation, explicit scoring failures, concrete diagnostic exercises, screening thresholds, grouped splits and bounded experiment selection. Gates remain unexecuted. Repository is public following the user-authorized visibility change; raw data and checkpoint storage remain private.
