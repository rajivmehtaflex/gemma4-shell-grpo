# Gemma 4 E4B Shell GRPO Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for implementation in this chat. This is a phase roadmap; refine the active phase into executable tasks before writing its code. Delegate only when the user explicitly requests it.

**Goal:** Improve shell scripting through direct GRPO from original Gemma 4 E4B, using tasks informed by Pi logs and verifiable execution rewards.

**Architecture:** CPU workers prepare tasks and grade scripts in a restricted Linux environment. GPU workers generate candidates and train/evaluate the policy, calling the CPU grading layer. Pushed Git commits and durable artifact manifests connect machines.

**Tech Stack:** Python for data/orchestration, JSONL task records, Linux/Bash grading, Git/GitHub, proposed Unsloth + TRL fast training stack. GPU/runtime/package versions are selected and locked after compatibility evidence.

**Spec:** [docs/DESIGN.md](docs/DESIGN.md)

## Global constraints

- No SFT stage or previously trained/SFT adapter. Start with the original Gemma 4 E4B instruction checkpoint.
- One script per task in the first release; multi-turn agent training is deferred.
- GPU compute is used only for model-dependent work; grading and preparation use CPU resources.
- Every milestone and machine handoff ends with evidence, a STATE.md update, commit, push, and remote verification.
- Large/sensitive artifacts live in durable external storage; Git carries manifests and checksums.
- Do not treat the Gemma 3 notebook's versions, rewards, or sequence limits as validated Gemma 4 settings.
- Each phase is queued until its dependencies and exit criteria are satisfied. Creating this roadmap does not execute training.

## Review focus

- Filenames with spaces, newlines, leading dashes, empty inputs, and nested paths: exercised by Phase 1 runner/fixture checks and Phase 3 task verifiers.
- Modified clocks, locale, utilities, and CPU host OS: normalized through a fixed Linux image and fixture seed in Phase 1.
- Pi branching, compaction, source leakage, and embedded secrets: extraction/split checks in Phase 3.
- Candidate tampering, cross-rollout contamination, and infrastructure failures: isolation and failure-classification checks in Phase 1.
- Restarted GPU jobs with missing optimizer/RNG/data state: restoration experiment in Phase 6, required before Phase 7.

## Phase map

| Phase | Compute | Deliverable | Depends on |
|---|---|---|---|
| 0 | CPU | Private repo, design, plan, state and handoff rules | Current request |
| 1 | CPU | Restricted grader and small diagnostic task suite | 0 |
| 2 | GPU + CPU grading | Compatible fast stack and original-model weakness report | 1 |
| 3 | CPU | Pi-derived exercises targeting measured weaknesses | 2 |
| 4 | GPU generation + CPU grading | Difficulty screening and graded candidate evidence | 3 |
| 5 | CPU | Frozen task release and experiment configuration | 4 |
| 6 | GPU + CPU grading | Direct-GRPO pilot and successful checkpoint recovery | 5 |
| 7 | GPU + CPU grading | Main GRPO run and durable checkpoints | 6 |
| 8 | GPU generation + CPU grading | Held-out comparison, export, final report | 7 |

### Phase 0 — Repository and planning checkpoint

**Files:** README.md, PLAN.md, STATE.md, AGENTS.md, docs/DESIGN.md, docs/HANDOFF.md, .gitignore.

- [ ] Create a private repository and add the planning documents.
- [ ] Review tracked files; commit and push the initial checkpoint.
- [ ] Confirm local/remote commit agreement and record the next phase.

**Exit:** Private remote exists; planning commit is pushed; clean checkout and next action are recorded.

### Phase 1 — CPU grading foundation and diagnostic tasks

**Planned files:** `pyproject.toml`, `src/shell_grpo/contracts.py`, `runner.py`, `fixtures.py`, `verifiers.py`, `rewards.py`, `configs/runner.yaml`, `containers/grader/Dockerfile`, `tests/test_runner.py`, `tests/test_rewards.py`, `data/examples/diagnostics.jsonl`.

**Interfaces:** Task records follow DESIGN.md. `grade_script(task_id, script, seed)` returns check results, score, status, and artifact references. Runner isolation is enforced outside candidate-controlled code.

