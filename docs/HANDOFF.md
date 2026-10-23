# CPU/GPU handoff and recovery

## Skill routing and phase ownership

CPU phases 0, 1, 3 and 5 use GitHub Codespaces through `gh-cli-ops`. GPU phases 2, 4, 6 and 7 use Google Colab through `colab-ssh-setup`. Phase 8 uses Colab for model evaluation, then Codespaces for analysis and reporting. Every phase activates its assigned machine and executes all tasks and acceptance checks, rather than stopping after SSH setup. `gh-cli-ops` publishes every milestone. `modal-deploy-ssh` is an explicitly selected fallback, not the default.

The local controller is the default GitHub writer. Worker code starts from a pushed source SHA; sanitized outputs and any reviewed source changes return to the controller for the results/state commit. A worker may write its own result branch only when that ownership is explicitly recorded and scoped authentication is established. Do not duplicate writers or copy controller credentials into candidate environments.

## Provider-specific activation and shutdown

- **Codespaces:** verify the active GitHub identity and repository, list suitable existing Codespaces, and connect/start the selected one by its actual ID; create only when needed with recorded machine type, inactivity timeout, retention and spending limits. Use the skill's `gh codespace` workflow. Restore the correct source commit, complete the entire CPU phase, collect results, commit/push and verify, then stop the Codespace and verify its state. Stopping is not deletion; retained storage remains subject to retention/billing policies and is not the sole artifact copy.
- **Colab:** confirm the session name before first creation. Resolve the actual CLI binary, version and `ssh --proxy-mode` support rather than assuming a package/version from an old example; use ADC authentication, a supported SSH key and the skill's cleared-PYTHONPATH bridge. Activate the selected GPU, record actual hardware, and verify grading isolation before running model work. Coordinate the skill's single-active-SSH constraint with IDE/transfer access. Complete the whole phase, export and verify private artifacts, publish the results checkpoint, then explicitly stop the named runtime and verify its state. `/content` is temporary; disconnecting SSH is not proof that the runtime stopped.
- **RunPod** (primary GPU provider, 2026-10-23): allocate with `runpodctl pod create` (SECURE cloud, GPU id + data center from `gpu list`, `--ports "22/tcp"`, container disk ≥15GB, volume ≥10GB); SSH keys must be registered on the account **before** pod boot (`runpodctl ssh add-key`); `runpodctl ssh info` yields ip/port for `~/.ssh/config` (endpoint changes on restart — re-read it); bill-by-the-second, no idle reclaim — always `pod remove` + verify `pod list`/`network-volume list` empty at closeout; a locally cancelled create may still have created the pod — always `pod list` after cancelling. CPU pods get no SSH proxy (platform limitation, `reports/runpod-smoke.md`).
- **Modal** (`modal-deploy-ssh`): named sessions via the skill's lifecycle manager (`launch --name X --gpu L4 --cpu 4 --memory 16384 --timeout <s>`); the manager rewrites the managed block in `~/.ssh/config` (alias stable across respawns); `/workspace` volume persists, rootfs is ephemeral (reprovision after respawn); sandboxes stop at `--timeout` — set it to the planned wall clock; `stop --name X` resolves app IDs and never deletes the volume. Same isolation proof and closeout discipline as every provider.

Keep live SSH endpoints, credential details and sensitive session identifiers in the controller's private session record. Public Git manifests carry sanitized identifiers/hashes and shutdown evidence.

All providers must satisfy the same Linux grading contract. Authenticated SSH into a worker does not by itself provide candidate isolation. Re-provisioning an environment is separate from restoring checkpoint/data state.


## Before leaving any machine

1. Finish a coherent milestone or record it as interrupted. Capture verification results and the next action in STATE.md.
2. Upload large artifacts to durable private storage. Record immutable URI/revision, byte size, and checksum in a Git-tracked manifest. Confirm availability and integrity before shutting down.
3. For training, save the full recovery state described in DESIGN.md. A saved adapter alone is not a training resume checkpoint.
4. Inspect `git status`, `git diff`, and the staged diff. Stage explicit paths; commit code/configs/manifests/state together. Do not stage raw logs or credentials.
5. Push the branch. Verify local HEAD equals the remote branch and record branch/SHA in the handoff message. A later evidence commit can reference an earlier run's source SHA.
6. Stop the phase's Codespace or Colab runtime after the checkpoint/artifact copy and Git push are verified; record the provider's stopped-state evidence. From the controller, publish and verify a small state-only closeout commit with sanitized stop evidence; only then mark the phase complete. Release GPU resources before later CPU reporting. On failure, retain the local recovery evidence and report the blocker.

