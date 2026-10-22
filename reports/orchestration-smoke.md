# Orchestration smoke evidence · Phase 0

Recorded: 2026-10-21 · Run: `P0-20261021T1140` · Codespace: `fantastic-goggles-vrj5767px2xp57`
Base commit: `aec2338` · Skill: `gh-cli-ops` local revision (SKILL.md + codespaces reference
SHA-256 recorded in the private run record). Sanitized: no tokens, endpoints, or session
identifiers beyond the provider-generated Codespace name.

## Scenario walkthrough (all checks executed against the live Codespace)

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Exact Git SHA captured on worker | Pass | `/workspaces/gemma4-shell-grpo` at `aec2338`, clean tree |
| 2 | Harmless sentinel + machine-readable exit record | Pass | `/tmp/smoke/sentinel.txt` + `/tmp/smoke/job.json` (job `smoke-P0-20261021T1140`, `exit_code: 0`) |
| 3 | Disconnect / reconnect | Pass | Second, independent SSH session re-verified state |
| 4 | Same job, no duplicate | Pass | Exactly one `job.json` on re-check (count = 1); no second sentinel run |
| 5 | Transfer worker → controller | Pass with substitution | Hashes matched exactly: sentinel `513f39c3…`, job record `ad365465…` |
| 6 | Failed Git push simulation | Pass | `git push` to invalid remote → fatal, no publication; remote URL restored; emergency copy already safe in two controller locations (`runs/…/smoke/` + `artifacts/…/smoke/`) |
| 7 | Controller-unavailable stop | Pass | Detached worker-side watchdog fired while controller was disconnected (`watchdog-fired` marker created with no controller interaction); Codespaces idle-timeout remains the provider backstop |
| 8 | Run journal recoverable copy | Pass | Smoke records exist in `runs/P0-20261021T1140/smoke/` **and** `artifacts/P0-20261021T1140/smoke/`; sanitized evidence also lives in this pushed report |
| 9 | Stop + closeout | See closeout commit | Provider stop commanded via `gh codespace stop`; stopped-state verified before this file's closeout line was published |

## Defect found and recorded

`gh codespace cp` failed **twice** in this headless context (internal scp reported
"No such file or directory" for files demonstrably present on the worker). Fallback to
base64-over-`gh codespace ssh` succeeded with exact hash match. **Decision recorded in
`runtime-capabilities.md`: ssh-stream is the primary transfer mechanism; `cp` is not relied
upon.** This is the smoke test doing its job — a broken mechanism was found before any real
work depended on it.

## Interpretation

- "Publish pending" and "closeout pending" states were exercised: the simulated push failure left
  the emergency copies verified-by-hash while publication had not happened; the subsequent real
  push cleared the pending state. No evidence was marked verified before its hash comparison.
- The watchdog proof satisfies the Phase 0 requirement that a spend deadline can stop a worker
  without the controller (worker-side mechanism), with the provider idle timeout as backstop.

## Not covered here (by design)

Colab runtime sentinel — repeats at Phase 2 activation before any model work (PLAN.md Phase 2).
Candidate-script grading — gated on Phase 1; `pi-sessions/verify.py` remains a gated skeleton.

## Colab sentinel subrun (Phase 2 activation, 2026-10-22)

Colab's tested job-persistence mechanism, per the PLAN Phase 2 requirement, on runtime
`g-check-pi-exp` (L4):

| Check | Result |
|---|---|
| Activate runtime | Pass — `colab --auth=adc new -s g-check-pi-exp --gpu L4`; "Session READY", VM SSH up in ~1 min. `gh codespace`-style auto-start does not apply; **a stopped Colab session must be re-created** (sessions are not start/stop-resumable like Codespaces). |
| Sentinel + job record survive disconnect/reconnect | Pass — detached `nohup` job wrote `job.json`, `sentinel.txt`, `exit.json` (~20 s work); controller disconnected and reconnected; exactly one job, files intact. |
| Copy to controller + hash | Pass — base64 over the SSH bridge, SHA-256 `17a6787c…` recorded worker-side. |
| `--rm`/stop behavior | Not exercised this activation (stop verified instead at closeout: `colab --auth=adc stop -s <session>` removes the runtime; `/content` and VM state are then gone — durable storage is mandatory before relying on any VM-resident artifact). |
| Single-session limit | Confirmed live: an unclean bridge disconnect holds the SSH slot ~1 minute (HTTP 429 until the server-side session expires); retry after ~60 s. |
| Transfer channel | `ssh colab-agent` ProxyCommand bridge (managed aliases rebuilt 2026-10-22 — the September 2026 LaunchAgent/port-forward chain no longer exists on this Mac; the CLI bridge needs nothing permanent). Multi-word remote commands over `gh codespace ssh`-style quoting do not apply here: scripts travel base64-encoded on stdin (`base64 -d \| bash`). |
