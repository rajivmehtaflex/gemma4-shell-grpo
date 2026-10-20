# Gemma 4 E4B Shell GRPO

Improve shell scripting with direct GRPO starting from the original Gemma 4 E4B instruction checkpoint. Begin with authored exercises and add tasks informed by Pi sessions if the source audit before Phase 3 supports them. Score newly generated scripts through reproducible execution. There is no SFT stage.

## Project documents

- [Phase plan](PLAN.md): deliverables, CPU/GPU ownership, and exit criteria.
- [Beginner's guide](docs/PLAN-GUIDE.md): plain-language walkthrough of the plan, GRPO, and the Unsloth/TRL stack.
- [Design](docs/DESIGN.md): scope and data/artifact contracts.
- [Current state](STATE.md): completed work and the next action.
- [Machine handoff](docs/HANDOFF.md): commit, push, restore, and checkpoint rules.

## Compute approach

CPU phases prioritize **GitHub Codespaces through `gh-cli-ops`**. GPU phases prioritize **Google Colab through `colab-ssh-setup`**; GPU workers also use CPU cores for restricted grading. Phase 8 uses Colab for evaluation and Codespaces for reporting. `modal-deploy-ssh` is an explicitly selected fallback.

Every phase includes machine activation/reconnection, restoration of the recorded source and artifacts, execution of all phase tasks/checks, private artifact preservation, a reviewed Git commit/push through `gh-cli-ops`, and verified machine shutdown. The local controller coordinates workers and is the default GitHub writer. See PLAN.md and docs/HANDOFF.md for the lifecycle, and the beginner's guide for a plain-language walkthrough.

The proposed fast stack is Unsloth + TRL with fresh LoRA adapters for direct GRPO. Establish the documented Unsloth inference path first; accelerated rollout generation is conditional on compatibility and parity evidence. Exact package versions, model revision, GPU, and training settings will be frozen after a GPU compatibility experiment. The supplied Gemma 3 notebook is a conceptual reference, not a tested Gemma 4 environment.

Git stores code, configs, plans, small sanitized examples, and artifact manifests. External durable storage holds raw logs, datasets, rollouts, and checkpoints. Every machine handoff starts from a pushed commit and verified artifact references.

Status: planning repository only. Phase 0's runtime, storage and orchestration checks precede Phase 1 implementation on authored exercises. The Pi source audit is deferred until before Phase 3; an authored-only dataset remains the fallback. See STATE.md before beginning work.

First milestone: five CPU-verified exercises (D01–D05 in PLAN.md) whose graders accept different valid scripts, reject plausible wrong scripts, and give repeatable results. The project ultimately measures matched held-out functional pass rate with uncertainty; increasing training reward alone is insufficient.
