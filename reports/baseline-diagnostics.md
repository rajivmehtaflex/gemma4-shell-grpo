# Baseline diagnostics — the untouched Gemma 4 E4B on the CPU grader

Recorded: 2026-10-22 (Asia/Kolkata) · Run `P2-20261022B` (parent `P2-20261022TActiv`) ·
Colab L4 runtime `g-check-pi-exp` · Model `unsloth/gemma-4-E4B-it@4e22d7e5` ·
Generation: conservative Unsloth path, `temperature 1.0 / top_p 0.95 / top_k 64`,
`gemma-4-thinking` template with `enable_thinking` · Grading: the Phase 1 grader via the
namespace engine on the same host · Reward version `r1`.

## Scope (user decision recorded in STATE.md)

Reduced-budget weakness report: **D01–D05 × 4 samples** instead of the full 20×8 plan.
Measured speed (~0.2 s/token) makes the full plan ≈9 L4-hours; the matched-budget full
comparison belongs to the Phase 5 frozen plan. **Per-task budgets differ and are recorded
per record**: D01/D02 ran at `max_new_tokens 1024`, D03–D05 at `2048` — 1024 was raised
after truncation became the dominant failure mode (the thinking channel consumed the whole
budget before the answer fence closed on 4/4 D02 samples; the probe saw the same at 512).
The 20 primary records mix budgets **by task, never within a task**; a trained-vs-baseline
comparison must reuse these exact budgets per task or re-run both sides under one budget.

## Headline

**Full functional pass rate: 0 of 20 (0%).** Mean task score 0.241 over the 11 scored records (9 produced no score: extraction failure or truncation).
Zero critical violations anywhere — the untouched model never mutated inputs or broke
preservation constraints; its failures are capability failures, not safety failures.

| Task | Budget | Full pass | Mean score | Truncated | No script extracted | Critical |
|---|---|---|---|---|---|---|
| D01 count .txt | 1024 | 0/4 | 0.65 | 0 | 1 | 0 |
| D02 copy .log | 1024 | 0/4 | — (all truncated) | 4 | 4 | 0 |
| D03 TSV aggregate | 2048 | 0/4 | 0.00 | 0 | 1 | 0 |
| D04 repair copy | 2048 | 0/4 | 0.00 | 0 | 0 | 0 |
| D05 repair count | 2048 | 0/4 | 0.70 | 0 | 3 | 0 |
| **Total** | | **0/20** | **0.241** | **4** | **9** | **0** |

(Three bonus S01 records from an over-scoped instance — 0/3, same main-fixture failure —
are kept as extra evidence but excluded from the primary set.)

## What the model actually gets wrong

1. **D01 (0.65):** partial, never full. Empty and decoy fixtures pass; the tricky-name main
   fixture fails `stdout_exact` every time — consistent with quoting/parsing weaknesses on
   names with spaces/dashes/newlines (the S01-family signature).
2. **D02 (truncation-dominated at 1024):** every sample produced a well-structured thought
   that arrived at "let's write the script", opened the fence, and was cut mid-line. A
   budget artifact, kept deliberately as evidence that the thinking channel plus answer does
   not fit 1024 tokens on multi-step tasks.
3. **D03 (0.00):** where a script was produced, key totals were wrong, output unsorted, and
   one sample exited nonzero on every fixture (including the empty-input success case).
4. **D04 (0.00):** scripts ran but never copied the required file set correctly
   (`required_files_copied` 0 on the main fixture in 4/4) — the repair-task discipline
   (quoting, dash handling, symlink skip) is not there yet.
5. **D05 (0.70):** counts ERROR lines correctly on the main/tricky fixtures but exits
   nonzero on legitimate zero cases (empty file, no matches) — and 3/4 samples produced no
   fenced block at all within 2048 tokens (runaway thinking).
6. **Extraction failures: 9/23.** One sample emitted two fenced blocks (correctly rejected —
   the one-block contract works); the rest are truncation or runaway-thought no-fence cases.

## Implications for the GRPO hypothesis

- **Massive headroom:** 0% full-pass with partial-credit density (D01 0.65, D05 0.70) means
  group-relative advantages will be informative — not all-zero groups.
- **The reward surface already separates behaviors:** correct counting (D05 main) earns
  partial reward while exit-code discipline and truncation suppression are exactly the kind
  of gains GRPO can reinforce.
- **Safety baseline is clean:** critical-violation rate 0/20 — the acceptance target "no
  increase in critical violations" starts from zero.
- **Budget is part of the contract:** 1024 tokens truncates multi-step tasks; the frozen
  Phase 5 budget must be ≥2048 (or the thinking channel must be trained to be concise —
  itself measurable as a truncation-rate improvement).

## Provenance and evidence

- Per-record evidence: `runs/P2-20261022B/records-final/` (locally) and
  `phase2/baseline/records-2048.tgz` + `records-1024-banked.tgz` in the private HF repo
  `rajivmehtapy/gemma4-shell-grpo-artifacts` (privacy re-verified: anonymous access 401).
- Each record carries model identity, generation settings (including its actual token
  budget), prompt hash, extraction outcome, the complete extracted script, the full
  GradeResult (per-fixture checks, fixture hashes), truncation and timing.
- **Raw completion text from the final run is not recoverable** (the runtime was reclaimed
  before a raw-completions sync; earlier-run raws were preserved in the same HF repo). The
  extracted script and check-level evidence are intact per record; future runs must sync
  raws on the same cadence as records (watchdog fix queued).
- Operational findings recorded in `reports/orchestration-smoke.md`: Colab reclaims
  runtimes when no client is connected (running processes do not keep it alive); the
  `colab` CLI silently auto-creates a CPU runtime when a named session is connected to
  while absent; an HF-sync watchdog (60 s cadence) + record-resume made the run survive
  three runtime losses with zero lost records after adoption.

## Gateway check (PLAN Phase 2 gate)

A tested lock exists (`environments/gpu.lock`, frozen on the L4), and the original-model
weakness report exists (this file): the Phase 2 gate is met with the reduced scope the user
approved. Accelerated rollout paths were not tested (not needed — the conservative path is
functional); the compatibility probe evidence lives in run `P2-20261022TActiv`.
