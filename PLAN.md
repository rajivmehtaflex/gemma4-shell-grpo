# Gemma 4 E4B Shell GRPO Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for implementation in this chat. This is a phase roadmap; refine only the active phase into executable tasks before writing its code. Delegate only when the user explicitly requests it.

**Goal:** Test whether direct GRPO from the original Gemma 4 E4B instruction checkpoint improves shell scripting on unseen, verifiable tasks, starting with authored exercises and incorporating Pi-informed tasks if the pre-Phase 3 source audit supports them.

**Architecture:** The local controller orchestrates CPU work in GitHub Codespaces through `gh-cli-ops` and GPU work in Google Colab through `colab-ssh-setup`. A GPU worker may use its own CPU cores for restricted grading; no distributed grading service is required. Each phase includes machine activation, full phase execution, evidence collection, durable artifact preservation, Git publication and verified shutdown. Pushed Git commits plus verified private artifacts connect machines.

**Tech Stack:** Python, uv, pytest, JSONL, Bash/GNU utilities in a digest-pinned restricted Linux image, Git/GitHub, proposed Unsloth + TRL + fresh LoRA adapters. Pin a tested GPU environment after compatibility evidence. Begin with the documented Unsloth inference path; accelerated generation is optional.

**Spec:** [docs/DESIGN.md](docs/DESIGN.md). **Recovery protocol:** [docs/HANDOFF.md](docs/HANDOFF.md).

## Four questions before implementation

1. **What would a specialist add?** Establish the baseline and challenge the grader before training; distinguish runtime defects from model weaknesses; predeclare the comparison and stopping rules; demonstrate restoration before a long run.
2. **What raw material comes first?** For authored exercises, the explicit task brief, initial files/bytes/modes and independently checked expected behavior. For Pi-derived additions, JSONL entries and branch IDs, original requests, exact commands/tool outputs and source model settings. Summaries and completed answers suggest tasks but do not prove correctness. Missing original state must be reconstructed and labeled or excluded.
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

## Skill orchestration contract

The user-selected priority is **CPU → GitHub Codespaces through `gh-cli-ops`**, **GPU → Google Colab through `colab-ssh-setup`**. `gh-cli-ops` also governs GitHub identity/repository checks and publication for every phase. `modal-deploy-ssh` is a fallback only after an explicit provider decision; never switch or allocate extra resources silently. These are agent-operated runbooks, not a new scheduling service.

The controller resolves the installed skills by name, reads their current instructions, and records skill ID, retrievable revision/source and script hashes in the run manifest. A hash by itself is not a restoration source: retain a permitted versioned copy or immutable source revision. Before executing a phase, check current CLI help/features and use Context7 for provider/library decisions; old skill version and pricing examples are not guarantees. If the recorded skill revision cannot be restored, validate and record the replacement before starting a new execution.

**Execution record:** Every phase run gets a unique `run_id` and a private controller-side record under ignored `runs/<run_id>/`. Record its phase status, parent run, GH base SHA, exact code executed (worker commit SHA or a content hash and retained patch bundle for a dirty working tree), skill revision/hash, provider session ID, active job handle, log path, and artifact references/checksums. Keep SSH endpoints, tokens, raw Pi logs and credentials out of public Git. A later results commit must cite both the base Git SHA and exact executed code identity; never imply the base SHA alone identifies uncommitted worker changes.

Track work, artifact transfer, Git publication, machine shutdown and closeout as separate milestones. Phase status can be `ready`, `running`, `interrupted`, `work_verified`, `artifacts_verified`, `publish_pending`, `machine_stopped`, `closeout_pending` or `complete`; the per-run record keeps milestone evidence even when phase status is interrupted. Resume from the first unverified milestone without repeating verified compute. Mark complete only after the result commit and sanitized shutdown closeout commit both match the GitHub remote.

**Mandatory lifecycle, inherited by every phase:** Before each activation, re-read **Execution lessons learned (Phases 0–3)** near the end of this file — every pitfall hit so far is pre-recorded there with its prevention rule; a re-execution that follows it skips those failures.

1. **Read state and check readiness:** verify prerequisites, source Git SHA, artifact hashes, authentication, selected resources, session identity, duration/spend ceiling and output storage. Establish the private controller-side `artifacts/` directory before the first cloud phase and check free capacity against that phase's planned output size. Before GPU work, select and test an independent durable private copy for model checkpoints; the controller directory remains the retrieval copy. Confirm the Colab session name before first provisioning as its skill requires. Source access and storage capacity must be ready before moving private material.
2. **Bootstrap or activate:** Phase 0 may create a Codespace from the repository's default environment and record its actual OS/Python/GH versions; a locked project environment does not exist yet. From Phase 1 onward, restore the pinned environment. For later phases, inspect existing sessions first, reconnect/start the suitable one, or create one only when needed. For CPU use Codespaces; for GPU use a named Colab runtime. Record the actual provider-generated ID, SSH target, workspace and hardware. Do not treat an alias as proof of a live machine. Confirm no run already owns that worker/branch before starting another.
3. **Restore and execute the entire phase:** verify the worker checkout, restore the locked environment and private artifacts, then run every task and acceptance check listed for that phase. A successful SSH login is not phase completion. Before launching the job, freeze an immutable launch snapshot of the exact execution tree — the worker commit or, for a dirty tree, a retained patch bundle plus content hash, including any untracked files the work depends on — so the recorded code identity cannot drift from what actually runs. When code changes on a worker, commit them on a local result branch before producing a results record or retain a Git bundle/patch and content hash. Transfer Codespaces changes with `gh codespace cp`; transfer Colab changes over its established SSH bridge. The controller verifies the transferred code identity against the recorded execution tree before publishing results. Transfer code and small manifests only; raw Pi logs and model artifacts use the private artifact path.
4. **Track the job, not only the SSH session:** assign a stable `job_id`; record its remote process/provider handle, start time, heartbeat/last progress, log path and eventual exit code in the private run record. Use the worker's supported persistent process/job mechanism and test it in Phase 0. On SSH loss, inspect both provider session status and that job record/log before reconnecting. Resume the live job or the first incomplete milestone; do not launch a duplicate based only on a failed SSH connection.
5. **Preserve and publish:** save reports and, where relevant, full training recovery state; verify a private durable copy independent of the active runtime. Collect sanitized results on the controller, update STATE.md/manifests, commit explicit paths, push, and verify the remote SHA with the `gh-cli-ops` workflow. The controller is the default GitHub writer; credentials remain outside the candidate grader.
6. **Stop and hand off:** stop the Codespace or Colab runtime using its skill workflow, verify the provider reports it stopped, and record the next action and stop evidence. After verified shutdown, the controller publishes a small state-only closeout commit containing sanitized stop evidence; the phase is complete only when this final state checkpoint is synchronized. GPU phases release their GPU before later CPU reporting. Stop Codespaces rather than delete them by default; retained storage still needs capacity/retention monitoring.

