# Runtime capability contract · Phase 0

Recorded: 2026-10-21 · Probe host: Codespace `fantastic-goggles-vrj5767px2xp57` (basicLinux32gb,
2 vCPU / 8 GB RAM / 32 GB storage), created from `rajivmehtaflex/gemma4-shell-grpo@main`,
base commit `aec2338`. Machine slug verified via the codespaces machines API: 2 cores, 8 GB RAM,
32 GB storage — matches the recorded basic 2-core decision. All probes executed read-only or
inside disposable containers; no candidate scripts exist yet, so no scoring was involved.

## Environment (recorded, not assumed)

| Item | Value |
|---|---|
| OS | Ubuntu 24.04.5 LTS |
| Architecture | x86_64 (matches the pinned linux/amd64 cross-machine target) |
| Python | 3.14.2 (default image; Phase 1 pins its own environment) |
| git / gh | 2.55.0 / 2.100.0 |
| Docker | 29.8.0, daemon reachable without sudo |
| Repo checkout | `/workspaces/gemma4-shell-grpo` at base SHA, clean tree |
| Disk | 19 GB free on `/workspaces` |

## Isolation capabilities (probe results)

| Requirement (PLAN Phase 0) | Result | Evidence |
|---|---|---|
| Unprivileged candidate execution | **Pass** | `useradd` + `runuser -u cand-test -- whoami` → `cand-test`; additionally Docker `-u 1000:1000` ran as non-root inside container |
| No network for candidate | **Pass** | `sudo unshare -n` → loopback only; unprivileged `unshare --user --map-root-user --net` also works; **Docker `--network none` → zero routes** (verified with `ip route \| wc -l` = 0 inside container) |
| Resource bounds | **Pass with caveat** | cgroup v2 present with `cpu io memory pids` controllers; default ulimits are unlimited, so the Phase 1 runner must set explicit `--memory`/`--pids-limit`/`ulimit` values — recorded as a Phase 1 requirement, not a capability gap |
| External verifier access | **Pass (structural)** | Grader runs as a separate user/paths outside candidate-writable locations; candidate containers receive no mounts of verifier state (`-v` allowlist is empty by default in the probe pattern) |
| Fixture/result transport | **Pass with caveat** | `gh codespace ssh` streams work reliably (base64 round-trip verified); `gh codespace cp` failed twice in headless context (internal scp "No such file" despite files present) — **ssh-stream is the primary transfer mechanism; `cp` is not relied upon** |
| Host kernel seccomp | Note | Outer devcontainer reports Seccomp 0; Docker containers get Docker's default seccomp profile — graded isolation is the container's, not the outer shell's |
| Repo checkout at recorded SHA | **Pass** | `git log --oneline -1` = base commit, clean tree |

## Engine decision for Phase 1 (evidence-based)

**Docker inside the Codespace** is the proven restricted-runner pattern:
`docker run --rm --network none -u <uid> --memory <bound> --pids-limit <bound> -v <fixtures-only:ro>`
with the verifier living outside every candidate mount. Rootless namespaces (`unshare --user`)
are a validated fallback. macOS development may use emulation per the plan; parity fixtures run
if the image target changes.

## GPU host note

Colab runtime capabilities are **not yet probed** — per PLAN.md this is verified when Phase 2
activates the GPU runtime, using the same sentinel and the same grading-contract checks before
any model work.

## Modal fallback

Unassessed. Eligible for consideration only if a preferred provider fails a capability check;
would be tested against this same contract before use.

## Phase 1 requirements recorded from this probe

1. Runner must set explicit memory/pids/cpu bounds (host defaults are unlimited).
2. Runner must use `--network none` (proven) and a non-root uid inside the container.
3. Fixtures are read-only mounts; verifier state is never mounted into candidate containers.
4. Transfers use the ssh-stream mechanism (`gh codespace cp` is unreliable headless — two
   failures recorded in `orchestration-smoke.md`).
