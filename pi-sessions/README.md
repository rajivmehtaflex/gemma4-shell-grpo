# Pi Practice-Session Campaign

Ten authored shell exercises (S01–S10) solved in **real Pi conversations**, producing genuine
session logs for the pre-Phase 3 source audit. The tasks are authored; the conversations and
outcomes are real. This campaign is the operational form of the authored-first decision
(STATE.md): practice sessions are reported **separately from naturally occurring project
sessions**, remain in the development pool, are excluded from the final unseen test set, and
never become SFT targets.

## Fixed choices

- **Operator:** the coding agent (user-delegated 2026-10-20). Sessions are **agent-driven
  practice runs**: real Pi/model conversations on authored tasks, honestly labeled as such.
  They are not organic human work and are never counted as Pi-derived task discoveries — the
  task bank's source remains the authored briefs themselves.
- **Pi:** v1.3.0 · provider `nvidia` · model `meta/muse-glimmer-30b` · thinking `medium`.
- **Spending:** confirmed free or already-included quota only (`pi auth check` before each
  batch). Pause if coverage is unknown or exhausted; record `launch blocked`.
- **Verification:** the Phase 1 grader inside its restricted Codespace environment — never a
  parallel grader, never execution on macOS. Gated on Phase 0/1 acceptance.
- **Worker:** the recorded basic 2-core Codespace under the $10/month ceiling.

## Layout

| Path | Contents | Git |
|---|---|---|
| `README.md`, `tasks/` | Instructions and ten versioned task briefs | tracked |
| `fixtures/` | Input specifications, starters, acceptance definitions | tracked |
| `verify.py` | Adapter to the Phase 1 grader | tracked |
| `manifest.jsonl` | Sanitized task identities, provenance, hashes, outcomes | tracked |
| `raw/` | Active Pi-generated session logs | ignored |
| `work/` | Editable workspaces and generated solutions | ignored |
| `results/` | Candidate/session snapshots and verification records | ignored |
| `private/` | Sensitive operational metadata | ignored |

## Shared conventions for every task

- `solution.sh` is invoked with `bash` and the arguments stated in its brief.
- Pinned Bash/GNU toolset and `LC_ALL=C`; S07 additionally permits Python 3 standard-library
  `csv`. Exact tool versions are recorded when the grader environment freezes.
- Unless a brief specifies otherwise: invalid arguments or unreadable inputs return exit code
  `2`, print a nonempty diagnostic to **stderr**, emit nothing to stdout, and leave all inputs
  unchanged.
- Input preservation is absolute unless the task is explicitly a copy/move task.
- Every requirement the audit scores is stated in the brief. No hidden requirements.

## Provenance rules

1. Submit each task's frozen brief as the actual Pi request.
2. Feed Pi only **actual** verification feedback, labeled as user-supplied evidence with its
   result ID. Never paste reference solutions into the conversation.
3. Preserve everything: first-attempt successes, failed attempts, corrections, unfinished work.
   No fabricated messages; no edited session histories.
4. If a reference solution is exposed to Pi, record the exposure in the manifest and the audit.
5. Resume only with the exact session file under the same restricted launch configuration.
6. After closure, snapshot the session file to `results/` and hash it; later continuations add
   new snapshots without overwriting.

## Per-session workflow

1. `pi auth check --provider nvidia --model meta/muse-glimmer-30b` — pause if not ready.
2. Launch from the task workspace (see the task brief for the exact command):
   `pi --name <id>-<slug> --session-dir .../pi-sessions/raw/<ID> --provider nvidia --model
   meta/muse-glimmer-30b --thinking medium --tools read,edit,write,grep,find,ls
   --no-extensions --no-mcp`
   Disabling bash in Pi means it cannot execute the script; the operator carries
   `solution.sh` to the verifier. This is convenience, not isolation — review edits and keep
   reference solutions out of Pi's context.
3. Verify from the controller:
   `python pi-sessions/verify.py <ID> --script pi-sessions/work/<ID>/solution.sh --codespace <recorded-id>`
4. Feed the result back to Pi (rule 2), iterate (≤ 3 submitted candidates per task in the
   initial campaign), then close and snapshot.

## Tracker

Two independent dimensions, recorded per task in `manifest.jsonl`:

- **Collection:** `not started` → `started` → `collected` (or `launch blocked`).
- **Verification:** `pending` → `verified` / `failed` / `infrastructure blocked`.

A *collected* session contains a real task request and a substantive model response addressing
it. Empty launches and authentication failures do not count. Continuations and forks do not
increase the distinct-task count.

**Campaign complete when:** ten distinct tasks have authentic session records; every submitted
candidate has an immutable snapshot linked to verification evidence; every task marked verified
passes all declared checks; resume/snapshot handling preserved earlier evidence; raw logs,
generated solutions and private outputs are absent from Git; usage limits and worker shutdown
are recorded.

## Phase 3 handoff

Designate `pi-sessions/raw/` explicitly for the deferred source audit. Report these **authored
practice sessions separately from naturally occurring project sessions**. Neither ten logs nor
ten passing exercises establishes ten independent source families — S01/D01, S02/D02, S05/D03,
S08/D04 and S06/S10/D05 share template lineage, and all practice derivatives stay in the
development pool, excluded from the final unseen test set. Pi responses are not SFT targets.
If the audit also finds naturally occurring material, it is audited and labeled under the
existing rules; if total viable material is insufficient, the authored-only fallback applies
without reopening the scope decision.