Record interrupted work as interrupted, including its latest verified checkpoint and actual live/stopped/unknown machine and job state. A disconnect first triggers a status check and reconnect attempt; never duplicate a possibly running job. Before launch, record the provider-documented session lifetime/idle limits, configured teardown behavior, controller wall-time/spend ceiling and checkpoint interval. Test teardown behavior in the phase smoke checks. Colab's `--rm` can stop a runtime when its SSH bridge exits, so test this behavior and prove checkpoint recovery before using it for a long training job. A timeout or watchdog must stop the session at the budget deadline even when the controller is unreachable — the mechanism must live on the worker or provider side; if it cannot, do not launch that paid run. On publication failure, retry within the frozen deadline; before that deadline, copy artifacts to the controller-side private `artifacts/` directory and verify hashes. If the provider or network fails, use the pretested emergency copy path, stop the machine by its deadline, and record `publish_pending`/`closeout_pending`; never mark complete. Do not assume `/content`, a Codespace disk, or a Modal mount alone is a complete recovery record.

Both Codespaces and Colab must pass the runner-capability contract. Their SSH login environment is not the candidate-script sandbox. If a preferred provider fails a capability check, record the failing test and decide whether the Modal fallback is eligible before launching it; the fallback is tested against the same grading contract. An incompatible grader never falls back to unrestricted execution.

## Phase map and acceptance evidence

| Phase | Compute / skill to activate | Entire-phase work after activation |
|---|---|---|
| 0 | CPU Codespace / `gh-cli-ops` | Complete runtime preflight and orchestration smoke checks, record readiness evidence; Pi source preflight deferred to pre-Phase 3 |
| 1 | CPU Codespace / `gh-cli-ops` | Implement and verify grader, five exercises and diagnostic suite |
| 2 | Colab GPU / `colab-ssh-setup` | Prove E4B compatibility, shared train/evaluate paths and untouched baseline |
| 3 | CPU Codespace / `gh-cli-ops` | Audit available Pi sources, then build, review, split and audit authored tasks with viable Pi-derived additions |
| 4 | Colab GPU / `colab-ssh-setup` | Execute screening, grade candidates and apply readiness thresholds |
| 5 | CPU Codespace / `gh-cli-ops` | Freeze dataset/configuration, restore artifacts and prepare GPU handoff |
| 6 | Colab GPU / `colab-ssh-setup` | Run pilot, prove recovery, compare validation and record proceed/revise decision |
| 7 | Colab GPU / `colab-ssh-setup` | Execute bounded main run, validate and preserve selected checkpoint |
| 8 | Colab GPU then CPU Codespace / both skills | Execute matched evaluation on Colab; complete analysis/release reporting on Codespaces |

Every row includes the mandatory lifecycle above: activate → restore → execute full phase → verify → preserve → commit/push → stop → publish shutdown evidence. Phase 8 completes both machines' relevant work and shutdowns before final closeout.

**GPU provider note (2026-10-23, user-approved; supersedes Colab-first routing):** GPU phases run on RunPod and Modal via `runpodctl` skills + `modal-deploy-ssh`, chosen per run for cost and availability (L4/A40 class; ~$0.59/h RunPod, ~$1.3–1.6/h Modal L4); Google Colab (`colab-ssh-setup`) is the fallback. Phase 4 executes as a hybrid: screening stage 1 on Modal within its $12 promotional credit, the stage-2 tail on RunPod. The same Linux grading contract (isolation proof before model work) applies on every provider.

### Phase 0 — Repository and evidence contract

**Machine activation and full execution:** Activate/reconnect the CPU Codespace with `gh-cli-ops`; complete the runtime-capability, storage and orchestration smoke checks there, then publish sanitized evidence and stop the Codespace; the Pi source preflight is deferred to a pre-Phase 3 re-run under the authored-first decision (STATE.md). Repository setup is already complete.

**Files:** README.md, PLAN.md, STATE.md, AGENTS.md, docs/DESIGN.md, docs/HANDOFF.md, .gitignore; readiness evidence in `reports/runtime-capabilities.md` and `reports/orchestration-smoke.md`. Source-audit evidence belongs to Phase 3.

- [x] Establish the repository and planning/state/handoff documents; repository subsequently made public at the user's request.
- [x] Commit, push and verify the initial planning checkpoint.
- [x] Review the deeper measurement and recovery contract in this revision; verify publication separately after committing.

