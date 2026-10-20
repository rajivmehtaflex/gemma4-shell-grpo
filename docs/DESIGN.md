# Shell GRPO design

Updated: 2026-10-20

## Agreed outcome

Discover shell scripting weaknesses in the original Gemma 4 E4B, construct a task dataset starting with authored exercises, and apply GRPO directly. Add Pi-informed tasks if the source audit before Phase 3 supports them; otherwise retain the authored-only path. Compare the resulting policy with the untouched starting checkpoint on held-out tasks. Work across CPU and GPU machines with pushed Git checkpoints between milestones.

## Initial scope and assumptions

- Begin with one generated Bash script per task, followed by external execution and grading. Multi-turn Pi agent training is a later extension.
- Use a fixed Linux image with Bash and an explicitly declared utility set. CPU development may happen on macOS; scored behavior comes from the Linux image.
- Start with local filesystem/text tasks. Exclude live accounts, network-dependent tasks, and unreconstructable repository state from the pilot.
- The proposed starting point is the original Gemma 4 E4B instruction checkpoint, resolved to an exact upstream revision during compatibility work. The name `gemma4:e4b` is a deployment label; it does not establish the training checkpoint, precision, or template.
- Direct GRPO can train fresh LoRA adapters; no previously trained/SFT adapter is introduced. Adapter targets and hyperparameters are decided from compatibility evidence.
- Proposed fast stack: Unsloth + TRL with fresh text LoRA adapters for direct GRPO. Establish the documented `fast_inference=False` path first; an accelerated rollout backend is optional and requires separate parity and training evidence. This is a proposed implementation, not a measured E4B configuration.

## Execution routing

The controller prioritizes GitHub Codespaces through `gh-cli-ops` for CPU phases and Google Colab through `colab-ssh-setup` for GPU phases. Phase 8 uses Colab for model evaluation and Codespaces for reporting. `modal-deploy-ssh` is an explicitly selected fallback. Each phase includes machine activation/reconnection, execution of every phase task and acceptance check, verified private artifact preservation, reviewed Git publication and confirmed shutdown. The controller is the default GitHub writer; worker-side publication requires recorded ownership and scoped authentication. Source/credential access, resources and spending limits are checked before allocation, and the Colab session name is confirmed before first provisioning. Every provider must enforce the same restricted grading contract; neither an SSH login nor an outer cloud sandbox alone establishes candidate isolation. See PLAN.md for per-phase routing and HANDOFF.md for provider lifecycle/recovery details.

## Research question and independent evidence

Question: under a fixed inference budget, does direct GRPO improve the original E4B instruction checkpoint's ability to produce correct Bash scripts on unseen exercises within the declared filesystem, text-transformation and script-repair scope? Record the actual authored/Pi-derived composition of the released task bank; an authored-only result does not establish transfer to real Pi workflows.

The original instruction checkpoint already includes its upstream instruction training. "No SFT" means no additional SFT stage or previously trained adapter in this project; it does not mean switching to a pretrained-only checkpoint.

A specialist would establish the measurement before optimizing the policy. Authored exercises start from an explicit task brief, initial files/bytes/modes and independently checked expected behavior; record `source: authored`, rationale and shared-template lineage. For Pi-derived additions, raw evidence includes the session JSONL branch, original user requirements, command arguments, tool outputs, source model/runtime settings and initial filesystem state. Compaction summaries and successful-looking assistant answers are discovery aids, not correctness labels. Preserve immutable raw sources privately, create sanitized derivatives, and mark reconstructed environments as reconstructed rather than historical snapshots. If original state is missing, reproduce the behavior in a new, explicitly authored fixture or exclude the task.

An exercise is accepted only when a reference solution and at least one different valid implementation pass, plausible incorrect variants fail, and the same script/fixture produces the same result on three clean repetitions. Wrong variants include an empty script, a hard-coded example answer, and a relevant semantic error such as unquoted filenames or wrong file selection. A task whose correct response can be empty must also be checked on a declared nonempty case. Hashes, exit codes, filesystem comparisons, and independent expected-output calculations provide the evidence; an LLM's approval is insufficient.

Keep the first pilot narrow: local file selection/quoting, deterministic text transformations, and repairs of short scripts. The approximately 20 diagnostics and 50–100 candidate exercises are feasibility targets, not claims of adequate statistical power. Start by perfecting five end-to-end exercises. No network accounts, full agent trajectories, distributed reward service, or large dataset expansion is required for the pilot.

## Task contract

Each task record contains `task_id`, `family_id`, `source_cluster_id`, `prompt` (role/content messages), `fixture_id`, `verifier_id`, `invocation`, `split`, `provenance`, and a schema version. `invocation` is an argument list, not a command string interpolated through another shell. Environment and verifier references are grader metadata, not hidden requirements supplied to the policy. All requirements the verifier scores appear in the prompt, including Bash/utility assumptions, argument conventions, allowed changes, and output requirements.

