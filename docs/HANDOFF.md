# CPU/GPU handoff and recovery

## Before leaving any machine

1. Finish a coherent milestone or record it as interrupted. Capture verification results and the next action in STATE.md.
2. Upload large artifacts to durable private storage. Record immutable URI/revision, byte size, and checksum in a Git-tracked manifest. Confirm availability and integrity before shutting down.
3. For training, save the full recovery state described in DESIGN.md. A saved adapter alone is not a training resume checkpoint.
4. Inspect `git status`, `git diff`, and the staged diff. Stage explicit paths; commit code/configs/manifests/state together. Do not stage raw logs or credentials.
5. Push the branch. Verify local HEAD equals the remote branch and record branch/SHA in the handoff message. A later evidence commit can reference an earlier run's source SHA.
6. Release the GPU only after the checkpoint/artifact upload and Git push are verified. On failure, retain the local recovery evidence and report the blocker.

Commit at a coherent milestone, not every training step. Checkpoints may be more frequent than commits; each refers to the immutable run source SHA. A result commit records the verified checkpoint URI and step. If a push/upload fails, label the handoff incomplete and preserve its recoverable state. Do not leave paid compute running indefinitely: follow the run's previously chosen emergency durable-storage procedure and spending ceiling, and report any unrecoverable gap explicitly.

## On the destination machine

1. Use a separate clone. Check the working tree before syncing an existing checkout; never discard dirty work.
2. Fetch the branch and check out the source commit named in the run/handoff manifest. Read STATE.md, PLAN.md, and DESIGN.md.
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
| Branch, source Git SHA, results commit | Code and evidence provenance |
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

Use one writer per branch. Before a GPU handoff, push the CPU milestone; the GPU worker fetches that exact source commit and runs it. Persist artifacts and push a results/state commit from the GPU checkout before returning to CPU work. Fetch that commit on CPU before making dependent changes. Parallel experiments use distinct branches and run IDs.

Neither an ephemeral GPU filesystem nor Git history alone is the complete project state. Resume requires both the Git checkpoint and the verified external artifacts.
