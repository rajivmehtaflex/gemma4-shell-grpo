# Understanding the Plan: A Beginner's Guide

A plain-language companion to [PLAN.md](../PLAN.md), written for readers who are new to
reinforcement learning, GRPO, Unsloth, and TRL.

**PLAN.md remains the authoritative document.** Where this guide paraphrases something, PLAN.md
and [DESIGN.md](DESIGN.md) win. This guide exists to make PLAN.md readable on a first pass, and
to say *why* each of its somewhat unusual strictness exists.

**Status check while reading:** the infrastructure phases have now actually run. Phases 0–3
are complete with recorded evidence: the CPU grader is built and accepted (241/241), the Colab
L4 runtime has been activated for compatibility and baseline work, the untouched model's
baseline weakness report is published, and the first task-bank release `bank-v1` is built and
accepted (137/137 executions). **No policy training has happened** — that begins at Phase 6,
after difficulty screening (Phase 4) and the frozen plan (Phase 5). Codespaces and Colab have
both been activated and stopped under the recorded lifecycle; no runtime is running between
phases.

**Where the work happens:** ordinary CPU phases use **GitHub Codespaces** through the
`gh-cli-ops` skill; model/GPU phases use **Google Colab** through `colab-ssh-setup`. Each phase
includes starting or reconnecting to its machine, doing the whole phase, saving the results,
committing/pushing its milestone, and stopping the machine. Section 4 explains this workflow.

**Where tasks come from:** authored exercises — now confirmed by evidence. The Phase 3 source
preflight inspected the one naturally available Pi session and it yielded 0/5 plausible
exercises (it contained only Pi self-configuration, no shell work), so the pre-selected
authored-only fallback applies to release `bank-v1`. A future real Pi corpus can revisit this
without reopening the decision.

---

## 1. The one-sentence version

> Train Google's Gemma 4 E4B model to write better Bash scripts, by letting it try thousands of
> scripts, automatically scoring each one by actually running it, and adjusting the model so that
> the scripts which scored well become more likely — while measuring, with a controlled comparison,
> whether the model improves on tasks it never saw during training.

Three ideas carry the whole project:

1. **Score by doing, not by asking.** A candidate script is judged by *executing it* and checking
   its behavior, never by asking another AI "is this good?"
2. **Trust the instrument before using it.** Build and challenge the grader with authored
   exercises (Phase 1) before expanding the task bank (Phase 3) or training (Phase 6).
3. **A believable result needs a controlled comparison.** The trained model is compared against
   the untouched original under identical conditions, with a confidence interval, and a negative
   result is an acceptable outcome.

---

## 2. Vocabulary you need first

This is the part that usually blocks newcomers. Each term below is defined by its role in *this*
project, not by its general textbook meaning.

### 2.1 The model and its accessories

**Gemma 4 E4B** — the model under test. "E4B" is a size/architecture label, not a training
configuration. The project treats the *deployment alias* `gemma4:e4b` and the *actual trainable
checkpoint* as two different things: the alias does not tell you the precision, the chat template,
or the exact upstream revision, so PLAN.md Phase 2 requires pinning all of those down before
training.

**Tokenizer** — the component that converts text to tokens and back. The exact tokenizer
revision is recorded per run, because swapping it silently changes what the model sees.

**Chat template / thinking mode** — Gemma 4 can answer with or without visible reasoning. Unsloth's
docs specify two templates: `gemma-4` (non-thinking) and `gemma-4-thinking`. The plan requires
using the checkpoint's *native* template and recording it, and explicitly forbids bolting on the
Gemma 3 notebook's custom reasoning tags just to mimic its reward format.

**LoRA (Low-Rank Adaptation)** — a way to train a large model by updating a small set of added
"adapter" weights instead of all the weights. Much cheaper in VRAM and time. Crucially for this
project: LoRA here starts **completely fresh**. No previously trained adapter is loaded. That is
what "no SFT" means in practice.

**QLoRA** — LoRA on top of a quantized (compressed) model. Less VRAM, slightly more approximation
error. Unsloth's Gemma 4 guide recommends E4B QLoRA over E2B LoRA, noting the quantization
accuracy difference is negligible.

**VRAM** — the GPU's memory. It is the main currency of this project. Unsloth's docs give useful
orientation: Gemma 4 E2B LoRA fits in 8–10GB, E4B LoRA needs 17GB, and Gemma 4 RL is documented
working on 9GB for E2B. E4B RL will need more — which is exactly why PLAN.md says to *select
hardware from measurements*, not from the model name.

**Unsloth** — a library that wraps Hugging Face `transformers`/`trl` to train large models with
much less VRAM and faster. It also ships its own inference path used during RL generation.

**TRL (Transformer Reinforcement Learning)** — Hugging Face's trainer library. It contains
`GRPOTrainer`, the class that implements the GRPO training loop, and `GRPOConfig`, where the
hyperparameters live.

### 2.2 The learning machinery

**SFT (Supervised Fine-Tuning)** — the "normal" way to teach a model: show it many
question→answer pairs and train it to reproduce the answers. It teaches *what the answer looks
like*. This project forbids adding an SFT stage.

**RL / GRPO (Group Relative Policy Optimization)** — the "normal" way to teach a model to get
*better at a verifiable task*: let it attempt the task many times, score the attempts, and shift
probability toward the good ones. GRPO was popularized in the DeepSeekMath paper and is now the
standard approach for math/reasoning RL and, increasingly, for code.

**Rollout** — one full attempt: a prompt goes in, a completion comes out. In this project a
rollout also means generating a candidate Bash script and running it in the grader.

**Completion** — the model's answer text. In this project: one Bash script, expected inside a
single fenced `bash` block.

**Group (`num_generations`, written `G`)** — the `G` completions generated from the *same* prompt
in the same training step. GRPO compares candidates *within* a group. This is where the name comes
from: the reward is judged **relative to the other attempts at the same question**.

**Reward** — a number for a completion. Bigger is better. In this project it comes from the
grader: a weighted fraction of the task's functional checks, zero if the script did nothing
useful, and capped at 1.