- [ ] Select `artifacts/` as the initial ignored controller-side handoff directory; check available capacity and record the Phase 0/1 output estimate. Keep the existing independent durable-storage choice as a prerequisite before the first GPU run.
- [ ] Bootstrap Phase 0 from the Codespace's default environment with no project lock. Record actual base image/OS and CLI/Python versions; create no GPU resources. From Phase 1 onward, use the pinned CPU environment/image defined there.
- [ ] Define the runner's host requirements before selecting an engine: Linux architecture, namespaces/resource limits, unprivileged execution, fixture/result transport, external verifier access, and availability on GitHub Codespaces and candidate Colab GPU runtimes; record whether a Modal fallback would be compatible. Use a pinned Linux/amd64 grading image as the initial cross-machine target; macOS development may use emulation. Record capability/transport decisions in `reports/runtime-capabilities.md`, record image digest per architecture, and run fixture parity checks if this target changes. No GPU allocation is required for the initial capability contract; verify actual Colab capabilities when Phase 2 activates the GPU runtime.
- [ ] Run an orchestration smoke check from the CPU Codespace: capture the exact Git SHA; execute a harmless command that writes a tiny sentinel and a machine-readable exit record; disconnect/reconnect; confirm the same `job_id` and result without starting a duplicate; copy the sentinel and record to the controller; compare hashes; push a sanitized smoke-evidence commit without marking the whole Phase 0 complete; stop the Codespace; publish/verify the state-only closeout commit. Also simulate an interrupted artifact upload and failed Git push on the tiny fixture; prove that partial copies are not marked verified and `publish_pending`/`closeout_pending` recover without rerunning the job. Also simulate controller unavailability: prove the selected deadline mechanism still stops the worker without the controller, and that the private run journal has a recoverable copy outside the single controller directory. Record the verified persistent-job mechanism and commands in `reports/orchestration-smoke.md`.
- [ ] Retrieve each skill revision by its recorded source revision/hash and perform a dry-run/read-only check of provider identity, session selection and stop command before first use. If the revision is unavailable or changed, review the replacement and record a new run contract before proceeding.

**Gate:** Repository setup is complete; the host-capability, storage and CPU orchestration smoke checks remain unstarted, and the Pi source preflight is deferred to a re-run before Phase 3 under the authored-first decision (STATE.md). Reuse the existing public repo. Phase 1 code begins after the gating checks and the five-exercise contract below are recorded.

### Phase 1 — Prove the CPU grader before trusting rewards

**Machine activation and full execution:** Activate/reconnect the CPU Codespace with `gh-cli-ops`; execute the full grader/exercise/diagnostic phase, verify its gate, preserve results, publish the milestone and stop the Codespace.

**Files:** `pyproject.toml`, `src/shell_grpo/{contracts,runner,fixtures,verifiers,rewards}.py`, `configs/runner.yaml`, `containers/grader/Dockerfile`, `tests/test_runner.py`, `tests/test_rewards.py`, `data/examples/diagnostics.jsonl`.

**Interface:** Specify versioned `TaskRecord` and `GradeResult` schemas in `contracts.py` before runner code. `grade_script(task_id: str, script: str, seed: int) -> GradeResult` derives the task's declared fixture-seed set from the supplied group seed. `GradeResult` contains schema/task/group/candidate IDs, script and fixture hashes, named check results, critical violations, per-fixture statuses/scores, aggregate execution status, nullable task score, and artifact references. Each execution status is one of `ok`, `invalid_script`, `runtime_error`, `resource_limit`, or `infrastructure_error`. Use the status and score precedence below; status describes execution, while named checks and the task score describe correctness. Freeze example task/result records and invalid-record checks before implementing execution.

**Initial five exercises:** All prompts require one Bash script, specify argument conventions and allowed changes, and run with a fixed locale/toolset. The exact prompts, input bytes, expected outputs, and intentionally wrong scripts are Phase 1's first documentation deliverable.

| ID | Exercise and invocation | Required outcome / critical checks |
|---|---|---|
| D01 | Count regular `.txt` files directly inside directory argument 1 | Print decimal count and newline; no recursion or symlink following; preserve all files; test empty input, spaces/newlines and leading dashes |
| D02 | Copy regular `.log` files recursively from argument 1 into empty destination argument 2 | Preserve relative paths and file bytes; skip symlinks; preserve source and unrelated files; test nested duplicate basenames |
| D03 | Aggregate two-field TSV input from file argument 1 | First field is a nonempty tab/newline-free key, second a nonnegative decimal integer; print one key/sum pair per key in C-locale key order; preserve input |
| D04 | Repair a supplied file-copy script using source/destination directory arguments | Correct quoting, option handling and exit-status propagation; copy direct regular files including spaces/leading dashes, skipping symlinks; preserve source; specified invalid arguments must fail without mutation |
| D05 | Repair a supplied two-stage log filtering/counting script with input-file argument 1 | Count lines containing the case-sensitive literal substring `ERROR`; print zero for no matches, but fail on missing/unreadable input; preserve input and propagate actual processing errors |

**Reward examples:** D02 earns 1 only when every selected file is copied correctly and constraints hold. Copying a proper subset earns its fraction of required files copied; no copy on a nonempty fixture earns 0. Source damage, extra selected files, or destination paths outside the stated contract earn 0 regardless of progress. Preservation is a gate, never a positive reward component. An empty-input fixture may legitimately require no changes; every exercise also includes a nonempty fixture that defeats vacuous success.

