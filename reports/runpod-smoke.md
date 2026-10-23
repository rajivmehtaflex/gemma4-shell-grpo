# RunPod toolchain smoke test — install + lifecycle + SSH verdict

Date: 2026-10-23 · Controller: macOS · Toolchain: `runpodctl 3.0.1-551d6a4` (brew), official skills `runpod-plugins-official@926087d` installed into `~/.zcode/skills/`

**Objective** (user-scoped): install the official RunPod skills and prove the allocate→operate→teardown pipeline on a minimal machine (CPU class, "2-core/2GB-ish"). **No phase execution** — Phase 4 remains paused.

## Toolchain install (no billing)

- `runpodctl` 3.0.1 via `brew install runpod/runpodctl/runpodctl` (≥2.12 floor met; `--ssh`, `--compute-type`, `--wait`, `--wait-timeout`, `--ports`, `--env` all present).
- Skills: cloned `runpod/runpod-plugins-official`, copied `plugins/runpod/skills/*` → `~/.zcode/skills/` (router `runpod`, lane `runpodctl`, golden paths, etc.), revision `926087d` recorded in `~/.zcode/skills/runpod/SKILL_REPO_REVISION.txt`.
- Auth: user-provided key in `~/.runpod/config.toml`; verified via `runpodctl user` (balance $37.5370, spend $0/hr, account spend limit $80).
- SSH: account key `~/.ssh/id_ed25519.pub` registered via `runpodctl ssh add-key` **before** any pod existed; confirmed in `ssh list-keys`.

## What ran

| Step | Result |
|---|---|
| `gpu list` | A5000 zero stock; A40 48GB Secure $0.59/hr Medium @EU-SE-1; 4090 $0.89/$0.34; L4 $0.59 — availability varies by hour |
| GPU pod create (A40, 5GB volume) | rejected `422 $.mounts.persistent.size: minimum 10` — **min volume is 10GB**; relaunch at 10GB was user-cancelled locally but **the pod still got created server-side and billed** — removed immediately (~2 min). Lesson: after cancelling a CLI create, always `pod list` and clean up |
| CPU pod #1 (`linuxserver/openssh-server`, 2 vCPU/4GB, $0.06/hr) | created, booted, sshd listening on 2222 with the env-injected public key ("Public key from env variable added") — **but no public endpoint: CLI `runtime` object is empty for CPU pods** |
| CPU pod #2 (`runpod/pytorch:1.0.3-cu1281`, 2 vCPU/4GB, $0.06/hr, `--ports 22/tcp`) | created, booted, sshd up ("Start script(s) finished, Pod is ready to use"); `ssh info` synthesized an endpoint (194.68.245.218:22010) |
| SSH connect (pod #2) | **TCP never opened** — timed out from the controller AND from a GitHub Codespace (independent network), across two assigned ports (22010 → 22080 after `pod restart`), while the container stayed healthy in logs |
| `pod restart` | works; reassigned the public port (documented gotcha, seen live) |
| `pod remove` ×3 | all deleted; `pod list` and `network-volume list` verified empty; `currentSpendPerHr: 0` |

**Total spend: $0.0227** (balance 37.5369532551 → 37.5142157571).

## Findings

1. **Lifecycle pipeline PROVEN end-to-end**: create → running → logs → get → restart → remove → verify-empty, with per-second billing confirmed by the balance delta.
2. **SSH-into-pod is NOT functional for CPU pods on Secure cloud**, despite `--ports 22/tcp` and a healthy in-container sshd: the platform never attached a TCP proxy (empty `runtime` binding; endpoints black-holed from two networks). This matches the official skill's note that CPU pods get no RunPod-managed ssh — `ssh info`'s endpoint is synthesized, not measured (the CLI's own `--wait` does a real TCP probe).
3. The SSH leg's documented, live-verified path is **GPU pods** (golden path 06: `ssh info` + real ssh on a 4090 pod) — same CLI flow, same key registration.
4. Gotchas confirmed live: 10GB minimum persistent size; `--ports` replaces the whole list; public port changes on restart; a cancelled local create can still create the pod server-side (always `pod list` after a cancel).

## Verdict and next step

The toolchain and lifecycle are clear. The only unproven leg — interactive SSH — is blocked on the CPU pod class at the platform level, not by our setup. Recommended closure (pending user approval): a 10–15 minute **GPU** pod smoke (~$0.10–0.15 at the cheapest available card) to prove the SSH leg on the documented path, since the actual future workloads (Phase 4+) are GPU pods anyway. No ceiling impact: total RunPod spend to date $0.023 against the $10/month envelope.