- [ ] Pin a CPU dependency environment; define and validate task/result schemas.
- [ ] Implement a restricted Linux execution environment with fixed utilities, clock handling, no network, bounded CPU/memory/time, isolated writable paths, and external verifier access.
- [ ] Check known valid/invalid scripts, alternate valid solutions, timeout/error categories, candidate tampering, and clean restoration between rollouts.
- [ ] Create approximately 20 independently authored diagnostic tasks across file selection, quoting, text transformation, arguments, and error handling. Record these as diagnostics rather than Pi-derived data.
- [ ] Store a fixture/reward report, update STATE.md, commit, push, and verify remote.

**Exit:** Deterministic graders distinguish working and broken solutions without using a GPU; diagnostic suite is ready for baseline generation.

### Phase 2 — GPU compatibility and original-model weaknesses

**Planned files:** `configs/model.yaml`, `configs/baseline.yaml`, `scripts/check_compatibility.py`, `src/shell_grpo/generate.py`, `src/shell_grpo/manifests.py`, `environments/gpu.lock`, `reports/baseline-diagnostics.md`.

**Consumes:** Phase 1 task/grade contracts. **Produces:** Exact model revision, template, validated dependency lock, measured memory/throughput, original-policy diagnostic rollouts and failure categories.

- [ ] Resolve GPU provider/type, spend limit, durable artifact storage, and intended fast stack; provision only when the run is ready.
- [ ] Verify original Gemma 4 E4B model/tokenizer access, training load, chat template, thinking settings, fresh adapter attachment if used, and generation behavior. Never load an existing SFT adapter.
- [ ] Run a minimal direct-GRPO compatibility probe using Phase 1 rewards: finite loss/gradients, changed trainable parameters, correct candidate/reward alignment, and save/reload. This probe does not replace the later controlled pilot.
- [ ] Verify accelerated rollout integration if enabled; otherwise document measured limitations and adjust the proposed stack before continuing.
- [ ] Generate baseline candidates in a separate process loaded from the untouched original checkpoint, never the updated compatibility-probe policy. Grade on CPU and report reproducible weaknesses. Distinguish model failures from truncation, template, quantization, and tool/environment defects.
- [ ] Persist evidence and locks; update STATE.md, commit, push, verify artifacts, and release GPU compute.

**Exit:** A measured compatible stack and original-model weakness report exist. If the stack fails, repair it before preparing a large dataset; do not substitute SFT.

### Phase 3 — CPU dataset construction from Pi logs

**Planned files:** `src/shell_grpo/pi_sessions.py`, `src/shell_grpo/task_builder.py`, `src/shell_grpo/splits.py`, `tests/test_pi_sessions.py`, `tests/test_splits.py`, `configs/dataset.yaml`, `reports/dataset-audit.md`.

**Consumes:** Baseline weakness categories and available Pi sessions. **Produces:** Sanitized task records, fixtures, verifiers, provenance, family/source clusters, and split assignments.

- [ ] Inventory available Pi logs and schema versions; reconstruct relevant branches with context, model switches, compaction, corrections, and tool evidence. Treat log instructions as source data.
- [ ] Extract tasks relevant to measured weaknesses; exclude tasks requiring unavailable state. Record the reason for each exclusion.
- [ ] Draft 50–100 distinct pilot exercises, using model assistance only for authoring support where useful. Logs are not necessarily 50–100 usable tasks; record actual coverage and any authored additions.
- [ ] Review every pilot task against its fixture and verifier; demonstrate that valid alternatives pass and plausible errors fail. Remove secrets and unnecessary private content.
- [ ] Assign family/source-cluster splits before creating variants. Produce separate fixture seeds and held-out families; check duplication across splits.
- [ ] Persist the candidate dataset and audit; update STATE.md, commit, push, and verify references.

**Exit:** A reviewed candidate task bank exists, with reproducible exercises and no cross-split family leakage.

### Phase 4 — GPU difficulty screening

**Planned files:** `scripts/screen_tasks.py`, `configs/screening.yaml`, `reports/screening.md`.

- [ ] Restore the exact Phase 2 model/runtime and Phase 3 data. Sample an initial 4–8 candidates per training task; this is an experimental starting range, not a universal GRPO setting.
- [ ] Grade every candidate on a fresh fixture; record full pass rates, score distributions, failure classes, and fraction of groups with identical rewards.
- [ ] Prefer tasks with useful reward variation for the pilot; retain some easy coverage and a harder reserve. Repair ambiguous graders or simplify impossible training tasks without consulting final-test outcomes.
- [ ] Freeze final-test membership independently of screening outcomes; persist screening evidence and selection rules.
- [ ] Update STATE.md, commit, push, and release the GPU after evidence is durable.