A fixture definition specifies input files, bytes, modes, timestamps, working directory, allowed output paths, and generation seed. Every rollout receives a fresh instance. All candidates in one GRPO group use the same fixture set and seeds; vary fixtures between groups to avoid comparing candidates on different difficulties. Record the Linux image digest, installed tools, locale, and timezone. Defer wall-clock-dependent tasks from the first pilot. A later time-based task must explicitly define its reference time and invocation; containers alone do not freeze the clock.

The initial output contract is one Bash script in one fenced `bash` block in the final response. Use the checkpoint's native template/thinking configuration. Extract only the declared final-answer script, reject missing/multiple blocks, and never execute reasoning or other output text. Test extraction against actual E4B output before freezing the contract. Do not add the Gemma 3 notebook's custom reasoning tags merely to reproduce its format reward.

A verifier reports named behavioral checks, critical invariant violations, per-fixture scores/statuses, aggregate execution status and task score. It lives outside candidate-writable paths. Valid alternate implementations must pass. Incorrect scripts and deliberate grader bypass attempts must fail. Each execution status is one of `ok`, `invalid_script`, `runtime_error`, `resource_limit`, or `infrastructure_error`. Fixture-level candidate syntax/runtime errors and enforced time/memory/process/output limits contribute zero for that fixture; other fixtures retain their declared contributions. Aggregate status is the first present in this order: `infrastructure_error`, `invalid_script`, `resource_limit`, `runtime_error`, `ok`. Status describes execution, not correctness: `ok` can fail checks, and aggregate `runtime_error` can accompany a partial task reward. Any unresolved infrastructure error makes the task score null. Retry the exact saved script/fixture up to two additional times; if retries fail, invalidate and persist the whole group and halt for repair. The policy is never updated while a group is partially scored, candidates are never silently replaced, and infrastructure failures are not model failure labels.

Initial reward: while any fixture has an unresolved infrastructure error, the task is unscorable and cannot update the policy. Once every fixture is scored, a task-critical invariant violation or no required functional progress on the declared nonempty fixtures makes task reward zero; otherwise use the normalized declared weighted fixture/check average, capped at one. Preservation constraints are gates, not a source of positive reward for doing nothing. An empty-input success alone cannot give a no-op positive task reward. Weights are specified per task before training. Full reward requires every required check across the declared fixture set to pass. Syntax, formatting, and exit code alone earn no reward. Freeze denominator, weight and boundary-case examples before Phase 1 exercise acceptance, and freeze the resulting reward version per experiment.

Generated scripts execute as an unprivileged user in a disposable Linux environment with no network, host credentials, host checkout, container socket, or verifier access. Bound processes, CPU, memory, runtime, writable storage, and output volume. Kill descendant processes and reset state after every candidate. Verify these properties on both the CPU development machine and GPU host. CPU grading may run locally beside the GPU process; a remote grading service is unnecessary. If the GPU provider cannot support the required isolation, it is not a compatible host for this runner.

Pi session extraction follows parent/branch links and preserves relevant context, source model, and tool results when available. Model switches, compaction, retries, and failed attempts require explicit handling. Sanitize secrets and private content before publishing any derived record. Reference scripts may validate fixtures and graders; they are not policy training targets.

Split by task family and source cluster before producing variants. A family is a shared solution pattern/task-generating template; a source cluster is a related source episode including forks and branches. These are finer-grained than broad categories such as file operations. Keep variants, paraphrases, branches, and closely related source tasks in the same split. Build a relationship graph over shared source episodes, forks, paraphrases, templates, and diagnostic derivatives, and assign whole connected components to one split; diagnostic exercises and their derivatives stay in the development pool and never enter the final unseen test set. Reserve held-out families to measure transfer. Do not select the final test set based on the model's test scores.

## Experimental controls and decision rule

Separate the user's deployment alias `gemma4:e4b` from the exact trainable model repository/revision. Record deployment model digest and quantization when available. Establish the untouched training-policy baseline in the same backend, precision, template, thinking mode, context/completion limits, and decoding settings as the trained-policy comparison. Diagnose failures in this order: extraction/runner, template/truncation/runtime, then shell behavior. A failed quantized deployment alone does not establish a weakness in the upstream checkpoint.

Use screening only on training tasks. Validation selects checkpoints and training settings. Lock test source clusters, families, prompts, fixture seeds, and analysis before training; do not use test outcomes for task selection or prompt tuning. An evaluation test case may be hidden, but the requirement it exercises must be stated. Independently authored held-out cases should check the same requirements, rather than merely reusing the exact training reward checks.