| Exercise | Positive reward rule | Zero-reward / critical examples |
|---|---|---|
| D01 | Fraction of fixture cases with exactly correct count and output format; full reward requires all cases | No output, wrong counts on every case, input mutation, or unusable execution |
| D02 | Fraction of required files copied with exact relative path and bytes, averaged across fixtures | No progress on nonempty inputs, source damage, extra files or out-of-contract writes |
| D03 | Fraction of expected keys with correct totals; full reward also requires sorted output and exact key set | No correct key totals, fabricated/extra keys, input mutation or unusable execution |
| D04 | Fraction of required files copied correctly; full reward requires all success and invalid-argument fixtures | Source damage, symlink copying, mutation on invalid arguments, or no functional progress |
| D05 | Fraction of valid-input cases with correct count/output; full reward requires every case | Missing/unreadable input incorrectly accepted, input mutation, no correct outputs, or unusable execution |

For multi-fixture exercises, specified expected nonzero exits (such as invalid arguments in D04) are successful checks, not runtime failures. A fixture-level `invalid_script`, `runtime_error`, or `resource_limit` contributes zero for that fixture; other scored fixtures retain their declared contributions. An `ok` execution may still fail behavioral checks.

Aggregate execution status is the first status present in this precedence order: `infrastructure_error`, `invalid_script`, `resource_limit`, `runtime_error`, `ok`. Any unresolved infrastructure error makes the task score null and invokes the retry/group-halt protocol, even if other fixtures have scored results. Once every fixture is scored, a task-critical violation or no required functional progress on the declared nonempty fixtures makes the task reward zero; otherwise use the declared weighted fixture/check average. Thus `[ok, runtime_error]` has aggregate status `runtime_error` and may earn partial reward, while `[ok, infrastructure_error]` is unscorable. A successful empty fixture alone cannot give a no-op positive task reward. Full reward requires every required check across all fixtures to pass. Freeze denominator/weight rules, empty-input handling and output-order checks with example records before acceptance.

- [ ] Lock a CPU environment independent of CUDA dependencies. Select a Linux runtime that can enforce unprivileged execution, no network/host mounts/credentials/socket, external grading, and bounded processes, memory, time, storage and output.
- [ ] Implement task/result validation and fresh per-candidate fixtures. Fix utility versions, locale and timezone; do not assume a container freezes time.
- [ ] Write and review the five exact prompts, invocation examples, schema examples and reward tables — including worked boundary cases: an empty-input fixture that legitimately passes while a no-op still fails the nonempty fixture; D03 with every total correct but the output unsorted; D04 copying correctly yet mishandling the invalid-argument fixtures — before runner implementation; then complete five exercises end to end before adding more. Each must accept a reference plus an alternate solution, reject relevant semantic errors/no-op/hard-coding, and repeat identically three times.
- [ ] Check descendant cleanup, grader protection, isolation between candidates, timeouts and infrastructure-error reporting. Candidate execution is always inside the restricted runner.
- [ ] Define the scoring failure protocol: fixture-level candidate syntax/runtime errors and enforced time/memory/process/output limits contribute zero for that fixture; task reward and status follow the aggregation rules above. A genuine infrastructure error retries the exact saved script/fixture up to two additional times without generating a replacement. Do not update the policy until the entire group is scored. If retries fail, invalidate the whole group, persist it, and halt the run for infrastructure repair; do not silently drop candidates or select a replacement group. A resumed run records its unchanged policy checkpoint and whether the invalidated group is replayed.
- [ ] Build approximately 20 diagnostics covering the three initial families. Store check-level evidence and fixture hashes; mark these as authored diagnostics rather than Pi-derived data.

**Gate:** Every accepted exercise meets the positive/negative/repeatability checks. If the grader is ambiguous or insecure, repair it on CPU. Close milestone with report, state update, commit, push and remote verification.

### Phase 2 — Prove E4B compatibility and measure the original model

**Machine activation and full execution:** Activate/reconnect the named Colab GPU runtime with `colab-ssh-setup`; complete compatibility and baseline work, preserve its locks/rollouts/evidence, publish through `gh-cli-ops` and stop Colab.

**Files:** `configs/{model,baseline}.yaml`, `scripts/check_compatibility.py`, `src/shell_grpo/{generate,evaluate,train,manifests}.py`, `scripts/evaluate.py`, `environments/gpu.lock`, `reports/baseline-diagnostics.md`.

- [ ] Use Colab as the first GPU provider with the **L4 (24GB)** accelerator as the working expectation — E4B LoRA/RL needs ~17GB VRAM, exceeding the free T4 — funded within the $10/month ceiling via Colab Pro/PAYG compute units (burn rate measured at activation; the free T4 covers ≤16GB workloads and E2B remains the documented emergency fallback). Confirm the session name, spending/time ceiling and private durable storage. Verify the host supports the Phase 1 runner before loading weights.
- [ ] Before model generation, run the Colab sentinel as a **separate smoke subrun** with its own mini-lifecycle: activate the runtime, confirm `job_id`/exit record survives a disconnect/reconnect, copy its private output to the controller and verify its hash, test the selected `--rm`/stop behavior, stop Colab, and publish the sanitized shutdown closeout. Then activate/restore again for the actual phase work below. Record Colab's tested job-persistence mechanism in `reports/orchestration-smoke.md`.
- [ ] Map the deployment alias/digest to a precise upstream training checkpoint/tokenizer revision. Record precision, template, thinking mode, limits and decoding settings. Verify a fresh adapter does not change the initial baseline beyond documented numeric tolerance.
- [ ] Introduce minimal shared `generate.py`, `evaluate.py` and `train.py` entry points now. Baseline, screening, pilot and main runs reuse their output extraction, task iteration, generation settings and scoring failure protocol. The compatibility probe uses the same training path as the later pilot, with tiny limits. Follow the documented conservative Unsloth/TRL path first. On a few diagnostics, demonstrate finite gradients, a nonzero trainable-parameter update, correct prompt/candidate/reward alignment, and adapter save/reload. Do not use an SFT adapter.
- [ ] Check all candidates in a prompt group receive identical fixture seeds on independent copies. Record generation/grading wall time, peak VRAM and CPU utilization; select hardware from measurements, not model-name size alone.
- [ ] Produce a per-task/per-candidate evaluation record with model/config/fixture hashes, the raw completion, the extraction outcome (success/failure and what was extracted), the policy/checkpoint step it came from, the complete script, score/checks, status, truncation and timing. Preserve raw completions privately. Use this evaluator for all later validation and test comparisons. Reload the untouched original policy in a separate process for baseline measurement. Inspect extraction/runner defects, template/truncation/precision issues, then shell errors. Keep deployment-runtime findings distinct from upstream-checkpoint findings.
- [ ] Test an accelerated rollout path only if needed and supported. Compare unchanged-policy outputs/log-probability behavior within declared tolerances before relying on it; the project can proceed on the proven conservative path.

