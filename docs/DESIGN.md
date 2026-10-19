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
- Proposed fast stack: Unsloth + TRL, with vLLM or another accelerated rollout path only after verifying the integration on the chosen GPU. No support claim or package lock is implied yet.

## Task contract

Each task record contains `task_id`, `family_id`, `prompt` (role/content messages), `fixture_id`, `verifier_id`, `split`, `provenance`, and a schema version. Environment and verifier references are grader metadata, not hidden requirements supplied to the policy. All requirements the verifier scores appear in the prompt.

A fixture definition specifies input files, bytes, modes, timestamps, working directory, allowed output paths, and generation seed. Every rollout receives a fresh instance. Use a fixed reference clock for age-based tasks. Record the Linux image digest and installed tools.

A verifier reports named behavioral checks, critical invariant violations, score, and execution status. It lives outside candidate-writable paths. Valid alternate implementations must pass. Incorrect scripts and deliberate grader bypass attempts must fail. Nonzero exit codes, syntax errors, timeouts, and infrastructure failures are separate recorded categories; infrastructure failures are not model failure labels.

Initial reward: zero on unusable execution or critical invariant violation; otherwise a normalized weighted fraction of stated behavioral checks, capped at one. Weighting must not reward doing nothing over correctly completing the requested transformation. Syntax/format/exit-code checks alone are insufficient. Reward definitions are versioned and frozen per experiment.

Pi session extraction follows parent/branch links and preserves relevant context, source model, and tool results when available. Model switches, compaction, retries, and failed attempts require explicit handling. Sanitize secrets and private content before publishing any derived record. Reference scripts may validate fixtures and graders; they are not policy training targets.

Split by task family and source cluster before producing variants. Keep variants, paraphrases, branches, and closely related source tasks in the same split. Reserve held-out families to measure transfer. Do not select the final test set based on the model's test scores.

## Artifact and state contract

Every run manifest records source Git SHA, config hash, model/tokenizer revisions, template/thinking settings, dependency lock hash, image digest, data release/hash, reward version, seeds, hardware, run ID, parent run, and durable artifact URIs with checksums. No credentials are stored in manifests.

Distinguish the run's source commit from the later commit recording its results. Do not put a self-referential current commit hash into a file and expect it to match the commit containing that file.

A resumable training checkpoint includes policy/adapters, optimizer, scheduler, RNG, trainer state, and data-order/sampler state where supported. Record unsupported state and any loss of exact reproducibility. Adapter-only exports are inference artifacts, not complete training recovery points.

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

Fetch current implementation documentation when a phase begins. This design does not assert that a particular Gemma 4/Unsloth/TRL/vLLM version combination has been tested.
