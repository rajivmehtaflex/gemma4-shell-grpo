# Source preflight — Pi corpus assessment before dataset construction

Recorded: 2026-10-22 (Asia/Kolkata) · Run `P3-20261022T1900` · Deferred from Phase 0 per
the authored-first decision (STATE.md). This preflight ran before any dataset construction.

## Sources inspected (metadata + full content)

| Source | Identity | Sanitized hash / size | Status |
|---|---|---|---|
| Natural Pi session | `2026-10-07T10-37-19Z_01a115f0…jsonl` (session dir `--Users-rajivmehtapy-Documents-Dev--`) | sha256 `27597b26ac8765d17351f56672a93d84450f39f9b3774da9db137279b4f47222`, 158,583 bytes, 97 JSONL entries | Read in full |
| Natural session dir 2 | `--Users-rajivmehtapy-Documents-Dev-Transformers-exp--` | empty directory (0 files) | Confirmed empty |
| Practice campaign | `pi-sessions/raw/S01–S10` | 10 sessions, ~44–68 KB each (476 KB total) | Excluded from task discovery by charter (see below) |

Schema: Pi JSONL session format, version fields present per entry; entry types observed:
session, session_info, model_change ×2, thinking_level_change, context_edit, message ×91
(system ×2, user ×4, assistant ×45, toolResult ×40 — 40 tool calls: bash ×32, read ×6,
edit ×2). No compaction records. Branching: none observed (linear).

## Exercise-yield assessment (the actual question)

The natural session's four user requests are, in order: (1) make a model/provider the
default in Pi's settings.json and set two flags, verified against documentation; (2) map
the skills directories under `~/.hermes/skills` for selective consumption; (3) render that
listing as a table; (4) extend the listing to `~/.agents/skills`. All remaining traffic is
the assistant's tool work (reads/edits of Pi configuration files, directory listings).

Assessment against the initial exercise categories:

- **File selection/quoting:** no request involves selecting files by name pattern,
  awkward filenames, or directory-tree walks as the deliverable.
- **Deterministic text transformation:** no request transforms file content; the "tabular
  listing" is a presentational aside over machine-specific directory state that cannot be
  reconstructed as a portable fixture.
- **Short script repair:** no defective script appears; the two edits are Pi JSON
  configuration changes whose correctness is defined by Pi's own documentation and the
  machine's existing state — not reconstructable, and not a Bash-scripting exercise.

**Yield: 0 plausible exercises** (target: ≥5). Metadata-only counts (1 session, 158 KB)
would have suggested more promise than the content supports — recorded here precisely
because of that.

The practice sessions are **not** a substitute source: their charter (pi-sessions/README.md)
excludes them from Pi-derived task discovery — they are agent-driven practice runs on
already-authored briefs, kept in the development pool, never counted as source episodes.
Counting them would manufacture provenance.

Missing filesystem state: the session references `~/.hermes/skills`,
`~/.agents/skills`, and Pi's settings.json — machine-specific state with no reconstruction
path that would not fabricate the exercise. Reconstruction effort if forced: high;
justified by yield: none. Exclusions: entire session excluded as a task source; retained
privately, hash-recorded, content never committed.

## Decision

**Authored-only path** — the pre-selected fallback (STATE.md, user-approved 2026-10-20),
applied without reopening the scope decision. Consequences, per PLAN.md Phase 3:

- `src/shell_grpo/pi_sessions.py` and `tests/test_pi_sessions.py` are **not implemented**
  (no viable Pi extraction path exists to implement).
- The Pi-extraction checklist item (private log inventory, reconstruction) is recorded as
  **not applicable** for this path.
- The task bank is built from authored exercises only; every record carries
  `source: authored` with authoring rationale. A future mixed-source revision requires a
  new user-designated corpus and a re-run of this preflight.

Machine note: the raw session file lives only on the controller and was inspected locally;
it was never transferred to the phase worker and never enters Git. The Codespace phase
execution covers the dataset build and acceptance checks, which need no Pi content.