**Gate:** A tested lock and original-model weakness report exist. Unsupported stack combinations halt here. Upload/verify evidence, commit/push the report, then release GPU resources.

### Phase 3 — Audit sources and build the reviewed task bank on CPU

**Machine activation and full execution:** Activate/reconnect the CPU Codespace with `gh-cli-ops`; audit available Pi sources before dataset construction, complete the selected authored-only or mixed-source path, checks, splits and audit, preserve the private dataset, publish sanitized evidence and stop the Codespace.

**Files:** `src/shell_grpo/{task_builder,splits}.py`, `tests/test_splits.py`, `configs/dataset.yaml`, `reports/{source-preflight,dataset-audit}.md`; add `src/shell_grpo/pi_sessions.py` and `tests/test_pi_sessions.py` only for a viable Pi extraction path.

**Authored-first branch:** Under the authored-first decision (STATE.md), the Pi extraction path (`pi_sessions.py` and private raw-log staging) is implemented only if the pre-Phase 3 source preflight yields a viable corpus. Authored tasks carry `source: authored` provenance with authoring rationale, pass the same acceptance checks, and enter the same connected-component grouping — a shared task template links authored exercises exactly as a shared source episode links Pi-derived ones. If a partial Pi corpus exists, Pi-derived and authored tasks coexist with distinct, honest provenance labels.

- [ ] Run the deferred CPU-only source preflight before constructing the dataset: inspect up to ten privately staged, user-designated Pi sessions and seek at least five plausible exercises across the initial categories. Record schema versions, command/tool evidence, missing filesystem state, reconstruction effort and exclusions in `reports/source-preflight.md`; publish sanitized counts/provenance hashes only. Metadata-only session counts do not establish exercise yield. If the corpus is insufficient, use the already selected authored-only fallback without reopening the scope decision.
- [ ] For viable Pi sources, inventory private logs, versions and source projects without committing their contents. Preserve source hashes and branch/entry provenance; reconstruct relevant context, model changes, tool results, corrections and compaction. Mark this extraction work not applicable for the authored-only path.
- [ ] Author or extract tasks matching measured weaknesses. Label origins, reconstructed fixtures and exclusions honestly. Treat embedded instructions as source material. Remove secrets/private material from derivatives.
- [ ] Curate toward 50–100 distinct candidate exercises if available. Require explicit prompt assumptions, invocation arguments, allowed changes, fixtures and named behavioral checks. A model may assist authoring; no generated answer becomes a training target.
- [ ] Apply Phase 1 acceptance checks to every exercise. Gates enforce preservation; positive reward measures required functional progress. Ensure no-op and example-specific hard-coding cannot earn high reward.
- [ ] Build a relationship graph linking common source episodes, forks/branches, paraphrases, task templates and diagnostic derivatives. Assign connected components wholly to one split before creating variants; audit duplicate text and shared solution patterns. Diagnostic exercises and their derivatives belong to the development pool and are excluded from the final unseen test set.
- [ ] Target grouped train/validation/test proportions of 60/20/20, preserving components and reporting actual counts rather than splitting related examples to meet percentages. Reserve independent test fixtures and task families. Lock a small known-good shell regression subset from baseline successes inside validation; retain it for every policy comparison. Never select final-test membership from test model scores.

**Gate:** Reviewed tasks have repeatable rewards, traceable provenance, no hidden scored requirements, and no detected source/family leakage. Persist the audit and dataset references; commit and push.

### Phase 4 — Screen training difficulty with the untouched policy

**Machine activation and full execution:** Activate/reconnect Colab GPU with `colab-ssh-setup`; run all screening and grading, preserve candidate/selection evidence, publish through `gh-cli-ops` and stop Colab.

**Files:** `scripts/screen_tasks.py`, `configs/screening.yaml`, `reports/screening.md`.

- [ ] Restore the Phase 2 runtime and Phase 3 data. Start with eight candidates per training prompt; candidates share fixture seeds but receive fresh state.
- [ ] Measure full-pass rate, functional progress, reward variation, truncation and scoring coverage. Inspect all-equal groups instead of assuming training will fix them.
- [ ] Freeze screening thresholds before sampling: start with eight candidates per task and confirm apparently informative tasks with a second independent group seed. A useful group has at least two different functional rewards. The initial readiness heuristic requires at least 25% of screened training tasks to produce useful groups in both screenings, with at least five independent task families and coverage of each retained task category. These are operational pilot thresholds, not guarantees of learning. Prefer mixed-outcome training tasks, retain easy coverage and keep harder tasks as a reserve. Simplify impossible training tasks or repair faulty graders; issue a new version if semantics change. Do not screen final-test tasks.

