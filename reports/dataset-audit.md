# Phase 3 dataset audit — release `bank-v1`

Date: 2026-10-22 · Code commit at audit/acceptance: `ffd1f4d` · Reward version: `r1`

## Release identity

| Field | Value |
|---|---|
| Release | `bank-v1` (built by `scripts/build_dataset.py`, seed `20261022`) |
| Bank digest | `bank.jsonl` sha256 `4b97165dae969a477fc5b02c95f20859cccb2207b91ad513854c7c5d9d95750c` (recomputed at audit, matches manifest) |
| Tasks | 32 registered (20 development D/S/V + 12 held-out T) |
| Components / families | 26 connected components over 21 families |
| Splits (actual) | train 11 · validation 9 · test 12 |
| Aspirational 60/20/20 | Would be 19.2/6.4/6.4 of 32; PLAN.md requires reporting actual counts instead of splitting related examples to hit percentages — with whole components and the test pool reserved, the actual 34/28/38 % is the honest outcome. |

## Provenance

Authored-only, per the recorded preflight decision: the one naturally available Pi session
yielded 0/5 plausible exercises (`reports/source-preflight.md`), so no Pi extraction path was
implemented and every task carries `source: authored`. The 12 held-out T tasks additionally
carry the `held_out_test` pool label and a `phase3-task-bank` campaign tag with authoring
rationale (`HOLDOUT_PROVENANCE` in `src/shell_grpo/tasks/heldout.py`). No model-generated
text is a scored target; wrong scripts are hand-authored negative controls.

`bank.jsonl` records do not embed fixtures, verifiers, or wrong-script expectations — those
live in the registry code pinned by the commit above. Reproducing grades therefore requires
`ffd1f4d` (or a descendant that re-passes acceptance), not the JSONL alone.

## Composition and leakage checks

`check_integrity()` (run inside the builder and re-run at audit) reports **no** duplicate task
IDs, no unknown IDs, no family spanning more than one split, and no development-pool task in
the test split. Re-computed at audit time over all 32 registered tasks: no problems.

- **Test split is exclusively held-out material**: test = T1a–T6b (12 tasks, pool
  `held_out_test`). Train = D02 D03 D04 S02 S03 S04 S05 S08 V01 V03 V04 (11).
  Validation = D01 D05 S01 S06 S07 S09 S10 V02 V05 (9).
- **Family disjointness holds**: 21 families, none spans two splits. The six held-out test
  families (dedup-order, column-projection, rename-batch, zero-janitor, head-tail,
  line-numbering) share no solution pattern with any development family (select/copy/move/
  count/aggregate/repair).
- **Diagnostics stay out of test**: every D/S/V task is train or validation only; the
  fixture-seeded variants and decoys used to teach/calibrate never appear in the final set.
- **Duplicate-text audit**: within families the two variants differ in required behavior
  (e.g. T1a global-sort vs T1b first-seen order; T4a delete vs T4b count-only; T3a suffix vs
  T3b prefix), not paraphrase; prompts were authored per variant, not templated with slots.

## Acceptance evidence (Phase 1 harness applied to the T bank)

`scripts/acceptance.py --tasks T1a..T6b --repeats 3` on the Codespace grading image:

- **137 executions, `all_passed=true`, 0 failures** at `ffd1f4d`, clean tree
  (summary + per-execution records preserved in `runs/P3-20261022T1900/acceptance/`;
  tarball with matching sha256 `7453132e3e68751de19d605f9d50e32d8d7620a05c95d38994030d236eb91f5f`
  in private artifacts).
- Reference and alternate of all 12 tasks: task_score 1.0, aggregate `ok`, byte-identical
  results across 3 repeats (determinism check), on every repeat.
- Wrong scripts: 39 declared `zero` all scored exactly 0.0 (including critical-violation
  paths: partial rename mutations, recursive rename, symlink deletion, overdelete, counts-
  then-deletes); 2 declared `partial` scored in (0,1): T1a `wrong-hardcode` 0.7 and T2a
  `wrong-cut-novalidate` 0.85.
- Full pytest at the same commit on the Codespace: 69 passed (58 host tests + 11
  Docker-gated tests that skip on the macOS host).

Three acceptance rounds were needed; the catches are themselves audit evidence:

1. **Round 1** — T2a/T2b malformed-row fixtures declared success in their `GroundTruth`, so
   the engine misread the scripts' *correct* exit-2 as `runtime_error`; T3b's prefix verifier
   wrapped a boolean in `all()` (TypeError); T1a/T2a wrong-script expectations declared
   `zero` for scripts that legitimately earn partial credit. Fixed in `64c61e2`.
2. **Round 2** — T5a main fixture data ended in a blank line, so the file's true last line
   was empty and the authored expectation was wrong, not the scripts; T4b's alternate used
   bash `globstar`, which silently descends directory symlinks and counted 4 instead of 3
   (replaced with a symlink-skipping recursive walk); T2a's alternate matched the literal
   two characters `\t` in a `case` pattern instead of a tab; T4a's `find -L` wrong script
   passed by traversal-order luck (its target was deleted before the symlink was visited).
   Fixed in `ffd1f4d` — the T4a wrong now *removes the symlinks it traverses*, a
   deterministic critical violation independent of readdir order.
3. **Round 3** — clean: 137/137 expectations met.

## Reward ceilings against known hacks

- No-op: 0.0 on every task (no-progress rule).
- Example-specific hard-coding: capped at 0.7 (T1a) — distinct-data fixtures and error
  fixtures are unsatisfiable by a memorized answer; full reward is unreachable.
- Partial compliance (skips an explicit validation requirement): capped at 0.85 (T2a
  cut-without-validation) — the violated requirement carries its own fixture weight.
- Any critical violation (collateral mutation, overdelete, tree mutation on refusal
  fixtures): task score zeroed by the r1 rule regardless of per-fixture partials.

## Recorded deviations

- **Regression subset** (`configs/dataset.yaml`): PLAN wording says lock known-good checks
  "from baseline successes", but the baseline produced zero full-task successes
  (`reports/baseline-diagnostics.md`). The subset degrades to reference/alternate known-goods
  on D01 and D05 (the two tasks with partial baseline credit) plus those baseline
  fixture-level successes, recorded explicitly rather than silently widened.
- **T2 stdout-on-error scope**: the prompt requires "write nothing to stdout" on the
  malformed-row error; the fixtures only exercise malformed-row-only files, so a script that
  emits partial output before an error row is not caught. Noted as unchecked scope, not a
  hidden requirement; widening it would require stdout-buffering reference implementations.
- **First acceptance attempt lost**: the initial detached run (launched in `/tmp`) died with
  an idle Codespace stop before any polling; relaunched with output under `/workspaces`
  (persistent) and keep-alive polling. No duplicate-job risk: process table was verified
  empty before relaunch.
