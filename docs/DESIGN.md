# Shell GRPO design

Date: 2026-10-19

## Agreed outcome

Discover shell scripting weaknesses in the original Gemma 4 E4B, construct a task dataset informed by Pi logs, and apply GRPO directly. Compare the resulting policy with the untouched starting checkpoint on held-out tasks. Work across CPU and GPU machines with pushed Git checkpoints between milestones.

## Initial scope and assumptions

- Begin with one generated Bash script per task, followed by external execution and grading. Multi-turn Pi agent training is a later extension.
- Use a fixed Linux image with Bash and an explicitly declared utility set. CPU development may happen on macOS; scored behavior comes from the Linux image.
- Start with local filesystem/text tasks. Exclude live accounts, network-dependent tasks, and unreconstructable repository state from the pilot.
- The proposed starting point is the original Gemma 4 E4B instruction checkpoint, resolved to an exact upstream revision during compatibility work. The name `gemma4:e4b` is a deployment label; it does not establish the training checkpoint, precision, or template.
- Direct GRPO can train fresh LoRA adapters; no previously trained/SFT adapter is introduced. Adapter targets and hyperparameters are decided from compatibility evidence.
- Proposed fast stack: Unsloth + TRL with fresh text LoRA adapters for direct GRPO. Establish the documented `fast_inference=False` path first; an accelerated rollout backend is optional and requires separate parity and training evidence. This is a proposed implementation, not a measured E4B configuration.

## Research question and independent evidence

Question: under a fixed inference budget, does direct GRPO improve the original E4B instruction checkpoint's ability to produce correct Bash scripts on unseen exercises derived from the same kinds of work as the available Pi sessions?

The original instruction checkpoint already includes its upstream instruction training. "No SFT" means no additional SFT stage or previously trained adapter in this project; it does not mean switching to a pretrained-only checkpoint.

A specialist would establish the measurement before optimizing the policy. The raw evidence is the session JSONL branch, original user requirements, command arguments, tool outputs, source model/runtime settings, and the initial files/bytes/modes needed to reproduce the task. Compaction summaries and successful-looking assistant answers are discovery aids, not correctness labels. Preserve immutable raw sources privately, create sanitized derivatives, and mark reconstructed environments as reconstructed rather than historical snapshots. If original state is missing, reproduce the behavior in a new, explicitly authored fixture or exclude the task.

An exercise is accepted only when a reference solution and at least one different valid implementation pass, plausible incorrect variants fail, and the same script/fixture produces the same result on three clean repetitions. Wrong variants include an empty script, a hard-coded example answer, and a relevant semantic error such as unquoted filenames or wrong file selection. A task whose correct response can be empty must also be checked on a declared nonempty case. Hashes, exit codes, filesystem comparisons, and independent expected-output calculations provide the evidence; an LLM's approval is insufficient.

Keep the first pilot narrow: local file selection/quoting, deterministic text transformations, and repairs of short scripts. The approximately 20 diagnostics and 50–100 candidate exercises are feasibility targets, not claims of adequate statistical power. Start by perfecting five end-to-end exercises. No network accounts, full agent trajectories, distributed reward service, or large dataset expansion is required for the pilot.

## Task contract

Each task record contains `task_id`, `family_id`, `source_cluster_id`, `prompt` (role/content messages), `fixture_id`, `verifier_id`, `invocation`, `split`, `provenance`, and a schema version. `invocation` is an argument list, not a command string interpolated through another shell. Environment and verifier references are grader metadata, not hidden requirements supplied to the policy. All requirements the verifier scores appear in the prompt, including Bash/utility assumptions, argument conventions, allowed changes, and output requirements.

A fixture definition specifies input files, bytes, modes, timestamps, working directory, allowed output paths, and generation seed. Every rollout receives a fresh instance. All candidates in one GRPO group use the same fixture set and seeds; vary fixtures between groups to avoid comparing candidates on different difficulties. Record the Linux image digest, installed tools, locale, and timezone. Defer wall-clock-dependent tasks from the first pilot. A later time-based task must explicitly define its reference time and invocation; containers alone do not freeze the clock.

The initial output contract is one Bash script in one fenced `bash` block in the final response. Use the checkpoint's native template/thinking configuration. Extract only the declared final-answer script, reject missing/multiple blocks, and never execute reasoning or other output text. Test extraction against actual E4B output before freezing the contract. Do not add the Gemma 3 notebook's custom reasoning tags merely to reproduce its format reward.

