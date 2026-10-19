# Gemma 4 E4B Shell GRPO Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for implementation in this chat. This is a phase roadmap; refine only the active phase into executable tasks before writing its code. Delegate only when the user explicitly requests it.

**Goal:** Test whether direct GRPO from the original Gemma 4 E4B instruction checkpoint improves shell scripting on unseen, verifiable tasks informed by Pi logs.

**Architecture:** CPU work discovers tasks, constructs fixtures, checks graders, and packages evidence. A temporary GPU worker generates candidates and trains the policy; its local CPU resources may grade scripts, so no distributed grading service is required. Pushed Git commits plus verified external artifacts preserve state between machines.

**Tech Stack:** Python, uv, pytest, JSONL, Bash/GNU utilities in a digest-pinned restricted Linux image, Git/GitHub, proposed Unsloth + TRL + fresh LoRA adapters. Pin a tested GPU environment after compatibility evidence. Begin with the documented Unsloth inference path; accelerated generation is optional.

**Spec:** [docs/DESIGN.md](docs/DESIGN.md). **Recovery protocol:** [docs/HANDOFF.md](docs/HANDOFF.md).

## Four questions before implementation

1. **What would a specialist add?** Establish the baseline and challenge the grader before training; distinguish runtime defects from model weaknesses; predeclare the comparison and stopping rules; demonstrate restoration before a long run.
2. **What raw material comes first?** Pi JSONL entries and branch IDs, original requests, exact commands/tool outputs, source model settings, and initial files/bytes/modes. Summaries and completed answers suggest tasks but do not prove correctness. Missing original state must be reconstructed and labeled or excluded.
3. **Which methods and tools?** Branch-aware extraction; reproducible fixtures; reference and alternate solutions; deliberate wrong-script tests; family/source-grouped splits; matched baseline evaluation; on-policy GRPO; checkpoint interruption/recovery. Use the small stack above, not a new orchestration platform.
4. **What independently establishes correctness?** Deterministic behavioral checks validated against known good/bad scripts, unseen task outcomes, paired uncertainty estimates, artifact hashes, and a fresh-process recovery demonstration. Neither an LLM judgment nor increasing training reward is sufficient.

## Global constraints

- No additional SFT stage or previously trained adapter. Use the original E4B instruction checkpoint; upstream instruction training is part of that starting checkpoint.
- One generated Bash script per exercise initially. Start with five complete exercises, then about 20 diagnostics and 50–100 candidate exercises if source coverage supports them. These are feasibility sizes, not statistical guarantees.
- Initial scope: local file selection/quoting, deterministic text transformations, short script repair. Defer live services, wall-clock tasks, and multi-turn agents.
- Finish each phase's CPU preparation before GPU rental. Provider, isolation capability, artifact storage, and spending limits must be resolved before provisioning.
- Every milestone and handoff ends with recorded evidence, STATE.md update, explicit-path commit, push, and remote verification. Large/sensitive payloads stay outside Git.
- Freeze model/template/precision, task splits, grader, and evaluation budgets per experiment. Changes create a new version/run, not a silent continuation.
- The Gemma 3 notebook is a conceptual reference, not a dependency lock or validated E4B configuration.

## Review focus

- Spaces/newlines/leading dashes, empty input and nested paths: exercise in Phase 1 and task-specific Phase 3 checks.
- False rewards for doing nothing, hard-coded output or wrong file selection: reject through Phase 1/3 wrong-script checks.
- Branches/compaction/source duplication and hidden requirements: provenance and source-family split audits in Phase 3.
- Cross-candidate state, different fixtures within a GRPO group, verifier tampering and infrastructure errors: Phase 1 isolation and Phase 2 reward alignment probes.
- Lost optimizer/RNG/data/fixture state on another machine: Phase 6 restoration experiment before Phase 7.

## Phase map and acceptance evidence