**Reward function** — the Python callable that turns completions into rewards. TRL's interface
requires it to accept keyword arguments `prompts`, `completions`, `completion_ids`,
`trainer_state`, and any dataset columns, and to return a list of floats (one per completion).
Several reward functions may be passed as a list, combined as a weighted sum via
`reward_weights`. **Your grader plugs in here.**

**Advantage** — the number that says how much better than its group-mates a given completion was.
TRL computes it as:

```
advantage = (reward - mean(group rewards)) / std(group rewards)
```

**Reference policy** — a frozen copy of the original model. **KL divergence** measures how far
the training model has drifted from it, and can be added to the loss as a penalty to prevent
runaway drift. Current TRL defaults `beta = 0.0`, i.e. the KL term is off by default, following
recent practice. The plan still treats drift control as a real concern and freezes the setting
per experiment.

### 2.3 The verification machinery (this project's specialty)

**Grader / verifier** — the independent program that decides whether a candidate script did the
job. It builds a **fixture** (a temporary directory with known files, contents, and modes), runs
the script inside a restricted Linux container, computes the expected result independently, and
compares. It reports four things:

| Part | What it means |
|---|---|
| Named checks | Individual assertions, e.g. "selected exactly files A, B, C" |
| Critical violations | Preservation failures — the script deleted something it shouldn't have, or reached outside its sandbox |
| Score | A number in [0, 1]; this becomes the reward |
| Execution status | `ok` / `invalid_script` / `runtime_error` / `resource_limit` / `infrastructure_error` — only infrastructure errors leave the score unset |

That last row matters more than it looks. If the *grader* crashes, that is not evidence about
the *model*. Such cases are recorded as **unscorable** and fail the run's readiness gate, never
silently converted into "the model failed."

**Fixture** — the controlled input environment for one task: which files exist, their exact bytes,
permissions, the working directory, allowed output paths, and a generation seed. Every rollout
gets a fresh instance, and all candidates in one group share the same seeds so they face an
identical problem.

**Reward hacking** — the model learning to exploit the reward rather than do the task. Unsloth's
documentation describes the classic cases in a code setting: the model learns to *edit the timing
function* to report a fake result, to *cache* the answer and read it back, or to *outsource* the
work to a library when the task forbids it. In shell-script terms these are: hard-coding the
example answer, reading a stashed file, or tampering with the grading environment. One boundary
is worth stating plainly: **using permitted standard tools is not cheating.** A script that
solves the task with `find`, `awk`, or `sort` is a valid solution — cheating means violating a
restriction the task states or bypassing the grader, and the wrong-script checks target exactly
that (empty scripts, hard-coded answers, semantic errors), never legitimate tool use.

This is precisely why PLAN.md's Phase 1 wrong-script checks are not bureaucracy. A grader that
can be fooled will actively teach the model to fool graders, and the training curve will look
excellent while the model gets worse. Unsloth's own RL notebook handles this with separate
penalizing reward functions — a heavy negative score for a detected cheat — which is the same
shape as the plan's "critical violation" concept.

### 2.4 Infrastructure terms

**Fast inference / `fast_inference=False` / vLLM** — during RL, every training step generates many
completions, and that generation is usually the slow part. vLLM is a very fast inference server,
and TRL can use it for generation. The catch: **Unsloth's docs state that Gemma 4 RL works
without vLLM by setting `fast_inference=False` and using Unsloth's own inference instead.** So
the plan's conservative path (Unsloth + TRL, `fast_inference=False`) is not timidity — it is the
documented, supported route for this model. Accelerated generation stays optional and would need
its own parity evidence before being trusted.

**Checkpoint** — a saved snapshot of training state. An *adapter-only* export is an inference
artifact, not a training resume point. A true resume needs policy + optimizer + scheduler + RNG +
trainer state + data/fixture state, saved at an optimizer-step boundary.

**Manifest** — a small JSON file in Git recording the hashes and identifiers of things stored
outside Git: dataset release, model revision, image digest, reward version, artifact URIs and
checksums.

**Digest** — a content hash. Pinning a container by digest means "exactly this image," not
"whatever the tag points at today."

---

## 3. How GRPO actually runs, concretely

This is the core mental model, using the project's own domain. One training step, one prompt:

> **Prompt:** "Write a Bash script that lists the `.txt` files in the current directory, correctly
> handling filenames that contain spaces."

1. **Generate.** The model produces `G = 4` candidate scripts. TRL's `num_generations` controls
   this; the Unsloth/TRL examples commonly use 6.
2. **Grade.** Each script is extracted (one fenced `bash` block), run in a fresh restricted
   container against a fresh fixture, and graded. Suppose the results are:

   | Candidate | What it did | Reward |
   |---|---|---|
   | A | Crashed on the spaced filename (unquoted) | 0.0 |
   | B | Listed the right files but emitted an extra blank line | 0.5 |
   | C | Correct | 1.0 |
   | D | Correct, different implementation (`find` vs glob) | 1.0 |

3. **Normalize into advantages.** Mean reward = 0.625. The group's standard deviation is
   ≈ 0.415 (population convention), giving:

   | Candidate | Advantage | Meaning |
   |---|---|---|
   | A | −1.51 | strongly discouraged |
   | B | −0.30 | mildly discouraged |
   | C | +0.90 | encouraged |
   | D | +0.90 | encouraged |

   (Implementations differ on population vs sample standard deviation — with the sample
   convention the same rewards give ≈ 0.479 and advantages ≈ −1.31 / −0.26 / +0.78 / +0.78.
   The exact convention is frozen per experiment before training.)

4. **Update.** The model's weights move so that C- and D-style completions become slightly more
   likely, and A-style completions slightly less. Note that D is rewarded for a *different*
   implementation — GRPO does not push the model toward one canonical script.

5. **Control drift (optional).** If `beta > 0`, a KL penalty against the frozen original model
   is added to the loss.

Then the step repeats with new prompts. This is "online" learning: the training data is the
model's own fresh output, each step.