**Gate:** The predeclared informative-task proportion, family count, category coverage and scoring coverage are met. Every attempted candidate has a scored outcome or an explicitly halted infrastructure failure; the latter does not count as a low-reward response. Otherwise revise tasks or runtime before training. Upload/verify evidence, commit/push, then release GPU resources.

### Phase 5 — Freeze the CPU release and decision rule

**Machine activation and full execution:** Activate/reconnect the CPU Codespace with `gh-cli-ops`; complete packaging, configuration freeze and restoration checks, preserve the release, publish its manifest/handoff and stop the Codespace.

**Files:** `scripts/package_dataset.py`, `configs/grpo-{pilot,main}.yaml`, `manifests/dataset-v1.json`, `reports/dataset-card.md`.

- [ ] Release immutable prompt/split records, fixture generators, verifier bundle, image digest and hashes; store payloads externally and manifests in Git. Grader-only fields never enter policy prompts.
- [ ] Freeze the tested E4B script extraction contract, fixture seed schedule, rewards and per-task weights. Syntax/formatting alone earns no reward. Check actual sampled E4B outputs against the extractor.
- [ ] Declare the first 50–100-exercise release exploratory by default. Freeze evaluation task/component counts, split proportions actually achieved, number of generation repetitions, matched inference settings and paired task-level analysis before training. Average repetitions within task, then bootstrap independent connected source/family components. Report too-few-component uncertainty explicitly; do not treat fixture variants as extra independent evidence.
- [ ] Retain the proposed +5 percentage-point effect as a practical target, not a promise that the pilot can detect it. A confirmatory claim requires a precision/power assessment using development data or simulation before opening final-test outcomes, with a sufficient independent test set and the predeclared 95% interval criterion from DESIGN.md. Otherwise report an exploratory estimate, regressions and potentially inconclusive evidence. Never upgrade the claim or grow the test set in response to observed final-test scores.
- [ ] Freeze initial training sampling: sample tasks uniformly from the accepted training pool and rotate group fixture seeds; record easy/mixed/hard proportions and per-category frequencies. Do not add adaptive filtering or curriculum changes silently; a later change requires a new run/config and a repeated readiness check.
- [ ] Limit the exploratory campaign to at most three pilot configurations, one primary training seed per configuration, final-only validation selection per pilot, and five scheduled main-run validation checkpoints including the final checkpoint. Count early termination and failed configurations in the ledger. Freeze validation generation repetitions and quantitative regression/critical-violation stop thresholds before the first pilot. Log every attempted configuration, not only the selected winner. Report evidence from one training seed as conditional on that seed; method-level reliability requires separately budgeted replication.
- [ ] Set sequence lengths, candidate count, batches, adapter/KL settings and checkpoint cadence from Phase 2 measurements. Specify max steps, GPU-time/spend ceiling, stop conditions and maximum acceptable checkpoint loss before renting GPU time.
- [ ] Verify all CPU contracts from a clean checkout and rehearse dataset/artifact restoration. No test-score-driven changes are permitted after the experiment freeze.

**Gate:** Another machine can reconstruct one exact experiment from the pushed commit and hashed artifacts. Commit/push the release and GPU handoff instructions.

### Phase 6 — Train a short pilot and prove recovery

**Machine activation and full execution:** Activate/reconnect Colab GPU with `colab-ssh-setup`; execute the full pilot, interruption/recovery demonstration and validation comparison, preserve checkpoints, publish through `gh-cli-ops` and stop Colab.

**Files:** Extend Phase 2's `src/shell_grpo/train.py`; add `src/shell_grpo/checkpointing.py`, `scripts/restore_run.py`, `reports/pilot.md`.

- [ ] Start from the original policy with fresh adapters and generate on-policy candidates. Use the frozen external grader; no fixed Pi responses are substituted for model rollouts.
- [ ] Run a short budgeted pilot. Inspect updates, candidate alignment, reward variance, KL, clipping, truncation, functional pass rate, critical violations and CPU grading bottlenecks.
- [ ] Save a full checkpoint at an optimizer boundary, upload it and verify hashes. Restore from a fresh process/checkout; check trainer step, optimizer, scheduler, RNG and data/fixture state. Compare with a short uninterrupted control and document numeric tolerances/non-determinism.
- [ ] Compare pilot and untouched original on validation under equal generation budgets. Proceed only with valid grading, successful recovery and a positive functional validation point estimate without increased observed critical violations. Pilot significance is not required; rising training reward alone is insufficient.

**Gate:** All three conditions pass: real GRPO updates, demonstrated recovery, promising validation. Otherwise revise one cause and repeat a versioned pilot only within the frozen three-configuration campaign limit. Once that limit is reached, report the result and require a new documented research decision before further GPU runs. Persist report/checkpoints, commit/push, then release GPU resources.

### Phase 7 — Run the bounded main experiment

**Machine activation and full execution:** Activate/reconnect Colab GPU with `colab-ssh-setup`; execute the complete bounded main run and validation selection, preserve full recovery state, publish through `gh-cli-ops` and stop Colab.

**Files:** `manifests/runs/<run-id>.json`, `reports/training.md`; checkpoint and rollout payloads remain external.

- [ ] Declare original-policy restart or exact pilot-checkpoint continuation, with parent run and source SHA. Recheck data/runtime hashes before training.
- [ ] Train within the frozen step/time/spend ceiling. Periodically validate and upload recovery checkpoints. Stop on invalid rewards, numerical failures, persistent scoring outages or functional regressions; classify interruptions honestly.
- [ ] Select one checkpoint using validation only. Preserve completed and interrupted run lineage; do not choose by final-test performance.