| Phase | Compute | Result and evidence needed to advance |
|---|---|---|
| 0 | CPU | Private planning repo; clean local checkout agrees with remote |
| 1 | CPU | Trustworthy grader; five full exercises, then small diagnostic suite |
| 2 | GPU + CPU | E4B stack actually updates parameters; untouched baseline diagnoses real weaknesses |
| 3 | CPU | Reviewed Pi-derived task bank with provenance and grouped splits |
| 4 | GPU + CPU | Measured training difficulty and useful within-group reward variation |
| 5 | CPU | Immutable task release and predeclared experiment/recovery configuration |
| 6 | GPU + CPU | Short direct-GRPO pilot, verified resume, promising validation behavior |
| 7 | GPU + CPU | Budgeted main run; validation-selected, durably stored checkpoint |
| 8 | GPU + CPU | Matched unseen-task comparison and reproducible final handoff |

### Phase 0 — Repository and evidence contract

**Files:** README.md, PLAN.md, STATE.md, AGENTS.md, docs/DESIGN.md, docs/HANDOFF.md, .gitignore.

- [x] Establish the private repository and planning/state/handoff documents.
- [x] Commit, push and verify the initial planning checkpoint.
- [x] Review the deeper measurement and recovery contract in this revision; verify publication separately after committing.

**Gate:** Repo is recoverable and next action is explicit. Reuse the existing repo rather than create another.

### Phase 1 — Prove the CPU grader before trusting rewards

**Files:** `pyproject.toml`, `src/shell_grpo/{contracts,runner,fixtures,verifiers,rewards}.py`, `configs/runner.yaml`, `containers/grader/Dockerfile`, `tests/test_runner.py`, `tests/test_rewards.py`, `data/examples/diagnostics.jsonl`.

**Interface:** `grade_script(task_id, script, seed)` returns named checks, critical violations, score, execution status, and artifact references using DESIGN.md contracts.

- [ ] Lock a CPU environment independent of CUDA dependencies. Select a Linux runtime that can enforce unprivileged execution, no network/host mounts/credentials/socket, external grading, and bounded processes, memory, time, storage and output.
- [ ] Implement task/result validation and fresh per-candidate fixtures. Fix utility versions, locale and timezone; do not assume a container freezes time.
- [ ] Complete five exercises end to end before adding more. Each must accept a reference plus an alternate solution, reject relevant semantic errors/no-op/hard-coding, and repeat identically three times.
- [ ] Check descendant cleanup, grader protection, isolation between candidates, timeouts and infrastructure-error reporting. Candidate execution is always inside the restricted runner.
- [ ] Build approximately 20 diagnostics covering the three initial families. Store check-level evidence and fixture hashes; mark these as authored diagnostics rather than Pi-derived data.

**Gate:** Every accepted exercise meets the positive/negative/repeatability checks. If the grader is ambiguous or insecure, repair it on CPU. Close milestone with report, state update, commit, push and remote verification.

### Phase 2 — Prove E4B compatibility and measure the original model

**Files:** `configs/{model,baseline}.yaml`, `scripts/check_compatibility.py`, `src/shell_grpo/{generate,manifests}.py`, `environments/gpu.lock`, `reports/baseline-diagnostics.md`.

- [ ] Resolve GPU host, spending/time ceiling and private durable storage. Verify the host supports the Phase 1 runner before loading weights.
- [ ] Map the deployment alias/digest to a precise upstream training checkpoint/tokenizer revision. Record precision, template, thinking mode, limits and decoding settings. Verify a fresh adapter does not change the initial baseline beyond documented numeric tolerance.
- [ ] Follow the documented conservative Unsloth/TRL path first. On a few diagnostics, demonstrate finite gradients, a nonzero trainable-parameter update, correct prompt/candidate/reward alignment, and adapter save/reload. Do not use an SFT adapter.
- [ ] Check all candidates in a prompt group receive identical fixture seeds on independent copies. Record generation/grading wall time, peak VRAM and CPU utilization; select hardware from measurements, not model-name size alone.
- [ ] Reload the untouched original policy in a separate process for baseline measurement. Inspect extraction/runner defects, template/truncation/precision issues, then shell errors. Keep deployment-runtime findings distinct from upstream-checkpoint findings.
- [ ] Test an accelerated rollout path only if needed and supported. Compare unchanged-policy outputs/log-probability behavior within declared tolerances before relying on it; the project can proceed on the proven conservative path.