**The degenerate case, and why Phase 4 exists.** If all four candidates scored identically — say
all 1.0 or all 0.0 — the standard deviation is zero and the advantage carries no information.
Training on that prompt teaches nothing. TRL logs this directly as the
`frac_reward_zero_std` metric (the fraction of samples whose group reward had zero spread), and
PLAN.md Phase 4 requires inspecting exactly these all-equal groups rather than assuming training
will fix them.

One more TRL knob worth knowing, because PLAN.md Phase 5 freezes it: `scale_rewards` controls
the advantage formula's denominator. The default (`"group"`) standardizes within each group;
`"batch"` mixes in batch-level statistics; `False` disables std scaling entirely, which recent
work (the "Dr. GRPO" analysis) recommends to avoid a difficulty bias. It is a real, live choice —
not something to leave at a default and forget.

---

## 4. Who does the work, and on which machine?

Think of the project as a workshop with a coordinator and two workbenches.

- **The local controller** is the assistant coordinating from your computer. It reads the plan,
  chooses the next ready phase, connects to the right machine, checks the results, and records
  the handoff. Your computer is also where source files can be selected for authorized private
  transfer. Generated scripts are always executed inside the restricted grading environment.
- **GitHub Codespaces is the CPU workbench.** It is a remote development computer for ordinary
  programming and data preparation. We prioritize it for CPU phases, using the `gh-cli-ops`
  skill's Codespaces commands to find, start/connect to, and stop the correct workspace.
- **Google Colab is the GPU workbench.** A GPU can perform the model calculations needed for
  generation and training. We prioritize a named Colab runtime for GPU phases, using
  `colab-ssh-setup` to connect over SSH. SSH is the remote connection; it does not do the training.
- **Modal is the reserve workbench.** `modal-deploy-ssh` is used only after an explicit fallback
  decision if the preferred machine cannot meet the requirements. It is not started alongside
  every phase and is not selected automatically.

A **skill** is a set of instructions the assistant follows. It does not mean a machine is already
running or that phase code already exists. The assistant uses the skill to activate the worker,
then implements/runs that phase's work and checks. `gh-cli-ops` also supports the GitHub checks
and publication used at the end of every phase, including Colab phases.

### 4.1 The same complete cycle in every phase

Before every activation, re-read the **"Execution lessons learned (Phases 0–3)"** section near
the end of PLAN.md — every pitfall actually hit so far (Codespace idle stops, Colab runtime
reclaim, Gemma 4 processor quirks, fixture-authoring traps) is pre-recorded there with its
prevention rule as a binding part of the contract.

1. **Check the starting point.** Read STATE.md and the phase requirements. Confirm the right
   source-code version, files, account, machine resources, storage and spending limit. The
   controller also keeps a private per-run record folder (Git-ignored `runs/<run-id>/`) and
   checks its free space against what this phase plans to produce.
2. **Bootstrap or activate the workbench.** Reconnect to a suitable existing Codespace or Colab
   runtime; create one only if needed. The very first Codespace is a special case: it boots on
   the repository's default setup, and the team records what it actually contains — no pinned
   project environment exists until Phase 1 defines one. Confirm the Colab name before its first
   creation. Verify the actual worker identity, rather than assuming an old SSH shortcut still
   points to it.
3. **Restore the inputs.** Get the recorded code version, install the recorded software
   environment, and retrieve the matching private data/checkpoints. Check their file
   fingerprints (hashes). If work changes code on the worker, those changes travel back as a
   real commit or a saved patch — the recorded starting version alone never describes what
   actually ran.
4. **Do the entire phase, and track the work while it runs.** Run all its tasks and checks.
   Getting an SSH connection is the start of the work, not the completion signal. Every run gets
   a stable job identity with a heartbeat, a log location and, eventually, an exit code — so a
   dropped connection becomes a *reconnect-and-check* situation, never a reason to launch the
   same job a second time.
5. **Save and publish.** Copy large/private results to durable private storage and verify them.
   The controller reviews sanitized reports, updates STATE.md, commits the milestone, pushes it,
   and checks that GitHub has the same version. The controller is the default GitHub writer.
6. **Stop and record the next action.** Stop the active worker, check that the provider reports
   it stopped, and record where the next phase should pick up. Keep a verified artifact copy
   independent of that worker before stopping it. The controller then publishes a small final
   state update recording the verified shutdown, so the next phase sees what actually happened.

Stopping a Codespace preserves its workspace for its retention period; it is different from
deleting it. Storage can still have a cost. Colab's `/content` is temporary and must not be the
only copy of a dataset or training checkpoint. Closing SSH or the editor does not prove that
remote compute has stopped. Both CPU and GPU workspaces can have costs; check the limits first —
and a long paid run may only start once something (a watchdog or timeout) is proven able to stop
it at the budget deadline.

### 4.2 Which skill runs each phase?

| Phase | Machine activation skill | What the assistant completes there |
|---|---|---|
| 0 | `gh-cli-ops` → CPU Codespace | Runtime, storage and orchestration readiness checks |
| 1 | `gh-cli-ops` → CPU Codespace | Grader, five exercises, diagnostic checks |
| 2 | `colab-ssh-setup` → Colab GPU | Compatibility proof and original-model baseline |
| 3 | `gh-cli-ops` → CPU Codespace | Pi source audit; authored or mixed-source task construction, checks and splits |
| 4 | `colab-ssh-setup` → Colab GPU | Candidate generation, grading and difficulty screening |
| 5 | `gh-cli-ops` → CPU Codespace | Frozen dataset/configuration and GPU handoff |
| 6 | `colab-ssh-setup` → Colab GPU | Pilot, recovery demonstration and validation comparison |
| 7 | `colab-ssh-setup` → Colab GPU | Bounded main training run and checkpoint selection |
| 8 | Colab skill, then GH skill | GPU evaluation first; CPU analysis, reporting and final handoff second |

