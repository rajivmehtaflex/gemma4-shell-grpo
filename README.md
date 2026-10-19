# Gemma 4 E4B Shell GRPO

Improve shell scripting with direct GRPO starting from the original Gemma 4 E4B instruction checkpoint. Use Pi sessions to discover realistic tasks, then score newly generated scripts through reproducible execution. There is no SFT stage.

## Project documents

- [Phase plan](PLAN.md): deliverables, CPU/GPU ownership, and exit criteria.
- [Design](docs/DESIGN.md): scope and data/artifact contracts.
- [Current state](STATE.md): completed work and the next action.
- [Machine handoff](docs/HANDOFF.md): commit, push, restore, and checkpoint rules.

## Compute approach

CPU machines handle log processing, fixtures, verifiers, sandbox execution, dataset packaging, and reporting. GPUs handle model compatibility, baseline generation, screening, GRPO, and final model evaluation. GPU workers also need CPU resources for grading.

The proposed fast stack is Unsloth + TRL, with accelerated rollout generation if compatibility is demonstrated. Exact package versions, model revision, GPU, and training settings will be frozen after a GPU compatibility experiment. The supplied Gemma 3 notebook is a conceptual reference, not a tested Gemma 4 environment.

Git stores code, configs, plans, small sanitized examples, and artifact manifests. External durable storage holds raw logs, datasets, rollouts, and checkpoints. Every machine handoff starts from a pushed commit and verified artifact references.

Status: planning repository only. See STATE.md before beginning work.