**Gate:** A recoverable checkpoint and validation-based selection record exist within budget. Verify artifacts, commit/push the results/state checkpoint, then release GPU resources.

### Phase 8 — Evaluate unseen behavior and close the loop

**Machine activation and full execution:** Activate Colab GPU with `colab-ssh-setup` for all final inference/evaluation/export checks; preserve its outputs, publish the GPU submilestone through `gh-cli-ops`, and stop it. Activate the CPU Codespace with `gh-cli-ops` for final analysis, model/release documentation and reproducibility checks; publish the final handoff and stop the Codespace.

**Files:** Reuse Phase 2's `scripts/evaluate.py` and evaluator; add `scripts/export_model.py`, `reports/{final-evaluation,model-card}.md`, `manifests/release-v1.json`.

- [ ] Run original and selected policy on frozen held-out tasks under identical backend/precision/template/thinking/decoding and generation budgets. Score independent fixture copies using the same declared requirements.
- [ ] Report task-level single-attempt full-pass change, paired cluster-based 95% interval, family regressions, critical violations, scoring coverage, truncation and resource cost. Report multi-sample success separately. Use DESIGN.md's separate `effect_label`, `target_met` and `safety_pass` fields and its accepted-improvement rule; a functional gain that fails the safety constraint is not accepted improvement.
- [ ] If inference export is needed, reload and check it. Quantized/Ollama export is conditional on deployment needs and gets its own matched comparison; training-backend gains do not automatically establish deployed gains.
- [ ] Reproduce a sample result from a fresh checkout plus manifests. Preserve recovery checkpoints separately from inference adapters. Record exact next action or closeout decision in STATE.md.

**Gate:** A defensible result exists, including a negative or inconclusive result. Upload/verify artifacts, commit/push the final handoff and release remaining GPU resources.

## Current next action

Phases 0–3 are complete with recorded evidence (`reports/orchestration-smoke.md`, `reports/runtime-capabilities.md`, `reports/phase1-grader.md`, `reports/baseline-diagnostics.md`, `reports/dataset-audit.md`): the restricted CPU grader runs twenty authored diagnostics end to end in a digest-pinned image (acceptance 241/241 at `ce96da6`); seven of the ten collected Pi candidates verify through the grader; the Colab L4 compatibility probe passed with the namespace grading engine re-proving the isolation contract on a Dockerless host, `gpu.lock` frozen, and durable private HF storage live; the untouched checkpoint's reduced baseline (D01–D05 ×4) scored 0/20 full passes (mean 0.241); the Pi source preflight yielded 0/5, so the authored-only path built release `bank-v1` — 32 tasks, components kept whole across splits (11/9/12), held-out test pool T1–T6 accepted 137/137 executions at `ffd1f4d`. Next: Phase 4 — screen training difficulty with the untouched policy on the recorded 2026-10-23 GPU routing (Modal L4 for stage 1 within its credit, RunPod for the stage-2 tail; Colab fallback), eight candidates per training prompt; readiness thresholds decide which tasks enter the frozen Phase 5 plan. No training has been performed by updating this roadmap.

## Execution lessons learned (Phases 0–3)

Recorded 2026-10-22 from live execution evidence (Phase 1–3 reports, run records, STATE.md ledger). These are binding execution rules, not suggestions: each entry was an actual failure or near-miss whose prevention is now part of the contract.

### Provider operations — Codespaces

- `gh codespace ssh` does not preserve quoting on multi-word remote commands. Worker scripts travel as base64 on stdin: `base64 < script | gh codespace ssh -c NAME -- 'base64 -d | bash'`.
- `gh` has no `codespace start` (ssh auto-starts a stopped Codespace). `gh codespace cp` requires the `remote:`/`local:` prefix and has failed even then; the reliable transfer is streaming: `gh codespace ssh -c NAME -- 'base64 -w0 <remote-path>' | base64 -d > <local-path>` (works in both directions).
- An idle Codespace stop (default 30 min) kills detached processes **and wipes `/tmp`** — Phase 3's first acceptance run was lost this way. Run outputs go under `/workspaces/<dir>` (persistent across stop/start); keep a short SSH poll every few minutes to reset the idle timer; before relaunching anything, verify the old process is dead in the process table (never duplicate a possibly-running job).
- Host pytest is not worker pytest: Docker-gated tests skip on the macOS host (58 local vs 69 on the Codespace). The recorded suite must run on the execution host.

### Provider operations — Colab

- Runtimes are reclaimed when **no client is connected**, even with processes running — nohup alone is not survival. Hold a client connection (streamer/watchdog) for the whole job; records must support resume from durable storage.
- Connecting the colab CLI to an absent session name **silently auto-creates a CPU runtime**. Always create explicitly (`colab new --gpu L4`) and verify the accelerator before work.
- Expect a ~60 s SSH-slot cooldown (HTTP 429) after an unclean disconnect. Colab sessions are not resumable like Codespaces — every activation re-creates the runtime, so durable storage must run first.
- Sync raw completions on the same cadence as records: a recycled runtime lost the final baseline run's raw completions (extracted scripts survived in records).
- `hf upload` creates the target repo **public** by default. Flip it private and verify anonymous access returns 401 before uploading anything model-related.

### Task-bank authoring and acceptance (grader contract)