**Example:** Phase 3 finishes in Codespaces and saves the reviewed task bank privately. Its Git
milestone records the dataset fingerprint and storage reference. Phase 4 activates Colab,
restores exactly that version, and screens the tasks. The screening evidence is saved, its Git
checkpoint is published, and Colab is stopped. Phase 5 reconnects to Codespaces, retrieves that
evidence, and freezes the experiment. We move verified work between machines; we do not start
from memory each time.

### 4.3 Three different things that must be saved

| Item | Plain-language meaning | Where it belongs |
|---|---|---|
| Code and reports | The instructions and sanitized written results | Git/GitHub |
| Data and model checkpoints | The inputs and saved training progress | Private durable artifact storage |
| Run record | Which run did what: its job identity, logs, exact code identity and milestones | Private controller folder (Git-ignored `runs/`), never in Git |
| Session record | Which machine ran what, its resource limits and whether it stopped | Sanitized state/manifest; sensitive connection details remain private |

A checkpoint that can resume training includes more than the model's learned adapter. It also
includes the optimizer, training step and other recovery state described in HANDOFF.md. A saved
SSH address is not a saved training process. If a connection drops, check the provider's session
status *and* the run's job record (heartbeat, log, exit code) before reconnecting; never start a
duplicate job based on a lost connection alone.

The plan also tracks **how finished** a phase is, with words that each mean something specific:
`ready` → `running` → `work_verified` → `artifacts_verified` → `publish_pending` →
`machine_stopped` → `closeout_pending` → `complete` — plus `interrupted` whenever reality
interrupts. The purpose is honest resumability: after any failure, work resumes at the first
unverified step instead of repeating what already passed, and a phase is only `complete` when
both the results commit and the shutdown closeout commit are confirmed on GitHub.

Finally, **the cloud workspace is not automatically a safe script grader**. The GPU runtime has
CPU cores for checking scripts, but it must still enforce the same restricted Linux grading
rules as Codespaces. If that is impossible, stop that execution path and assess the fallback;
never run generated scripts directly in the SSH login environment.

---

## 5. The "no SFT" rule, and why it is phrased carefully

PLAN.md and DESIGN.md both insist on "no SFT," and both then immediately clarify what that means,
because the loose reading is wrong. The original E4B instruction checkpoint already includes
Google's own instruction training. "No SFT" means:

- no *additional* SFT stage in this project, and
- no previously trained or SFT-trained adapter is introduced.

It does **not** mean starting from a raw pretrained checkpoint with no instruction tuning. The
project starts from the original E4B instruction checkpoint, and adds only fresh LoRA adapters
trained by direct GRPO.

This is a real experimental choice with a real cost: without an SFT stage, the model has less
prior exposure to the task format, so the GRPO phase has to work harder, and Phase 2/Phase 4
measure whether it can. The plan is honest that this is a harder path, and the trade-off is
deliberate.

---

## 6. The nine phases, in plain language

### Phase 0 — Repository and evidence contract · *complete (run P0-20261021T1140)*

**Machine and skill:** Use `gh-cli-ops` to activate the CPU Codespace, finish the runtime, storage and orchestration checks, save their evidence, publish the milestone and stop the workspace. Repository creation itself is already done; no Pi-source sample is needed in this phase.

Create the repo, the planning documents, the state ledger, and the handoff rules, and push them
so a second machine can pick the work up. The rule for this project is that *state lives in Git
plus hashed external artifacts*, never in one machine's disk. The repository was created private
and is now public at the user's request; raw data and checkpoints stay out of Git regardless of
visibility.

Repository setup itself is done. Before Phase 1 implementation, record the CPU runtime contract
and the storage/orchestration evidence below. The Pi source audit belongs before Phase 3 task
construction and does not gate Phase 1.

- **Runtime capability contract** (`reports/runtime-capabilities.md`): define the grading
  runner's host requirements — architecture, namespaces and resource limits, unprivileged
  execution, fixture/result transport, external verifier access — *before* choosing a container
  engine. A pinned Linux/amd64 grading image is the initial cross-machine target; macOS
  development may use emulation. No paid GPU is needed for this check.

The orchestration revision added three more Phase 0 items, all about trusting the *workflow*
before trusting any results produced by it:

- **Claim the private handoff folder.** Select the Git-ignored controller-side `artifacts/`
  directory, check it can hold this phase's planned outputs, and record the estimate. The fully
  independent durable storage for model checkpoints remains a prerequisite to settle before
  Phase 2.
- **Bootstrap, don't assume.** The first Codespace boots on the repository's default setup;
  record the OS and tool versions it actually has, and create no GPU resources. Pinned project
  environments start with Phase 1.
- **Rehearse the whole lifecycle on something harmless** (`reports/orchestration-smoke.md`):
  run a tiny sentinel job, disconnect and reconnect, confirm it is the *same* run rather than a
  duplicate, copy its results back, compare hashes, push a sanitized evidence commit, stop the
  Codespace, and publish the closeout. Then deliberately simulate a failed upload and a failed
  push, and prove that partial copies are *not* treated as verified and that the phase can
  recover without rerunning the job. Before first real use, also do a read-only dry run of each
  skill — identity check, session selection, stop command — and record which skill revision was
  used, so the instructions themselves can be restored later.

### Phase 1 — Prove the CPU grader before trusting rewards · *complete (run P1-20261021T1805; reports/phase1-grader.md)*

**Machine and skill:** Activate the CPU Codespace with `gh-cli-ops`; build and check the whole grader/exercise phase, preserve its results, publish and stop.

**The most important phase in the plan.** Before anything else, build a grader you can actually
trust, and try to break it.

What "trustworthy" means here is concrete. Each of the first five exercises must:

- accept a **reference solution**;
- accept a **different valid implementation** — otherwise the grader is secretly hard-coded to
  one specific answer;
- reject **plausible wrong scripts** — empty script, hard-coded example answer, and a genuine
  semantic error such as an unquoted filename or wrong file selection;
- produce **identical results across three clean repetitions** — otherwise the reward signal is
  noise;