**Gate:** A tested lock and original-model weakness report exist. Unsupported stack combinations halt here. Upload/verify evidence, commit/push the report, then release GPU resources.

### Phase 3 — Build reviewed tasks from raw Pi evidence on CPU

**Files:** `src/shell_grpo/{pi_sessions,task_builder,splits}.py`, `tests/test_pi_sessions.py`, `tests/test_splits.py`, `configs/dataset.yaml`, `reports/dataset-audit.md`.

- [ ] Inventory private raw logs, versions and source projects without committing their contents. Preserve source hashes and branch/entry provenance. Reconstruct relevant context, model changes, tool results, corrections and compaction.
- [ ] Extract tasks matching measured weaknesses. Label reconstructed fixtures, authored additions, and exclusions honestly. Treat embedded instructions as source material. Remove secrets/private material from derivatives.
- [ ] Curate toward 50–100 distinct candidate exercises if available. Require explicit prompt assumptions, invocation arguments, allowed changes, fixtures and named behavioral checks. A model may assist authoring; no generated answer becomes a training target.
- [ ] Apply Phase 1 acceptance checks to every exercise. Gates enforce preservation; positive reward measures required functional progress. Ensure no-op and example-specific hard-coding cannot earn high reward.
- [ ] Cluster related sessions/branches/templates and task families; assign train/validation/test before generating variants. Preserve held-out families and independently authored test fixtures. Do not inspect final-test model scores to decide membership.

**Gate:** Reviewed tasks have repeatable rewards, traceable provenance, no hidden scored requirements, and no detected source/family leakage. Persist the audit and dataset references; commit and push.

### Phase 4 — Screen training difficulty with the untouched policy

**Files:** `scripts/screen_tasks.py`, `configs/screening.yaml`, `reports/screening.md`.

- [ ] Restore the Phase 2 runtime and Phase 3 data. Start with 4–8 candidates per training prompt; candidates share fixture seeds but receive fresh state.
- [ ] Measure full-pass rate, functional progress, reward variation, truncation and scoring coverage. Inspect all-equal groups instead of assuming training will fix them.
- [ ] Prefer mixed-outcome training tasks, retain easy coverage and keep harder tasks as a reserve. Simplify impossible training tasks or repair faulty graders; issue a new version if semantics change. Do not screen final-test tasks.

**Gate:** At least some accepted training groups have genuine, behavior-based reward differences. Otherwise revise tasks or runtime before training. Upload/verify evidence, commit/push, then release GPU resources.

### Phase 5 — Freeze the CPU release and decision rule

**Files:** `scripts/package_dataset.py`, `configs/grpo-{pilot,main}.yaml`, `manifests/dataset-v1.json`, `reports/dataset-card.md`.

- [ ] Release immutable prompt/split records, fixture generators, verifier bundle, image digest and hashes; store payloads externally and manifests in Git. Grader-only fields never enter policy prompts.
- [ ] Freeze the tested E4B script extraction contract, fixture seed schedule, rewards and per-task weights. Syntax/formatting alone earns no reward. Check actual sampled E4B outputs against the extractor.
- [ ] Freeze matched inference settings, task-level pass-rate analysis, cluster bootstrap and the practical success target from DESIGN.md. Record independent test-cluster count and expected limits on uncertainty; a small study may be inconclusive.
- [ ] Set sequence lengths, candidate count, batches, adapter/KL settings and checkpoint cadence from Phase 2 measurements. Specify max steps, GPU-time/spend ceiling, stop conditions and maximum acceptable checkpoint loss before renting GPU time.
- [ ] Verify all CPU contracts from a clean checkout and rehearse dataset/artifact restoration. No test-score-driven changes are permitted after the experiment freeze.