- An error-expecting fixture must declare the failure in its **GroundTruth** (`expects_failure`/`expected_exit`, the `_err` idiom), not only in the verifier: a success-declaring GroundTruth makes the engine classify the script's *correct* nonzero exit as `runtime_error` before the verifier runs.
- When reference AND alternate fail together, suspect the **fixture data** first: a trailing blank line changed "last line" semantics so the authored expectation was wrong while both scripts were right (T5a).
- Wrong-script expectations follow the recorded taxonomy: `zero` only for no-progress or critical-violation wrongs; hardcoded or partially-compliant scripts legitimately earn **partial** (observed ceilings: hardcode 0.7, validation-skipping 0.85 — full reward stays unreachable, which is the actual requirement).
- An anti-pattern must be **deterministically observable**: order-dependent flaws (e.g. `find -L` deleting a symlink's target before the symlink is visited) can pass by readdir luck. Model the flaw so a survivor/anti-mutation check trips regardless of traversal order.
- bash pitfalls that pass `bash -n` and synthetic unit tests: `case "$x" in *'\t'*)` matches the literal two characters backslash-t (use `$'\t'`); `globstar` (`**`) **silently descends directory symlinks**; `all(<single boolean>)` in a verifier is a TypeError. Only real grader execution catches these — host tests with synthetic verify-contexts did not.
- Grading containers stage **only the fixture workdir** (`-v instance_dir:/work`): fixture builders must not reference anything outside it — an outside-root symlink dangles in-container and a "deterministic catch" silently no-ops.
- Every new task family runs the full acceptance harness (reference/alternate ×3 repeats byte-identical, wrongs vs declared expectations) at the exact published commit before the bank is trusted — `bank.jsonl` does not embed wrongs/fixtures, so behavior is pinned by the code commit, and bank-v1 needed three acceptance rounds to get there (findings enumerated in `reports/dataset-audit.md`).

### GPU / model stack (Gemma 4 + Unsloth/TRL)

- `Gemma4Processor` takes text **only as a keyword** (`text=`) — the first positional parameter is images, and `apply_chat_template` routes text into the image path. The frozen chat template is applied manually in `generate.py`.
- Mirror pad/eos attributes onto the processor and pass `processing_class` explicitly to `GRPOTrainer` (pad_token_id AttributeError otherwise).
- Gemma 4 RL requires `fast_inference=False` (no vLLM path); `use_cache=True` is mandatory at generation; the thinking channel consumed all 512 tokens, so evaluation budgets are ≥1024 and prefer 2048 (truncation dominated D02 at 1024).
- Dockerless GPU hosts: the namespace engine (`ns_exec.py`) replaces Docker — user+net namespaces with a direct `/proc/<pid>/uid_map` write from the real-root parent. This kernel forbids fork inside a non-init PID namespace (child forks ENOMEM), so **no PID namespace**; bwrap cannot nest user namespaces and util-linux `--map-users` drops the caller from its own map.

### Publication and hygiene

- Four GitHub accounts are logged in on the controller; confirm the active account is `rajivmehtaflex` before any push.
- Compute every published number with code, never copy-forward — a report mean had to be corrected (0.28 → 0.241) after being carried between drafts.

## Review findings addressed

### Execution-orchestration findings

| Finding | Planning resolution |
|---|---|
| Worker executes code newer/different than the source SHA | Record base SHA plus executed worker commit or retained patch/content hash; transfer and verify exact code before publishing results |
| SSH disconnect is confused with a stopped or live job | Record stable `job_id`, remote process/provider handle, heartbeat, log and exit status; inspect them before resuming |
| Upload/push failure conflicts with shutdown and spend limits | Bound retries by provider timeout and controller spend deadline; use a pretested private emergency copy and keep publication/closeout pending until synchronized |
| Completed work is repeated when only closeout failed | Track phase state and artifact/publish/stop/closeout milestones separately; resume the first incomplete milestone |
| Artifact storage is selected after early CPU handoffs | Establish ignored controller-side `artifacts/` capacity in Phase 0 and choose independent durable checkpoint storage before Phase 2 |
| First Codespace has no pinned project environment yet | Specify Phase 0 bootstrap on its default image, record actual versions, pin the CPU environment in Phase 1, and restore from Phase 1 onward |
| Skill hash cannot restore changed instructions | Record retrievable skill/script revisions and define validation/new-run handling if the revision is unavailable |
| Orchestration lifecycle is not tested as a whole | Phase 0 tests a harmless Codespaces sentinel through reconnect, transfer, hash, push, stop and closeout, including failed-upload recovery; Phase 2 repeats the runtime check for Colab |

### Earlier experiment-design findings

| Finding | Planning resolution |
|---|---|
| 1–2: Training/evaluation dependencies | Shared minimal train/generate/evaluate paths introduced in Phase 2 and reused thereafter |
| 3: Late source feasibility | CPU-only representative source audit, deferred to a pre-Phase 3 re-run under the authored-first decision |
| 4: Unscorable candidates | Bounded same-candidate retries, group-wide invalidation and halted updates on persistent infrastructure failure |
| 5: Cross-machine runner | Capability/architecture/transport contract before selecting the engine |
| 6–7: Exercise/schema/reward ambiguity | Five named exercises, typed result contract and mandatory reward examples in Phase 1 |
| 8: Weak screening gate | Predeclared informative-task/family/category thresholds and fixed initial sampling policy |
| 9: Overlapping splits | Connected-component grouping and diagnostic-derivative exclusion |
| 10: Evaluation size and claims | Exploratory default; predeclared independent test size/repetitions and confirmatory precision assessment |
| 11: Repeated selection and regression | Fixed campaign/validation limits, complete trial ledger and known-good regression subset |
| 12: Repository visibility | Public repository status recorded; historical private creation remains history |

These are planning resolutions, not evidence that their implementation gates have passed. Refine the active phase only; update supporting contracts when that phase's executable design is reviewed.