- for a task whose correct answer may legitimately be empty, also be checked on a declared
  **nonempty** case.

Alongside that: enforce isolation (bounded processes, CPU, memory, runtime, writable storage,
output volume), kill descendant processes, reset state after every candidate, and distinguish
model failures from infrastructure failures.

The plan now names the first five exercises explicitly, so "five exercises" is no longer
ambiguous:

- **D01** — count regular `.txt` files directly inside a directory argument (no recursion, no
  symlink following; tested with spaces, newlines, and leading dashes);
- **D02** — copy regular `.log` files recursively into an empty destination, preserving relative
  paths and exact bytes and skipping symlinks;
- **D03** — aggregate a two-column TSV file into one `key total` line per key, in C-locale key
  order;
- **D04** — repair a supplied file-copy script (quoting, option handling, exit-status
  propagation; specified invalid arguments must fail without mutating anything);
- **D05** — repair a supplied log-filtering script that counts lines containing the literal
  substring `ERROR` (prints zero for no matches, but fails on missing or unreadable input).

Two contract details matter as much as the exercises. First, the result is a typed schema —
`TaskRecord` and `GradeResult`, specified in `contracts.py` before any runner code — with the
five execution statuses above recorded for each fixture and for the task. A candidate error
contributes zero for its fixture; correctly scored fixtures can still earn partial reward.
Aggregate status uses this priority: `infrastructure_error`, `invalid_script`, `resource_limit`,
`runtime_error`, `ok`. Thus a script that runs on one fixture and crashes on another can have
status `runtime_error` and partial reward. Status describes execution; checks describe correctness.

An unresolved infrastructure error makes the task unscorable. Retry the exact same saved script
and fixture up to two more times; if it still fails, persist and invalidate the entire group and
halt for repair. Once every fixture is scored, any task-critical violation or no required
functional progress on the nonempty fixtures makes task reward zero. Passing an empty fixture
alone cannot reward a no-op. Full reward requires every required check to pass. The policy is
never updated while a group is partially scored, and candidates are never silently dropped or
replaced. Exact weights and boundary-case reward examples are specified before implementation.

Only after five exercises pass all of that do you scale to roughly twenty diagnostics covering
the three initial families: local file selection and quoting, deterministic text transformations,
and repair of short scripts. These twenty are *authored* diagnostics, explicitly not Pi-derived
data.

**Why this ordering:** the grader *is* the reward function, and GRPO optimizes exactly what the
reward says. A broken grader does not merely add noise — it teaches the model to be broken, and
it does so while the loss curve looks perfectly healthy. Building tasks before the grader is
known-good means every task inherits an unvalidated measurement instrument.

### Phase 2 — Prove E4B compatibility and measure the original model · *complete (runs P2-20261022TActiv + P2-20261022B; reports/baseline-diagnostics.md)*

**Machine and skill:** Activate Colab GPU with `colab-ssh-setup`; finish compatibility and baseline measurements, save the evidence, publish through the GH workflow and stop Colab.

This phase ran on the Colab L4 (`g-check-pi-exp`) and is complete. What it proved, in order:

- **The isolation contract survives without Docker.** The Colab host has no Docker daemon (and its
  kernel forbids forks inside a PID namespace), so the same restricted-grading rules were re-proved
  through a new *namespace engine* (`src/shell_grpo/ns_exec.py`): user+network namespaces with a
  direct uid-map write give an unprivileged, network-less candidate with `/root` protected. The
  "SSH login environment is not a grader" rule held — the contract was ported, not waived.
- **The sentinel came first.** A tiny job survived disconnect/reconnect with a hash-matched copy
  before any model work, and the L4 burn rate was measured (~2.8 L4-hours for the activation)
  before any long job.
- **The compatibility probe passed 6/6**: checkpoint pinned (`unsloth/gemma-4-E4B-it` at a frozen
  revision), finite loss/gradients with a fresh LoRA (34.9M trainable params at r=16), a real
  tiny GRPO step, adapter save/reload byte-identical, and thinking-mode generation at
  ~0.2 s/token. The dependency lock (`gpu.lock`, 107 pins) was frozen on the GPU host.
- **Real Gemma 4 gotchas were hit, not just read about**: the processor takes text only as a
  keyword argument (first positional is images), pad/eos attributes must be mirrored onto it, and
  `processing_class` must be passed explicitly to `GRPOTrainer`. These are now fixes in the repo's
  `generate.py`/`train.py`, not folklore.
- **Durable private storage went live before any model output existed**: a private Hugging Face
  repo — made private and *verified* (anonymous access → 401) after the upload tool turned out to
  create repos public by default.
- **The baseline was measured honestly**: the user-approved reduced scope (D01–D05, 4 samples
  each) scored **0/20 full passes, mean reward 0.241, zero critical violations**. The diagnosis
  order paid off — several failures were harness-side truncation (1024 tokens was too small; the
  thinking channel alone consumed the budget), now recorded as per-task budgets (≥2048 where
  truncation dominated). Huge GRPO headroom with partial-credit density on D01/D05.

The run survived three Colab runtime recycles (runtimes are reclaimed whenever no client is
connected — a lesson now binding in PLAN.md). The GPU was released after the weakness report was
published and everything synced.

Two *documented* Gemma 4 quirks still await the training phases (6–7) and are why the
compatibility probe deliberately exercised the real training path with tiny limits:
`use_cache=False` — which QLoRA tutorials commonly set — corrupts E2B/E4B attention (garbage
logits, diverging loss), so `use_cache=True` is mandatory at generation; and a training loss of
13–15 is *normal* for these models, as is a gradient-accumulation quirk that inflates reported
loss. Whoever watches the pilot's first steps should not mistake either for breakage.

### Phase 3 — Audit sources and build the reviewed task bank (CPU) · *complete (run P3-20261022T1900; reports/dataset-audit.md)*

**Machine and skill:** Activate the CPU Codespace with `gh-cli-ops`; finish dataset construction and its audit, save the private dataset, publish sanitized results and stop.

This phase ran and is complete — on the **authored-only** path, exactly as the fallback
anticipated:

