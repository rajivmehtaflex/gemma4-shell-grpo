# Project state

Updated: 2026-10-20 (Asia/Kolkata)

## Current milestone

Phase 0 repository setup is complete and the repository is public. The current documentation milestone reconciles the authored-first phase gates, fixture/task scoring contract and final outcome classification following the review of commit `1d732d4`. GitHub Codespaces remains the CPU priority and Google Colab the GPU priority. Runtime/storage/orchestration checks, Phase 1 implementation and all model experiments remain unstarted; the Pi source audit is deferred until before Phase 3. Publication is verified after committing; this file does not embed its own containing commit SHA.

No Codespace, Colab or Modal session activation, model loading, Pi-log ingestion, generated-script execution, GPU provisioning, or training has been performed by this documentation work.

## Decisions

- Original Gemma 4 E4B instruction checkpoint; direct GRPO; no SFT stage.
- CPU-first preparation and grading, GPU only for model-dependent work.
- CPU phases 0/1/3/5: activate GitHub Codespaces with `gh-cli-ops` and execute the full phase.
- GPU phases 2/4/6/7: activate Google Colab with `colab-ssh-setup` and execute the full phase; Phase 8 uses Colab then Codespaces.
- All phases preserve private artifacts, publish a Git milestone through `gh-cli-ops`, and verify machine shutdown. Controller is the default GitHub writer.
- `modal-deploy-ssh` is a fallback only after an explicit provider decision, with the same grading and persistence gates.
- Separate public GitHub repository: `rajivmehtaflex/gemma4-shell-grpo`, using the `rajivmehtaflex` account for Git publication (user-confirmed 2026-10-20).
- Phase 0 CPU Codespace: basic 2-core machine on the GitHub free tier; controller spending ceiling $10/month (user-confirmed 2026-10-20).
- Dataset scope: authored-first path (user-confirmed 2026-10-20). Phase 0/1 proceed entirely on authored exercises; the user uses Pi for real shell work in parallel. Audit available, user-designated sessions before Phase 3. If they cannot support at least five plausible exercises, Phase 3 uses authored task construction; otherwise tasks may combine authored and Pi-derived origins with honest provenance. Public summaries describe this conditional source strategy. A substitute session source is possible only as a future documented scope decision.
- One generated script per exercise initially.
- Proposed fast stack is Unsloth + TRL, accelerated rollout integration conditional on compatibility evidence.
- Commit and push at every milestone and machine handoff.
- First CPU deliverable: five fully verified exercises before expanding to the diagnostic suite. Pilot scope stays within local file/quoting tasks, text transformations and short script repair.
- Candidates in a GRPO group share fixture seeds but execute on separate clean state. Preservation checks are gates; positive reward requires functional progress.
- Proposed acceptance target: +5 percentage points in held-out task-level pass rate, paired 95% interval above zero, and no increase in observed critical violations. Freeze before training; a small pilot may remain inconclusive.
- Matched training-backend comparison comes first; deployment quantization/runtime results are tracked separately.
- Pi practice-session campaign (user-approved 2026-10-20): ten authored exercises S01–S10 solved by the user in **real** Pi conversations (Pi 1.3.0, NVIDIA provider, `meta/muse-glimmer-30b`, medium thinking, bash disabled in Pi). Tasks are authored; conversations and outcomes are real; failures are preserved; nothing is fabricated or edited. Practice sessions are reported **separately from naturally occurring sessions**, stay in the development pool, are excluded from the final unseen test set, and are never SFT targets. Verification reuses the Phase 1 grader and is gated on Phase 0/1 acceptance; at most three submitted candidates per task in the initial campaign.

## Pending before their dependent phases

- Phase 1: choose CPU runtime/container engine and confirm Linux execution isolation requirements.
- Before CPU activation: verify current access, actual runtime identity, storage capacity and deadline/stop readiness against the recorded account, basic 2-core choice and $10/month ceiling. These user decisions are already resolved; no Pi sample is required for Phase 0/1.
  - Resolved 2026-10-20: Git publication account confirmed as `rajivmehtaflex` (user decision; verified active in `gh auth status`).
  - Resolved 2026-10-20: the user ran `gh auth refresh -h github.com -s codespace` on the active `rajivmehtaflex` account. Verified afterwards: token scopes now include `codespace`, `gh api user` returns `rajivmehtaflex`, and `gh codespace list` is empty. Single-identity strategy chosen — one account performs both Codespace activation and Git publication; no split-role activator needed. The first Codespace will be created from `rajivmehtaflex/gemma4-shell-grpo` (user-stated plan).
  - Resolved 2026-10-20 (resources and budget): basic 2-core Codespace, GitHub free tier, $10/month spending ceiling (user decision).
  - Resolved 2026-10-20 (dataset scope): authored-first path chosen (see Decisions). The existing archive's exercise yield is **not yet assessed** (metadata-only inspection found one 156 KB session; contents unread), so the source preflight is deferred to a re-run before Phase 3 rather than run now.
  - Open before Phase 3: Pi source viability. Local inventory on 2026-10-20 found Pi installed and authenticated but with exactly one session file (156 KB, 2026-10-07, project `~/Documents/Dev`); nothing in the last 7 days. Exercise yield remains unassessed because session contents were not read. This does not block Phase 0/1; the user accumulates real Pi sessions in parallel.