Commit at a coherent milestone, not every training step. Checkpoints may be more frequent than commits; each refers to the immutable run source SHA. A result commit records the verified checkpoint URI and step. If a push/upload fails, label the handoff incomplete and preserve its recoverable state. Do not leave paid compute running indefinitely: follow the run's previously chosen emergency durable-storage procedure and spending ceiling, and report any unrecoverable gap explicitly.

## On the destination machine

1. Use a separate clone. Check the working tree before syncing an existing checkout; never discard dirty work.
2. Fetch the branch and check out the base commit named in the run/handoff manifest, then restore the recorded executed-code identity — the worker result commit, or the retained patch/content hash for a dirty tree. Restoring the base commit alone can omit worker changes. Read STATE.md, PLAN.md, and DESIGN.md.
3. Restore the matching CPU environment or validated GPU lock; compare model/tokenizer revisions, template, GPU capabilities, data hashes, reward version, and grader image digest.
4. Download referenced artifacts and verify checksums. Never infer the latest dataset/checkpoint from a mutable directory name.
5. Run the phase's readiness checks, then begin the recorded next action. For recovery, restore full trainer state and record a child run ID pointing to its parent.

Before generation on any GPU host, prove that its Linux runner still enforces the CPU-tested isolation contract. GPU model work and CPU grading may share that machine, but candidate processes cannot access the trainer, credentials, checkpoints, or verifier. A new backend, precision, template, image or reward version is a new experimental condition, not a transparent machine move.

## Minimal recovery acceptance experiment

In Phase 6, train a few optimizer steps on the tiny diagnostic subset. Persist the complete checkpoint, dataset/fixture state and source manifest. Restore in a fresh process/checkout, verify saved step and state, and continue past that step. Compare with an uninterrupted short control under the same settings. Record the actual parameter/metric tolerance and unsupported state. Repeat the restore from durable storage rather than relying on the original machine's cache. Do not claim bitwise equivalence across GPU architectures without evidence.

## Required run/handoff fields

| Field | Purpose |
|---|---|
| Phase, status, next action | Continuation point |
| Skill identifier and retrievable revision/source (a hash alone is not restorable) | Exact lifecycle instructions used |
| Provider, actual session ID, SSH target and workspace | Reconnect to the right worker |
| Requested/actual resources, timeout and stop evidence | Resource accounting and verified shutdown |
| Controller and Git writer identity | Single-writer ownership |
| Branch, base Git SHA, results commit | Code and evidence provenance |
| Executed code identity (worker commit or patch/content hash) and launch snapshot | Exact code that ran, not just the base |
| Job ID, remote handle, heartbeat/log path and exit code | Resume the job, never duplicate it |
| Milestone status on the phase-state ladder | Resume from the first unverified milestone |
| Run ID and parent run | Experiment lineage |
| Model/tokenizer revision and template/thinking config | Starting policy identity |
| Dataset release/hash and split membership | Exact task identity |
| Verifier/reward version and Linux image digest | Exact scoring behavior |
| CPU/GPU lock hash and hardware | Runtime reconstruction |
| Artifact URIs, sizes, checksums | Durable restoration |
| Checkpoint step and saved state inventory | Training resume capability |
| Fixture seed schedule and reward group IDs | Same task conditions after recovery |
| Step/time/spend ceiling and emergency persistence procedure | Bounded run and shutdown behavior |
| Metrics, checks, failures, resource use | Evidence and limitations |

## Repository workflow

Use one writer per branch. Before a GPU handoff, the controller pushes the CPU milestone; the Colab worker fetches that exact source commit and runs it. The worker preserves private artifacts and returns sanitized results to the controller, which reviews and pushes the results/state commit before dependent CPU work. Fetch that published commit in the Codespace before continuing. If worker-side publication is explicitly selected, record its writer and result branch first. Parallel experiments use distinct branches and run IDs.

Neither an ephemeral GPU filesystem nor Git history alone is the complete project state. Resume requires both the Git checkpoint and the verified external artifacts.