- **The source preflight ran first and settled the question.** The one naturally available Pi
  session contained only Pi self-configuration (no shell work at all): exercise yield **0/5**,
  below the five-exercise bar. So no Pi parser was built and every task carries honest
  `source: authored` provenance (`reports/source-preflight.md`). A future real Pi corpus can
  revisit this without reopening the decision.
- **Twelve held-out tasks were authored**: T1a–T6b, six task families (dedup+order, column
  projection, suffix/prefix rename, zero-byte janitor, head–tail pair, line numbering) whose
  solution patterns deliberately overlap *no* development family — plus 65 candidate scripts
  (reference, alternate, and wrong scripts per task).
- **Splits were assigned by connected component, kept whole.** Release `bank-v1` (seeded,
  hash-pinned in `data/dataset/bank-v1/`) groups 32 tasks into 26 components over 21 families,
  with actual counts **11 train / 9 validation / 12 test** — reported as achieved rather than
  forcing the 60/20/20 aspiration by splitting related tasks. Integrity checks confirm no family
  spans two splits and the test pool contains *exclusively* held-out tasks. The known-good
  regression subset is a recorded deviation: the baseline had zero full-task successes to lock,
  so it degrades to the D01/D05 known-goods plus their fixture-level baseline successes.

  **Why components and not a random shuffle?** Because near-duplicate tasks leak. A paraphrased
  variant of a training task sitting in the test set inflates your result. The plan keeps
  variants, paraphrases, templates, and diagnostic derivatives in the *same* split by building a
  relationship graph and assigning whole connected components to one split — and forbids choosing
  test membership by looking at model scores. Diagnostics and their derivatives stay in the
  development pool, never in the final unseen test set.
