# Project working rules

- Read README.md, PLAN.md, STATE.md, and docs/HANDOFF.md before continuing.
- Follow the active phase; mark completion only with recorded evidence.
- No SFT. Start from the original Gemma 4 E4B instruction checkpoint; fresh LoRA adapters are permitted for direct GRPO if the compatibility phase validates them.
- Complete CPU preparation before renting GPU compute. Record GPU compatibility evidence before claiming the fast stack works.
- Execute generated shell scripts only in the restricted Linux grading environment. Never execute them on the development host.
- Keep raw Pi logs, credentials, datasets, model files, and checkpoints out of Git. Small sanitized fixtures and manifests are allowed.
- At each completed milestone and before every machine handoff: record evidence and next action, review the diff, commit explicit paths, push, and verify synchronization.
- Persist artifacts separately and verify hashes. A Git commit alone does not preserve training state.
- Never overwrite another worker's dirty checkout. Each machine uses its own checkout; record the source commit of every run.
- GPU provider, durable artifact storage, spending limits, and the interpretation of the fast stack are pending decisions in STATE.md. Do not provision paid resources based on assumptions.
- If .codegraph/ exists at the repository root, use CodeGraph before searching or reading code to understand it. Otherwise skip it.
- Use Context7 for current library/CLI documentation when making implementation decisions; do not copy the reference notebook's dependency pins blindly.