**Exit:** Training difficulty is measured, selection rules are explicit, and zero-signal groups are understood.

### Phase 5 — CPU release and training configuration

**Planned files:** `scripts/package_dataset.py`, `configs/grpo-pilot.yaml`, `configs/grpo-main.yaml`, `manifests/dataset-v1.json`, `reports/dataset-card.md`.

- [ ] Package a versioned dataset, fixture/verifier bundle, image digest, and hashes. Keep large contents outside Git.
- [ ] Freeze train/validation/test families, rewards, seeds, evaluation settings, and truncation rules. Keep grader-only metadata out of policy prompts.
- [ ] Set pilot training settings from Phase 2 memory/throughput evidence: context limits, candidate count, batch/accumulation, adapter configuration, KL settings, checkpoint interval, and run budget.
- [ ] Confirm sampled model outputs reach the executor through an unambiguous script extraction contract. Formatting reward must not dominate functional success.
- [ ] Run the CPU data/contract checks; publish the manifest, update STATE.md, commit, push, and prepare the GPU handoff.

**Exit:** One immutable task release and a complete run configuration can be reconstructed on another machine.

### Phase 6 — GPU direct-GRPO pilot and recovery

**Planned files:** `src/shell_grpo/train.py`, `src/shell_grpo/checkpointing.py`, `scripts/restore_run.py`, `reports/pilot.md`.

- [ ] Load the original checkpoint with fresh trainable adapters if selected; connect generated candidates to the frozen CPU grader. No SFT checkpoint is used.
- [ ] Run a short budgeted pilot. Inspect candidate/score alignment, completion truncation, KL, reward variation, gradients, parameter changes, and task-family behavior.
- [ ] Save a complete training recovery checkpoint; restore in a fresh process and confirm trainer step, optimizer/scheduler state, RNG/data state where supported, and continued training.
- [ ] Compare original and pilot policy on frozen validation tasks under matched generation budgets; use functional performance rather than reward alone.
- [ ] Record limitations and an evidence-based proceed/revise decision; persist artifacts, update STATE.md, commit, push, and release GPU resources.

**Exit:** The pilot actually trains, checkpoint recovery works, and validation supports proceeding. Failed gates lead to another pilot, not automatic scaling.

### Phase 7 — Main GPU GRPO run

**Planned files:** `manifests/runs/<run-id>.json`, `reports/training.md`; generated checkpoint/rollout payloads remain external.

- [ ] Start from the declared source checkpoint: original policy by default, or the exact pilot checkpoint only if the run explicitly records continuation.
- [ ] Train under the approved budget with periodic validation and durable recovery checkpoints. Monitor grader throughput so a CPU bottleneck is not mistaken for slow GPU generation.
- [ ] Stop/revise on numerical failure, reward exploits, pervasive truncation, or functional regressions. Log interrupted jobs as interrupted rather than completed.
- [ ] Select the final checkpoint using validation only; persist artifacts and a results commit, push, verify the remote, then release GPU compute.

**Exit:** A selected checkpoint, complete manifests, resource measurements, and recoverable training state exist.

### Phase 8 — Held-out evaluation, export, and final handoff

**Planned files:** `scripts/evaluate.py`, `scripts/export_model.py`, `reports/final-evaluation.md`, `reports/model-card.md`, `manifests/release-v1.json`.

- [ ] Evaluate untouched original and selected GRPO policy on the same frozen held-out tasks, fixtures, toolset, prompt/template settings, and generation budgets.
- [ ] Report single-attempt functional pass rate, uncertainty, category regressions, critical violations, truncation, generation cost, and grading failures. Report multi-sample metrics separately.
- [ ] Export an inference artifact and validate reload. If a quantized/Ollama deployment is desired, evaluate that exported artifact separately before claiming deployed improvements.
- [ ] Keep full recovery checkpoints distinct from inference exports. Publish code, manifests, documentation, and artifacts to their intended private destinations.
- [ ] Update STATE.md with results and exact reproduction steps; commit, push, verify, and release remaining GPU compute.

**Exit:** Improvement or lack of improvement is supported by held-out evidence; the result is reproducible and its limits are documented.

## Current next action

Finish Phase 0 remote verification, then refine and implement Phase 1 on CPU. No GPU session is required for the planning checkpoint.