A verifier reports named behavioral checks, critical invariant violations, score, and execution status. It lives outside candidate-writable paths. Valid alternate implementations must pass. Incorrect scripts and deliberate grader bypass attempts must fail. Execution status is one of `ok`, `invalid_script`, `runtime_error`, `resource_limit`, or `infrastructure_error`; only infrastructure errors leave the score null. Candidate syntax/runtime errors and enforced time/memory/process/output limits score zero. A genuine infrastructure error retries the exact saved script/fixture up to two additional times; if retries fail, the whole group is invalidated, persisted, and the run halts for repair. The policy is never updated while a group is partially scored, candidates are never silently replaced, and infrastructure failures are not model failure labels.

Initial reward: zero on unusable execution, critical invariant violation, or failure to make required functional progress; otherwise a normalized weighted fraction of stated functional checks, capped at one. Preservation constraints are gates, not a large source of positive reward for doing nothing. Weights are specified per task before training. A fully successful completion earns one only when all required checks pass across the declared fixture set. Syntax, formatting, and exit code alone earn no reward. Record grader infrastructure errors as unscorable and fail the run's readiness gate if scores cannot be computed; never silently replace these errors with model failures. Freeze reward definitions per experiment.

Generated scripts execute as an unprivileged user in a disposable Linux environment with no network, host credentials, host checkout, container socket, or verifier access. Bound processes, CPU, memory, runtime, writable storage, and output volume. Kill descendant processes and reset state after every candidate. Verify these properties on both the CPU development machine and GPU host. CPU grading may run locally beside the GPU process; a remote grading service is unnecessary. If the GPU provider cannot support the required isolation, it is not a compatible host for this runner.

Pi session extraction follows parent/branch links and preserves relevant context, source model, and tool results when available. Model switches, compaction, retries, and failed attempts require explicit handling. Sanitize secrets and private content before publishing any derived record. Reference scripts may validate fixtures and graders; they are not policy training targets.

Split by task family and source cluster before producing variants. A family is a shared solution pattern/task-generating template; a source cluster is a related source episode including forks and branches. These are finer-grained than broad categories such as file operations. Keep variants, paraphrases, branches, and closely related source tasks in the same split. Build a relationship graph over shared source episodes, forks, paraphrases, templates, and diagnostic derivatives, and assign whole connected components to one split; diagnostic exercises and their derivatives stay in the development pool and never enter the final unseen test set. Reserve held-out families to measure transfer. Do not select the final test set based on the model's test scores.

## Experimental controls and decision rule

Separate the user's deployment alias `gemma4:e4b` from the exact trainable model repository/revision. Record deployment model digest and quantization when available. Establish the untouched training-policy baseline in the same backend, precision, template, thinking mode, context/completion limits, and decoding settings as the trained-policy comparison. Diagnose failures in this order: extraction/runner, template/truncation/runtime, then shell behavior. A failed quantized deployment alone does not establish a weakness in the upstream checkpoint.

Use screening only on training tasks. Validation selects checkpoints and training settings. Lock test source clusters, families, prompts, fixture seeds, and analysis before training; do not use test outcomes for task selection or prompt tuning. An evaluation test case may be hidden, but the requirement it exercises must be stated. Independently authored held-out cases should check the same requirements, rather than merely reusing the exact training reward checks.

Primary endpoint: task-level single-attempt full functional pass rate under matched generation budgets, averaged equally over tasks. If several generation seeds are used, average within task first. Report per-family results, critical violation rate, truncation, scoring coverage, and GPU/CPU time. Multi-sample success and mean training reward are secondary measures. Use a paired task comparison with a family/source-cluster bootstrap for a 95% confidence interval; count independent clusters, not fixture variants or sampled responses, as the evidence units.

Proposed practical target to freeze in Phase 5: at least a 5 percentage-point held-out pass-rate improvement. Claim demonstrated improvement only when the paired 95% interval excludes zero and observed critical violations do not increase. A small pilot can remain inconclusive; report the effect estimate and interval instead of expanding scope to force a positive finding. A working trainer is a technical success, not proof of model improvement. The pilot proceeds only with valid rewards, verified recovery, and a positive validation point estimate without increased critical violations; it need not establish statistical significance.

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