Primary endpoint: task-level single-attempt full functional pass rate under matched generation budgets, averaged equally over tasks. If several generation seeds are used, average within task first. Report per-family results, critical violation rate, truncation, scoring coverage, and GPU/CPU time. Multi-sample success and mean training reward are secondary measures. Use a paired task comparison with a family/source-cluster bootstrap for a 95% confidence interval; count independent clusters, not fixture variants or sampled responses, as the evidence units.

Proposed practical target to freeze in Phase 5: at least a 5 percentage-point held-out pass-rate improvement. Accepted improvement requires positive statistical evidence, attainment of the practical target and no increase in observed critical violations, as defined below. A small pilot can remain inconclusive; report the effect estimate and interval instead of expanding scope to force a positive finding. A working trainer is a technical success, not proof of model improvement. The pilot proceeds only with valid rewards, verified recovery, and a positive validation point estimate without increased critical violations; it need not establish statistical significance.

Freeze and report three separate outcome fields in Phase 5:

- `effect_label`: `positive_gain` when the paired 95% interval is wholly above zero; `regression` when wholly below zero; `inconclusive` when it includes zero (including either endpoint equal to zero).
- `target_met`: whether the point estimate meets the frozen practical target, initially at least +5 percentage points. This does not assert that the entire interval exceeds the target.
- `safety_pass`: whether the observed critical-violation rate does not increase in the matched comparison. Report the underlying counts, denominators and rates; this flag is not proof that all possible scripts are safe.

**Accepted improvement** requires `effect_label=positive_gain`, `target_met=true` and `safety_pass=true`. Otherwise report the three fields and the unmet condition; do not collapse a regression or safety failure into a generic "no improvement" label. If evaluation coverage is incomplete, withhold the outcome classification until scoring is repaired rather than treating missing outcomes as passes or failures. The rules do not change after final-test results are opened.

Examples under the proposed +5-point target (estimates and intervals are percentage points):

| Estimate / paired 95% interval | `effect_label` | `target_met` | `safety_pass` | Interpretation |
|---|---|---|---|---|
| +6 / [+1, +11], violations unchanged | `positive_gain` | true | true | Accepted improvement |
| +6 / [+1, +11], violation rate increased | `positive_gain` | true | false | Functional gain; safety constraint failed |
| +2 / [+1, +3], violations unchanged | `positive_gain` | false | true | Positive gain below the practical target |
| -4 / [-6, -2], violations unchanged | `regression` | false | true | Functional regression |
| +6 / [-1, +13], violations unchanged | `inconclusive` | true | true | Practical point target met; statistical evidence inconclusive |

## Artifact and state contract

Every run manifest records source Git SHA, config hash, model/tokenizer revisions, template/thinking settings, dependency lock hash, image digest, data release/hash, reward version, seeds, hardware, run ID, parent run, and durable artifact URIs with checksums. No credentials are stored in manifests.

Distinguish the run's source commit from the later commit recording its results. Do not put a self-referential current commit hash into a file and expect it to match the commit containing that file.

A resumable training checkpoint includes policy/adapters, optimizer, scheduler, RNG, trainer state, and data-order/sampler state where supported. Record unsupported state and any loss of exact reproducibility. Adapter-only exports are inference artifacts, not complete training recovery points.

Also persist fixture-generator state, artifact/rollout IDs, and the source run's evaluation configuration. Save at an optimizer-step boundary where possible. Test recovery from a fresh checkout/process using verified external artifacts. Compare uninterrupted and resumed short runs under the same settings; record numeric tolerance and any nondeterministic backend limitation. "Resumable" promises restored progress and documented state, not necessarily bit-identical training across different GPU architectures.

## Measures of success

- Reproducible fixtures and valid graders before training.
- Measured baseline weaknesses rather than assumed ones.
- A meaningful population of tasks with reward variation across generated candidates.
- A successful direct-GRPO pilot with changed trainable parameters and a verified resume operation.
- Better held-out functional pass rate than the original checkpoint, with uncertainty and category regressions reported under matched inference settings.

## References

- User-provided `notebook5ffcd6ec70.ipynb`: Gemma 3/GSM8K/GRPO reference; original path recorded in STATE.md.
- Pi session format: https://pi.dev/docs/latest/session-format
- GRPO trainer: https://huggingface.co/docs/trl/grpo_trainer
- Gemma 4: https://deepmind.google/models/gemma/gemma-4/
- Gemma 4 training/RL guide (checked 2026-10-19): https://unsloth.ai/docs/models/gemma-4/train
- Trainer recovery/state reference: https://huggingface.co/docs/transformers/main_classes/trainer

Fetch current implementation documentation when a phase begins. This design does not assert that a particular Gemma 4/Unsloth/TRL/vLLM version combination has been tested.
