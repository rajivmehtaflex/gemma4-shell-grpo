# Project state

Updated: 2026-10-19 (Asia/Kolkata)

## Current milestone

Phase 0 complete. Planning checkpoint `6594b80d0415f6693721dbdf36759426c7462420` was pushed to `main`; GitHub private visibility and matching remote SHA were verified. Phase 1 is next and has not started.

No model loading, Pi-log ingestion, generated-script execution, GPU provisioning, or training has occurred in this repository.

## Decisions

- Original Gemma 4 E4B instruction checkpoint; direct GRPO; no SFT stage.
- CPU-first preparation and grading, GPU only for model-dependent work.
- Separate private GitHub repository: `rajivmehtaflex/gemma4-shell-grpo`, using the active authenticated GitHub account.
- One generated script per exercise initially.
- Proposed fast stack is Unsloth + TRL, accelerated rollout integration conditional on compatibility evidence.
- Commit and push at every milestone and machine handoff.

## Pending before their dependent phases

- Phase 1: choose CPU runtime/container engine and confirm Linux execution isolation requirements.
- Phase 2: confirm what the user means by fast stack, GPU provider/type, session budget, exact upstream model/tokenizer revisions, and tested dependency versions.
- Phase 2: select durable private artifact storage and retention policy; this must exist before the first GPU run.
- Phase 3: identify Pi session locations, relevant projects, and whether their original environments can be recreated.
- Phase 5: finalize training hyperparameters and checkpoint cadence from measured compatibility/screening evidence.

These decisions do not prevent Phase 1 CPU design and implementation.

## Next action

Refine Phase 1 into executable CPU tasks, select the Linux grading runtime, then implement task contracts, the restricted runner, fixtures, verifiers, and the diagnostic suite. Consult PLAN.md. GPU provisioning is not needed yet.

## Provenance

Reference notebook supplied by the user: `/Users/rajivmehtapy/Desktop/notebook5ffcd6ec70.ipynb` (Gemma 3/GSM8K GRPO tutorial; source only, not executed or copied into this repository).

Existing files in the parent workspace describe other projects with SFT prerequisites. Those project-specific workflows are not inherited by this new direct-GRPO project.

## Evidence ledger

- 2026-10-19: Parent workspace has no Git repository. Dedicated project directory selected.
- 2026-10-19: GitHub authentication verified; active identity is `rajivmehtaflex`.
- 2026-10-19: Roadmap and artifact/handoff contracts drafted. Implementation phases remain queued.
- 2026-10-19: Private repository created at https://github.com/rajivmehtaflex/gemma4-shell-grpo; initial planning commit `6594b80` pushed and remote SHA verified. This state update is a subsequent documentation checkpoint.
