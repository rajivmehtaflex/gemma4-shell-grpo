# Project overview

Research repo testing whether direct GRPO (no SFT) from the original Gemma 4 E4B instruction checkpoint improves Bash scripting on held-out, executable-verified tasks. Exercises are authored first; Pi-informed tasks were ruled out for bank-v1 by the source preflight (natural-session yield 0/5), recorded in `reports/source-preflight.md`. Phases 0–3 are complete with recorded evidence (`reports/orchestration-smoke.md`, `reports/runtime-capabilities.md`, `reports/phase1-grader.md`, `reports/baseline-diagnostics.md`, `reports/dataset-audit.md`): the restricted CPU grader runs twenty authored diagnostics in a digest-pinned Docker image (acceptance 241/241 at `ce96da6`); seven of the ten collected Pi candidates verify through it; the Colab L4 compatibility probe passed and the untouched checkpoint's reduced baseline scored 0/20 full passes (mean 0.241); the authored task bank `bank-v1` (32 tasks, splits 11/9/12) is accepted with 137/137 executions green. No training has happened here; Phase 4 (difficulty screening with the untouched policy on Colab) is next.

- Public repo: `rajivmehtaflex/gemma4-shell-grpo` (branch `main`); visibility was changed at the user's request — raw data, credentials, and checkpoints still never enter Git.
- Dev host is macOS; all scored script execution must happen inside the restricted Linux grading image (see rule below). The pinned Linux/amd64 grading image is the initial cross-machine target; macOS development may use emulation.
- Planned stack (from PLAN.md): Python + uv + pytest; package `src/shell_grpo/` with `contracts/runner/fixtures/verifiers/rewards` modules, plus `tests/`, `configs/`, `scripts/`, `containers/grader/`, `environments/`, `reports/`, `manifests/`, `data/examples/`. These directories do not exist yet — create them per the active phase's file list.
- Document map: README.md (summary) → PLAN.md (nine-phase roadmap, skill orchestration contract, phase-status ladder, active phase, per-phase file lists and gates) → docs/DESIGN.md (task/fixture/reward/split contracts) → STATE.md (current state, decisions, evidence ledger) → docs/HANDOFF.md (CPU/GPU handoff, provider lifecycle and recovery protocol).
- docs/PLAN-GUIDE.md is a beginner-friendly companion to PLAN.md (GRPO/Unsloth/TRL vocabulary and phase walkthrough). PLAN.md remains authoritative on any conflict.

# Project working rules

- Read README.md, PLAN.md, STATE.md, and docs/HANDOFF.md before continuing.
- Follow the active phase; mark completion only with recorded evidence.
- Phase 0/1 use authored exercises and do not require Pi-source staging or assessment. Audit user-designated Pi sessions before Phase 3; if the corpus is insufficient, continue with the recorded authored-only fallback.
- No SFT. Start from the original Gemma 4 E4B instruction checkpoint; fresh LoRA adapters are permitted for direct GRPO if the compatibility phase validates them.
- Complete CPU preparation before renting GPU compute. Record GPU compatibility evidence before claiming the fast stack works.
- Execute generated shell scripts only in the restricted Linux grading environment. Never execute them on the development host.
- Keep raw Pi logs, credentials, datasets, model files, and checkpoints out of Git. Small sanitized fixtures and manifests are allowed.
- At each completed milestone and before every machine handoff: record evidence and next action, review the diff, commit explicit paths, push, and verify synchronization. Use short conventional commit prefixes (`docs:`, `feat:`, `fix:`), matching existing history.
- Never commit model artifacts or raw data: `.gitignore` blocks `artifacts/`, `checkpoints/`, `data/raw/`, `data/processed/`, `outputs/`, `runs/`, and `*.safetensors`/`*.gguf`/`*.pt`/`*.pth`/`*.ckpt`. Git holds code, configs, plans, manifests, and small sanitized fixtures only.
- Persist artifacts separately and verify hashes. A Git commit alone does not preserve training state.
- Never overwrite another worker's dirty checkout. Each machine uses its own checkout; record the source commit of every run.
- Every phase run keeps a private record under Git-ignored `runs/<run_id>/` (job identity, logs, exact code executed, milestone evidence). On disconnect, check provider status and the job record before reconnecting; never duplicate a possibly-running job. PLAN.md's phase-status ladder (`ready → … → complete`) is the resume vocabulary: resume from the first unverified milestone.
- CPU work prioritizes GitHub Codespaces through `gh-cli-ops`; GPU work prioritizes Google Colab through `colab-ssh-setup`. Phase 8 uses Colab then Codespaces. Each phase includes activation/reconnection, full task execution and acceptance checks, artifact preservation, commit/push and verified shutdown, then a state-only closeout commit — a phase is complete only when its result and closeout commits both match the remote.
- `modal-deploy-ssh` is an explicitly selected fallback. SSH access alone does not satisfy the restricted grading contract.
- Codespaces access, machine size and the spending ceiling are decided in STATE.md (basic 2-core, free tier, $10/month). Still pending there: durable artifact storage, the Colab session name/accelerator and exact fast-stack configuration. Confirm the Colab session name before first provisioning, as its skill requires. Do not provision paid resources based on assumptions.
- If .codegraph/ exists at the repository root, use CodeGraph before searching or reading code to understand it. Otherwise skip it.
- Use Context7 for current library/CLI documentation when making implementation decisions; do not copy the reference notebook's dependency pins blindly.