- **The full acceptance harness then tried to break the bank — and succeeded three times.**
  137 executions at the published commit now pass, but getting there caught six real
  authoring/grader bugs: error-expecting fixtures whose ground truth declared success (the
  engine misclassified the script's *correct* exit-2), a verifier that wrapped a boolean in
  `all()`, fixture *data* that was wrong while both scripts were right (a trailing blank line
  changed "last line" semantics), bash `globstar` silently descending directory symlinks, a
  `case` pattern matching the literal two characters `\t`, and an anti-pattern wrong-script that
  passed by traversal-order luck (now made deterministically observable). This is the
  "trust the instrument before using it" principle doing its job — host unit tests with
  synthetic contexts caught none of these; only real grader execution did.
- **Reward ceilings against known hacks are now measured, not assumed**: a no-op earns 0,
  hard-coding the example answer caps at 0.7, skipping a stated validation requirement caps at
  0.85, and any critical violation zeroes the whole task. Full reward is unreachable by any
  shortcut recorded so far.

The full audit — composition, leakage checks, acceptance rounds, deviations — lives in
`reports/dataset-audit.md`. One subtlety worth knowing: `bank.jsonl` records the tasks but not
the wrong-script expectations or fixture ground truths — those live in registry code, so grader
behavior is pinned by the *code commit* (`ffd1f4d`), and any future task change must re-run
acceptance at the exact published commit.

### Phase 4 — Screen training difficulty with the untouched policy

**Machine and skill:** Activate Colab GPU with `colab-ssh-setup`; complete screening and grading, save its evidence, publish through the GH workflow and stop Colab.

Before spending money on a long run, find out whether the tasks are *learnable*. Use the
untouched original model to generate eight candidates per training prompt and look at:

- full-pass rate, functional progress, reward variation, truncation, scoring coverage;
- **all-equal groups** — prompts where every candidate scored the same, which carry no learning
  signal (TRL surfaces this as `frac_reward_zero_std`).

Prefer training tasks with genuinely mixed outcomes, keep easy tasks for coverage, and hold
harder ones in reserve. If a task is impossible or its grader is faulty, fix it or simplify it —
and if the task's *semantics* change, issue a new version rather than quietly editing the old
one. Do not screen the final test tasks.

**The gate:** the thresholds are predeclared, not vibes. A "useful" group has at least two
different functional rewards, and a task only counts as informative if a second, independent
group seed reproduces the result. Readiness requires at least 25% of screened training tasks to
be informative in both screenings, spanning at least five independent task families, with every
retained category covered. These are operational pilot thresholds, not guarantees of learning.
If they are not met, revise the tasks or the runtime *before* training — otherwise you would be
paying GPU time to train on noise. Every attempted candidate must end with a scored outcome or
an explicitly halted infrastructure failure, and the latter never counts as a low-reward
response.

### Phase 5 — Freeze the CPU release and the decision rule

**Machine and skill:** Activate the CPU Codespace with `gh-cli-ops`; finish packaging, freeze decisions and restore checks, save the release, publish the handoff and stop.

Everything becomes immutable, and an external machine must be able to reconstruct one exact
experiment from the pushed commit plus hashed artifacts.

You freeze: the dataset release and hashes; the script-extraction contract (tested against real
sampled E4B outputs); the fixture seed schedule; the reward definitions and per-task weights;
the matched inference settings; the analysis method (task-level pass rate, cluster bootstrap,
confidence interval) and the success target; and the training hyperparameters, checkpoint cadence,
step/time/spend ceilings, stop conditions, and maximum acceptable checkpoint loss.

The plan also bounds how many chances the experiment gets, because unlimited retries are a quiet
form of overfitting. The first 50–100-exercise release is **exploratory by default**: the
proposed +5-point target is a practical goal, not something the pilot is guaranteed to detect.
A *confirmatory* claim requires a precision/power assessment — from development data or
simulation — before anyone opens final-test outcomes. Training samples tasks uniformly from the
accepted pool with rotating group fixture seeds; no silent curriculum or adaptive filtering. The
campaign is capped at at most three pilot configurations, one primary training seed each, and
five scheduled validation checkpoints on the main run — and every attempted configuration goes
in the ledger, not just the winner. Evidence from a single training seed is reported as
conditional on that seed; method-level reliability needs separately budgeted replication.

**Grader-only fields never enter policy prompts.** A prompt must state every requirement the
verifier scores — bash/utility assumptions, argument conventions, allowed changes, output
requirements. If a scored requirement is hidden, the model is being tested on a secret.

Nothing about the test set may be changed after this point in response to test scores. Changes
create a new versioned run.

### Phase 6 — Train a short pilot and prove recovery

**Machine and skill:** Activate Colab GPU with `colab-ssh-setup`; finish the pilot, recovery test and validation comparison, save checkpoints, publish through the GH workflow and stop Colab.

Start from the original policy with fresh adapters, generate on-policy candidates, and score them
with the frozen external grader. No fixed Pi responses are substituted for real rollouts.

Then do the thing most people skip: **prove you can resume.** Train a few optimizer steps on a
tiny subset, save the full checkpoint, upload it, verify hashes, and restore it in a **fresh
process and a fresh checkout** from durable storage — not from the original machine's cache. Check
the saved step, optimizer, scheduler, RNG, and data/fixture state, then continue *past* that
step. Compare against an uninterrupted short control under identical settings and record the
actual numeric tolerance and any non-determinism.

Then compare the pilot against the untouched original on **validation** (never test). Proceed only
if all three hold: valid grading, successful recovery, and a positive functional validation
point estimate with no increase in observed critical violations. **Significance is not required**
for the pilot — a working trainer plus a promising direction is enough. A rising training reward
alone is not. Failed pilot revisions count against the frozen three-configuration campaign
limit; once the limit is reached, the result is reported and any further GPU runs require a new
documented research decision.

### Phase 7 — Run the bounded main experiment

**Machine and skill:** Activate Colab GPU with `colab-ssh-setup`; finish the bounded main run and checkpoint selection, save recovery artifacts, publish through the GH workflow and stop Colab.

The real run, under the frozen ceilings. Periodically validate and upload recovery checkpoints.
Stop honestly on invalid rewards, numerical failures, persistent scoring outages, or functional
regressions — and classify interruptions as interruptions rather than quietly dropping the
affected steps.

Select one checkpoint **using validation only**. Never pick by final-test performance.

### Phase 8 — Evaluate unseen behavior and close the loop

**Machine and skill:** Activate Colab for the final model comparisons and any export checks, save outputs, publish the GPU evidence checkpoint and stop its GPU. Then activate Codespaces through `gh-cli-ops` to finish the report/reproducibility handoff, publish and stop the CPU workspace.

Run the original and the selected policy on the frozen held-out tasks, under identical backend,
precision, template, thinking mode, and decoding settings, with equal generation budgets. Score
independent fixture copies against the same declared requirements.

Report: task-level single-attempt full-pass change, the paired cluster-based 95% confidence
interval, per-family regressions, critical violations, scoring coverage, truncation, and resource
cost. Report multi-sample success separately, as a secondary measure.

If an inference export is needed, reload and check it. A quantized or Ollama export is conditional
on deployment needs and gets its own matched comparison — training-backend gains do not
automatically transfer to a deployed quantized model.

**A defensible result includes a negative or inconclusive one.** The gate is a rigorous answer,
not a positive answer.

---

## 7. The four questions the plan asks before writing code

PLAN.md opens with four questions that shape every phase. They are worth reading as a checklist
for your own judgment:

1. **What would a specialist add?** Establish the baseline and challenge the grader before
   optimizing; distinguish runtime defects from model weaknesses; predeclare the comparison and
   stopping rules; demonstrate restoration before a long run.
2. **What raw material comes first?** For authored exercises: the explicit task brief, initial
   files/bytes/modes and independently checked expected behavior. For Pi additions: JSONL entries
   and branch IDs, original requests, exact commands/tool outputs and source model settings.
   Summaries and completed answers suggest tasks but do not prove correctness. Missing original
   state must be reconstructed and labeled, or excluded.
3. **Which methods and tools?** Branch-aware extraction; reproducible fixtures; reference and
   alternate solutions; deliberate wrong-script tests; family/source-grouped splits; matched
   baseline evaluation; on-policy GRPO; checkpoint interruption and recovery. Use the small
   stack, not a new orchestration platform.
4. **What independently establishes correctness?** Deterministic behavioral checks validated
   against known good and bad scripts, unseen task outcomes, paired uncertainty estimates,
   artifact hashes, and a fresh-process recovery demonstration. Neither an LLM judgment nor
   increasing training reward is sufficient.

---

## 8. The constraints, and the reasoning behind them

| Constraint | Why it exists |
|---|---|
| No additional SFT stage, no pre-trained adapter | Keeps the experiment a clean measurement of direct GRPO |
| One script per exercise, five exercises first, then ~20 diagnostics, then 50–100 | Feasibility sizes, not statistical guarantees — five perfect tasks beat fifty shaky ones |
| Initial scope: file selection/quoting, text transforms, short script repair | Keeps tasks reconstructible and verifiable; defers network, clock, and multi-turn complexity |
| Finish each phase's CPU preparation before renting GPU | Money and time; also the CPU work *gates* the GPU work |
| Codespaces for CPU, Colab for GPU; resources, isolation, storage and limits checked before activation | A preferred provider still needs a compatible, budgeted runtime |
| Activate, execute the whole phase, save, commit/push, stop | Connecting to a machine alone does not complete a phase |
| Every milestone ends with evidence, STATE.md update, explicit-path commit, push, remote verification | "It worked on my machine" is not a result |
| Freeze model/template/precision, splits, grader, and budgets per experiment | A silent change mid-run makes the result uninterpretable |
| The Gemma 3 notebook is a conceptual reference only | It is a Gemma 3/GSM8K tutorial, not a tested Gemma 4 environment; its pins and reward hacks are not to be copied |

And the **review focus** — the plan's own list of things most likely to go wrong, and where each
is addressed:

- Spaces, newlines, leading dashes, empty input, nested paths → Phase 1 and task-specific Phase 3
  checks.
- False rewards for doing nothing, hard-coding output, wrong file selection → the Phase 1 and
  Phase 3 wrong-script checks.
- Branches, compaction, source duplication, hidden requirements → the Phase 3 provenance and
  source-family split audits.
- Cross-candidate state, different fixtures inside a group, verifier tampering, infrastructure
  errors → the Phase 1 isolation checks and Phase 2 reward-alignment probes.
- Lost optimizer/RNG/data/fixture state on another machine → the Phase 6 restoration experiment
  before Phase 7.

---

## 9. How success is judged

The proposed acceptance target — a practical goal frozen before training, not a promised
detection:

- at least a **5 percentage-point** improvement in held-out task-level pass rate;
- the paired **95% confidence interval excludes zero**;
- **no increase** in observed critical violations.

Record three results separately: `effect_label` is `positive_gain`, `regression`, or
`inconclusive` according to whether the paired interval lies above zero, below zero, or includes
zero; `target_met` says whether the point estimate reaches the frozen practical target;
`safety_pass` says whether the observed critical-violation rate did not increase. Report the
underlying counts and rates too.

Accepted improvement requires a positive gain, the practical target and the safety constraint
all to pass. For example, a +6-point gain with an interval of +1 to +11 still fails acceptance
if critical violations increase. A +2-point gain with an interval of +1 to +3 is positive evidence
below the practical target. A negative interval is a regression. An interval containing zero
remains inconclusive even if its point estimate exceeds +5 points. See DESIGN.md for the full
rules; incomplete scoring must be repaired before classifying an outcome.

A small pilot may well remain inconclusive. The plan explicitly says: report the effect estimate
and the interval instead of expanding scope to force a positive finding. A working trainer is a
technical success, not proof of model improvement.

The default outcome is an **exploratory** estimate. Calling the result *confirmatory* requires a
precision/power assessment before final-test outcomes are opened, and the claim can never be
upgraded — nor the test set grown — in response to observed final-test scores.

**The statistics matter here.** The unit of evidence is the *connected component* of the plan's
relationship graph — source episodes linked through shared episodes, forks, paraphrases, task
templates, and diagnostic derivatives — not the number of fixture variants or sampled responses,
because those are not independent. (This matters especially for authored tasks: two exercises
built from one template are related even with different source episodes.) A bootstrap over these
components is what makes the confidence interval honest. Reporting a point estimate over 100
correlated fixture variants would be a way to manufacture significance, and the plan's insistence
on counting independent components is designed to prevent exactly that.

---

## 10. Where to start, concretely

Phases 0–3 are complete. The recorded state as of 2026-10-22:

- **Grader (Phase 1):** built and accepted — twenty authored diagnostics, 241/241 acceptance
  executions in a digest-pinned image (`reports/phase1-grader.md`); seven of the ten collected Pi
  candidates verified through it.
- **GPU compatibility + baseline (Phase 2):** Colab L4 probe passed 6/6 with the namespace
  grading engine re-proving isolation on a Dockerless host; `gpu.lock` frozen; durable private
  HF storage live (privacy verified); the untouched model scored **0/20 full passes, mean 0.241**
  (`reports/baseline-diagnostics.md`) — huge headroom, with per-task budgets recorded (≥2048
  tokens where truncation dominated).
- **Task bank (Phase 3):** authored-only after the 0/5 preflight; release `bank-v1` — 32 tasks,
  26 components kept whole, splits 11/9/12, held-out test pool T1–T6 — accepted 137/137
  executions at `ffd1f4d` (`reports/dataset-audit.md`).
- **Everything is stopped**: no Codespace or Colab runtime is running between phases; results
  and closeout commits are synced with the remote.

What comes next is **Phase 4 — difficulty screening with the untouched policy**, on Colab. The
inputs it needs all exist: the bank-v1 development-pool tasks, the frozen gpu.lock, the namespace
engine, the generate/evaluate entry points, and the baseline budgets. It generates eight
candidates per training prompt, grades them through the frozen grader, and applies the
predeclared readiness thresholds (≥25% informative tasks in both screenings, ≥5 families) to
decide which tasks enter the Phase 5 frozen plan. Before activating Colab, re-read the
**"Execution lessons learned (Phases 0–3)"** section in PLAN.md — it is binding, and it is the
difference between repeating six known failures and skipping them. One standing scope note: the
matched-budget baseline comparison belongs to the Phase 5 frozen plan, and queued operational
debt says raw completions must sync on the same cadence as records.

---

## 11. Where the detailed contracts live

This guide is an orientation. The binding details live in:

| Document | What it holds |
|---|---|
| [PLAN.md](../PLAN.md) | The nine-phase roadmap, per-phase file lists, gates, and the current next action |
| [DESIGN.md](DESIGN.md) | Task, fixture, reward, split, artifact, and state contracts in full |
| [STATE.md](../STATE.md) | Current state, decisions taken, pending decisions, and the evidence ledger |
| [HANDOFF.md](HANDOFF.md) | The CPU/GPU handoff and recovery protocol, and the required run/handoff fields |
| [AGENTS.md](../AGENTS.md) | Working rules for agents (and humans) working in this repo |

## 12. Reference material worth reading directly

- TRL GRPO Trainer: https://huggingface.co/docs/trl/grpo_trainer
- Unsloth RL guide: https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide
- Unsloth Gemma 4 training guide: https://unsloth.ai/docs/models/gemma-4/train
- Unsloth on RL reward hacking: https://unsloth.ai/docs/get-started/reinforcement-learning-rl-guide/advanced-rl-documentation/rl-reward-hacking
- GRPO paper (DeepSeekMath, introduced GRPO): https://huggingface.co/papers/2402.03300
- DeepSeek-R1 (popularized GRPO for reasoning): https://huggingface.co/papers/2501.12948
- Pi session format: https://pi.dev/docs/latest/session-format
- Gemma 4: https://deepmind.google/models/gemma/gemma-4/

Fetch these at the moment a phase begins rather than trusting a summary — including this one.
Documentation in this area moves quickly, and PLAN.md explicitly says so.
