# Dataset card — release `bank-v2` (manifest `dataset-v1`)

Date: 2026-10-24 · Manifest: `manifests/dataset-v1.json` · Phase 5 freeze commit: this repository state

## Identity and reconstruction

| Field | Value |
|---|---|
| Release | `bank-v2` (34 tasks; bank-v1's 32 + the W top-up), seed 20261022, reward version `r1` |
| Bank digest | sha256 recorded in the manifest; re-verified locally and against the private HF payload by `scripts/package_dataset.py verify` (**VERIFY OK** 2026-10-24) |
| Splits (actual, components whole) | train 13 · validation 9 · test 12 (aspirational 60/20/20 reported, never forced) |
| External payloads | `hf://rajivmehtapy/gemma4-shell-grpo-artifacts/p5/dataset-v1/` — `bank-v2/bank.jsonl`, `bank-v2/manifest.json`, `examples-scripts.tar.gz` (hashes pinned in the manifest; repo private, anonymous access returns 401) |
| Verifier bundle | contracts/verifiers/fixtures/rewards/runner/ns_exec + runner.yaml + Dockerfile sha256s pinned in the manifest |
| Model/template identity | `unsloth/gemma-4-E4B-it@4e22d7e5`, gemma-4-thinking template frozen byte-exact in `src/shell_grpo/generate.py` |

Another machine reconstructs the exact experiment from: this commit + `manifests/dataset-v1.json` + the HF payloads. Grader-only fields (fixtures, verifiers, wrong-script expectations) never enter policy prompts; prompts are the `prompt` field of bank records only.

## Composition and provenance

- 34 authored tasks over 27 components / 22 families. `source: authored` everywhere; the W01/W02 top-up carries the `phase5-family-topup` campaign tag with authoring rationale.
- Train pool (13): D02 S03 S05 S08 V01 V03 V04 + W01 W02 (top-up). Validation (9): D01 D05 S01 S06 S07 S09 S10 V02 V05. Test (12, exclusively held-out T tasks): T1a–T6b.
- Families: 22 total; none spans two splits; diagnostics stay out of test (integrity checks re-run in the builder and at freeze).

## Accepted training pool (frozen)

- **Mixed-outcome core (6)** — useful groups under BOTH screening seeds: D02, S03, S05, V01, W01, W02 (families: copy-recursive, move-select, text-aggregate, copy-flat, manifest-verify).
- **Easy coverage (2)**, retained per PLAN: D04, V04 (all-equal full passes — anchor rewards, zero variance expected).
- **Hard reserve (4)**, excluded: D03, S02, S04 (all-zero), V03 (16/16 extraction failures — flagged for re-authoring; a fix would be a new task version, not a silent edit).
- Sampling: uniform over the 8 accepted tasks; group fixture seeds rotate as `derive_fixture_seeds(task_id, 20261022 + global_step)`; candidates share the group seed and receive fresh state. No curriculum, no adaptive filtering (any change = new config + repeated readiness check).

## Frozen experiment contract

- **Extraction**: exactly one fenced bash block (frozen in `evaluate.py`); sampled check: 96/128 screening completions extracted (75%); failures concentrate in V03 (re-authoring flag) and long thought channels.
- **Pilot** (`configs/grpo-pilot.yaml`): GRPO num_generations 8, one group/step, completion 1280 / prompt 768 / seq 2048, lr 2e-6 cosine, beta 0 (group-relative), Gemma 4 decoding (1.0/0.95/64), 12 steps, LoRA r=16 fresh, 4-bit QLoRA base, no vLLM (`fast_inference=false`). Ceilings: 10 GPU-hours, $10/month cash, stop conditions (NaN; loss > 20 ×2 steps — healthy E4B band 13–15 per probe; three consecutive zero-reward steps; infra halts). Checkpoints at steps 4/8/12 with full optimizer state.
- **Evaluation** (frozen): 9 validation tasks × 4 candidates × 2 repetitions at 2048 tokens, paired task-level vs the untouched Phase 2 baseline, bootstrap over connected components, exploratory claim (+5pp is the practical target, not a promise); regression subset (D01/D05 known-goods) rerun every comparison; any increase in critical violations blocks proceeding.
- **Campaign limits**: ≤3 pilot configs, one seed each, final-checkpoint selection, five scheduled main-run validation checkpoints; every attempted configuration logged.
- **Main** (`configs/grpo-main.yaml`): inherits everything; 60 steps, checkpoints every 12, runs only after the pilot gate passes.

## Deviations and known limitations (all recorded, none silent)

1. Regression subset degrades to known-goods on D01/D05 (baseline had zero full-task successes) — `configs/dataset.yaml`.
2. V03 flagged for re-authoring; excluded from the training pool until a new version passes acceptance + screening.
3. S08 (repair-copy) unconfirmed (useful seed 1, all-zero seed 2) — family coverage comes from D04/V04 as easy-covered; S08 remains in the pool only as coverage, and its behavior during the pilot is logged per step.
4. 60/20/20 remains aspirational; actual 38/26/35 % with components kept whole.
5. W02 shows a high extraction-failure rate under the untouched policy (9/16); the task still produces useful reward spread (0.5/1.0) on extracted outputs — training-time truncation/extraction rates are logged per step and reviewed at the pilot gate.

## Freeze verification

- Host suite green (62 passed, 11 docker-gated skipped) at the freeze commit; Codespace suite green (73) with the Docker grader image.
- `package_dataset.py verify`: local bank + verifier bundle + remote HF payloads all match `manifests/dataset-v1.json`.
- Clean-checkout restore rehearsal: performed on a fresh Codespace clone (see STATE.md closeout entry).