- Before first Colab activation: confirm its session name as required by `colab-ssh-setup`; verify CLI SSH/ADC prerequisites, accelerator, isolation capabilities and session budget.
- Phase 2: confirm the intended fast stack, Colab accelerator, exact upstream model/tokenizer revisions, and tested dependency versions. Proposed conservative path: Unsloth + TRL, fresh LoRA, `fast_inference=False`; accelerated rollout generation is optional.
- Phase 2: select durable private artifact storage and retention policy; this must exist before the first GPU run.
- Before Phase 3 task construction: identify user-designated representative Pi sessions and assess source viability and reconstructable state; record the authored-only or mixed-source path. An insufficient corpus uses the already approved authored-only fallback.
- Phase 5: finalize training hyperparameters and checkpoint cadence from measured compatibility/screening evidence.

The runner capability contract must be recorded before Phase 1 implementation; source feasibility is re-assessed before Phase 3 under the authored-first path (see Decisions). GPU-specific choices remain deferred until their dependent phases.

## Next action

CPU access, resources and budget are resolved. Activate the CPU Codespace from `rajivmehtaflex/gemma4-shell-grpo` through `gh-cli-ops` (basic 2-core), then execute Phase 0: claim the `artifacts/` handoff folder with a capacity check, bootstrap on the default image and record actual OS/tool versions, run the read-only skill dry-runs and the orchestration smoke test (including simulated failed upload/push recovery), and record the runtime capability contract. The Pi source preflight is deferred under the authored-first path and re-runs before Phase 3. Then specify the five Phase 1 exercises, typed schemas, reward examples and failure handling before CPU implementation. No GPU provisioning is needed.

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

- 2026-10-20: Added the user-approved GH/Codespaces-first CPU and Colab-first GPU orchestration to PLAN.md, HANDOFF.md and companion documentation, including the beginner guide. This is a documentation milestone only; no provider machine was activated and no phase acceptance gate was executed.

- 2026-10-20: Pre-activation environment audit (read-only): `gh auth status` shows four logged-in accounts; `rajivmehtaflex` is active with repo/workflow scopes but no `codespace` scope; `rajivmehtajs` and `mantramehtapy` carry `codespace`. User confirmed `rajivmehtaflex` as the publication account. Pi CLI (`~/.bun/bin/pi`) is installed and authenticated; `~/.pi/agent/sessions/` holds exactly one JSONL session (156 KB, 2026-10-07). No sessions were read; metadata only. Two user decisions now gate Phase 0 activation: Codespace scope strategy and Pi dataset scope.

- 2026-10-20: Codespace scope gap closed. User completed the device-flow `gh auth refresh -h github.com -s codespace` for `rajivmehtaflex`; post-refresh verification confirms the `codespace` scope and active identity. Remaining Phase 0 inputs: Codespace machine type and spending/storage expectations, plus the Pi dataset-scope decision (authored-first vs accumulate Pi sessions vs substitute source).

- 2026-10-20: User accepted the authored-first dataset path and set Phase 0 resources: basic 2-core Codespace, GitHub free tier, $10/month spending ceiling. Phase 0 machine activation is now unblocked; no Codespace has been created yet. Phase 0/1 proceed on authored exercises; the Pi source preflight re-runs before Phase 3.

- 2026-10-20: Commit `1d732d4` applied amendments from the 16-finding review, including the guide's arithmetic and paper references, launch snapshots, handoff fields, controller-unavailability smoke requirements, Colab smoke subruns and raw-completion records. Follow-up review found remaining Pi prerequisites in companion documents, inconsistent fixture/task scoring descriptions and an incomplete outcome classification. The earlier claim that every finding was resolved was premature; the next entry records the follow-up amendments. Documentation amendments do not demonstrate that runtime gates have passed.

- 2026-10-20: Follow-up documentation amendments remove obsolete Phase 0/1 Pi prerequisites, place the source audit with Phase 3, align authored-first summaries, specify fixture/aggregate status and reward precedence, and separate final effect direction, practical-target attainment and critical-violation acceptance. Boundary examples cover mixed execution statuses and functional gains with increased violations. Validation reviewed all seven Markdown files, resolved all 14 local links, preserved the nine-phase sequence, checked five numerical outcome examples and passed `git diff --check`; the obsolete gate phrases were absent. No machine activation, source ingestion, grader implementation or model experiment occurred; phase acceptance evidence remains to be produced during execution.

- 2026-10-20: Pi practice-session campaign scaffolded under `pi-sessions/` (tracked: README, ten task briefs S01–S10 with frozen prompts, fixture specs, gated `verify.py` skeleton, `manifest.jsonl`; ignored: `raw/`, `work/`, `results/`, `private/` — ignore rules verified via `git check-ignore`). Pi CLI verified at v1.3.0 with every planned launch flag present (`--name`, `--thinking`, `--tools`, `--no-extensions`, `--no-mcp`, `--session-dir`) and a read-only `pi auth check` available for spending coverage. Frozen prompts and fixture edge cases authored; one S04 fixture byte-sort error was found and corrected during authoring. Brief/fixture hashes, sessions, and outcomes do not yet exist. Collection is operator-owned (the user drives Pi) and not started; verification is gated on Phase 0/1 acceptance.