**Gate:** Another machine can reconstruct one exact experiment from the pushed commit and hashed artifacts. Commit/push the release and GPU handoff instructions.

### Phase 6 — Train a short pilot and prove recovery

**Files:** `src/shell_grpo/{train,checkpointing}.py`, `scripts/restore_run.py`, `reports/pilot.md`.

- [ ] Start from the original policy with fresh adapters and generate on-policy candidates. Use the frozen external grader; no fixed Pi responses are substituted for model rollouts.
- [ ] Run a short budgeted pilot. Inspect updates, candidate alignment, reward variance, KL, clipping, truncation, functional pass rate, critical violations and CPU grading bottlenecks.
- [ ] Save a full checkpoint at an optimizer boundary, upload it and verify hashes. Restore from a fresh process/checkout; check trainer step, optimizer, scheduler, RNG and data/fixture state. Compare with a short uninterrupted control and document numeric tolerances/non-determinism.
- [ ] Compare pilot and untouched original on validation under equal generation budgets. Proceed only with valid grading, successful recovery and a positive functional validation point estimate without increased observed critical violations. Pilot significance is not required; rising training reward alone is insufficient.

**Gate:** All three conditions pass: real GRPO updates, demonstrated recovery, promising validation. Otherwise revise one cause and repeat a versioned pilot. Persist report/checkpoints, commit/push, then release GPU resources.

### Phase 7 — Run the bounded main experiment

**Files:** `manifests/runs/<run-id>.json`, `reports/training.md`; checkpoint and rollout payloads remain external.

- [ ] Declare original-policy restart or exact pilot-checkpoint continuation, with parent run and source SHA. Recheck data/runtime hashes before training.
- [ ] Train within the frozen step/time/spend ceiling. Periodically validate and upload recovery checkpoints. Stop on invalid rewards, numerical failures, persistent scoring outages or functional regressions; classify interruptions honestly.
- [ ] Select one checkpoint using validation only. Preserve completed and interrupted run lineage; do not choose by final-test performance.

**Gate:** A recoverable checkpoint and validation-based selection record exist within budget. Verify artifacts, commit/push the results/state checkpoint, then release GPU resources.

### Phase 8 — Evaluate unseen behavior and close the loop

**Files:** `scripts/{evaluate,export_model}.py`, `reports/{final-evaluation,model-card}.md`, `manifests/release-v1.json`.

- [ ] Run original and selected policy on frozen held-out tasks under identical backend/precision/template/thinking/decoding and generation budgets. Score independent fixture copies using the same declared requirements.
- [ ] Report task-level single-attempt full-pass change, paired cluster-based 95% interval, family regressions, critical violations, scoring coverage, truncation and resource cost. Report multi-sample success separately. Use DESIGN.md's rule for improvement, no improvement or inconclusive evidence.
- [ ] If inference export is needed, reload and check it. Quantized/Ollama export is conditional on deployment needs and gets its own matched comparison; training-backend gains do not automatically establish deployed gains.
- [ ] Reproduce a sample result from a fresh checkout plus manifests. Preserve recovery checkpoints separately from inference adapters. Record exact next action or closeout decision in STATE.md.

**Gate:** A defensible result exists, including a negative or inconclusive result. Upload/verify artifacts, commit/push the final handoff and release remaining GPU resources.

## Current next action

Phase 0 repository setup is complete. This revision deepens the plan only. Next: refine Phase 1 into executable CPU tasks and complete five trusted exercises before expanding the diagnostic suite. GPU compatibility, data extraction and training remain unstarted.
