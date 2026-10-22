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

## GPU host note — probed 2026-10-22 (Phase 2 activation)

Colab L4 runtime `g-check-pi-exp` (Ubuntu 24.04.4, x86_64, 12 vCPU, 52 GB RAM, NVIDIA L4
23034 MiB, driver 580.82.07, Python 3.13, uv present, 71 GB free):

| Requirement | Result | Evidence |
|---|---|---|
| Docker | **Absent** (expected on Colab) | `which docker` empty |
| Unprivileged user namespaces | **Pass** | `unshare --user --map-users ...` works; direct `/proc/<pid>/uid_map` write from a real-root parent (util-linux `--map-users` drops the caller from its own map — recorded) |
| No network for candidate | **Pass** | `--net` namespace: 0 routes, `connect` → unreachable |
| Unprivileged candidate execution | **Pass** | child setuid to inner 65534 = outer uid 165533 (file ownership proves the drop); zero capabilities after the uid change |
| Host state protection | **Pass** | `/root` 0700 denies the candidate (HF token, weights, verifier state); `env -i` scrubbed environment |
| Resource bounds | **Pass with caveat** | `ulimit -v` + per-uid nproc + host timeout with process-group kill; **fork inside a PID namespace fails with ENOMEM on this kernel**, so the PID namespace is omitted — process bounds come from the per-uid nproc limit instead (host processes' cmdlines under /proc remain world-readable to the candidate: recorded caveat, no secrets in argv) |
| End-to-end grading | **Pass** | the full `grade_script` pipeline (namespace engine) on this host: D01 reference 1.0 on all fixtures, D05 starter rejected with the exact expected critical, S07 reference 1.0 with support file |

Engine decision for GPU hosts: **`NamespaceRunner`** (user+net namespace engine in
`src/shell_grpo/ns_exec.py`), selected automatically by `make_runner()` when Docker is
absent. The Docker engine remains authoritative on Codespaces.

## GPU model-stack probe (same activation)

Unsloth 2026.10.7 + transformers 5.17.0 + TRL 1.15.0 + torch 2.14.1+cu130 on the L4:
E4B loads via the conservative path (`fast_inference=False`), fresh r=16 LoRA shows finite
loss/gradients, a tiny GRPO step runs, adapter save/reload is output-identical, generation
produces the documented `<|channel>thought` stream. Details and the exact Gemma 4 processor
gotchas are in `runs/P2-20261022TActiv/p2-compat-evidence.json` (hash-verified copy) and
`reports/phase2-*.md`. Measured generation speed: ~0.2 s/token (~103 s for 512 tokens).

## Modal fallback

Unassessed. Eligible for consideration only if a preferred provider fails a capability check;
would be tested against this same contract before use.

## Phase 1 requirements recorded from this probe

1. Runner must set explicit memory/pids/cpu bounds (host defaults are unlimited).
2. Runner must use `--network none` (proven) and a non-root uid inside the container.
3. Fixtures are read-only mounts; verifier state is never mounted into candidate containers.
4. Transfers use the ssh-stream mechanism (`gh codespace cp` is unreliable headless — two
   failures recorded in `orchestration-smoke.md`).
