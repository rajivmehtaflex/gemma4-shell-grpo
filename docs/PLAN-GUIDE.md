# Understanding the Plan: A Beginner's Guide

A plain-language companion to [PLAN.md](../PLAN.md), written for readers who are new to
reinforcement learning, GRPO, Unsloth, and TRL.

**PLAN.md remains the authoritative document.** Where this guide paraphrases something, PLAN.md
and [DESIGN.md](DESIGN.md) win. This guide exists to make PLAN.md readable on a first pass, and
to say *why* each of its somewhat unusual strictness exists.

**Status check while reading:** this repository currently contains planning documents only. No
model has been loaded, no shell script has been generated or executed, no GPU has been rented, and
no training has run. Everything below describes work that is planned, not work that has happened.

---

## 1. The one-sentence version

> Train Google's Gemma 4 E4B model to write better Bash scripts, by letting it try thousands of
> scripts, automatically scoring each one by actually running it, and adjusting the model so that
> the scripts which scored well become more likely — while proving, with statistics, that the model
> genuinely got better on tasks it never saw during training.

Three ideas carry the whole project:

1. **Score by doing, not by asking.** A candidate script is judged by *executing it* and checking
   its behavior, never by asking another AI "is this good?"
2. **Trust the instrument before using it.** The grader is built and attacked (Phase 1) *before*
   any task data exists (Phase 3) and *before* any training happens (Phase 6).
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
work to a library that does it for free. In shell-script terms these are: hard-coding the
example answer, reading a stashed file, or calling a helper instead of writing the script.

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

3. **Normalize into advantages.** Mean reward = 0.625, standard deviation ≈ 0.331, so:

   | Candidate | Advantage | Meaning |
   |---|---|---|
   | A | −1.89 | strongly discouraged |
   | B | −0.38 | mildly discouraged |
   | C | +1.13 | encouraged |
   | D | +1.13 | encouraged |

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

## 4. The architecture sentence, decoded

PLAN.md's architecture paragraph is dense. Here it is clause by clause.

> **"CPU work discovers tasks, constructs fixtures, checks graders, and packages evidence."**

Everything that does not need a model runs on ordinary laptops. That is: deciding *what* to
train on (Phase 3, from your Pi session logs), building the test data each task needs, proving
the graders are trustworthy (Phase 1), and freezing and packaging everything for a reproducible
experiment (Phase 5).

> **"A temporary GPU worker generates candidates and trains the policy."**

Training needs a GPU, so you rent one for a while, do the model work there, and hand it back.
"Policy" is another word for "the model, as a thing that chooses actions." "Temporary" is
load-bearing: PLAN.md requires releasing the GPU at the end of every GPU phase, and never letting
paid compute idle indefinitely.

> **"Its local CPU resources may grade scripts, so no distributed grading service is required."**

Grading a shell script means *running* a shell script and checking the output — that is CPU work,
not GPU work. The rented GPU machine has CPU cores anyway, so grading happens on that same box.
The alternative — a networked grading service the candidate scripts call into — would add
infrastructure, add a network attack surface, and add a service to keep alive. The plan prefers
the simpler design, and the *isolation* requirements (no network, no host mounts, no credentials,
no container socket, no access to the verifier) are checked on the CPU machine **and** the GPU
host.

> **"Pushed Git commits plus verified external artifacts preserve state between machines."**

You will move between machines constantly. Git holds code, configs, plans, and reports. Git cannot
hold model weights, datasets, or raw logs, so those live in durable storage and Git records their
addresses and checksums. Neither alone is the complete project state — you need both. A commit
tells you *what code ran*; an artifact tells you *what it ran on*.

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

### Phase 0 — Repository and evidence contract · *setup complete, preflights unstarted*

Create the repo, the planning documents, the state ledger, and the handoff rules, and push them
so a second machine can pick the work up. The rule for this project is that *state lives in Git
plus hashed external artifacts*, never in one machine's disk. The repository was created private
and is now public at the user's request; raw data and checkpoints stay out of Git regardless of
visibility.

Repository setup itself is done, but the plan adds two CPU-only preflights that must be recorded
before any Phase 1 code is written:

- **Source preflight** (`reports/source-preflight.md`): locate the user-designated Pi sessions,
  inspect up to ten representative sessions locally, and confirm at least five plausible
  exercises exist across the initial categories. Commit sanitized counts and provenance hashes
  only. If fewer usable tasks exist, stop for a dataset-scope decision rather than pretend a
  Pi-derived corpus exists.
- **Runtime capability contract** (`reports/runtime-capabilities.md`): define the grading
  runner's host requirements — architecture, namespaces and resource limits, unprivileged
  execution, fixture/result transport, external verifier access — *before* choosing a container
  engine. A pinned Linux/amd64 grading image is the initial cross-machine target; macOS
  development may use emulation. No paid GPU is needed for this check.

### Phase 1 — Prove the CPU grader before trusting rewards

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
five execution statuses above, per-fixture aggregation by declared weights, and any critical
violation zeroing the whole task. Second, the scoring failure protocol: a broken candidate
scores zero, but a genuine infrastructure error retries the exact same saved script and fixture
up to two more times; if it still fails, the entire group is invalidated, persisted, and the run
halts for repair. The policy is never updated while a group is partially scored, and candidates
are never silently dropped or replaced.

Only after five exercises pass all of that do you scale to roughly twenty diagnostics covering
the three initial families: local file selection and quoting, deterministic text transformations,
and repair of short scripts. These twenty are *authored* diagnostics, explicitly not Pi-derived
data.

**Why this ordering:** the grader *is* the reward function, and GRPO optimizes exactly what the
reward says. A broken grader does not merely add noise — it teaches the model to be broken, and
it does so while the loss curve looks perfectly healthy. Building tasks before the grader is
known-good means every task inherits an unvalidated measurement instrument.

### Phase 2 — Prove E4B compatibility and measure the original model

Now rent a GPU — but first confirm the runner still enforces the Phase 1 isolation contract on
that host, and that the host is not allowed to proceed if it cannot. Then:

- pin the exact upstream checkpoint and tokenizer revision, plus precision, template, thinking
  mode, and decoding settings;
- verify that attaching a **fresh** adapter does not change the initial baseline beyond a
  documented numeric tolerance (this is the "no SFT" rule under test);
- demonstrate finite gradients, a **nonzero change in trainable parameters**, correct
  prompt/candidate/reward alignment, and adapter save/reload;
- introduce the minimal shared `generate.py` / `evaluate.py` / `train.py` entry points that the
  baseline, screening, pilot, and main runs all reuse — the compatibility probe deliberately
  exercises the same training path as the later pilot, just with tiny limits, and every
  evaluation produces a per-task/per-candidate record (hashes, complete script, score, checks,
  status, truncation, timing) that all later comparisons reuse;
- record generation/grading wall time, peak VRAM, and CPU utilization — and pick hardware from
  those measurements;
- then, in a **separate process**, reload the untouched original policy and measure the baseline
  weaknesses honestly, diagnosing in a fixed order: extraction/runner defects first, then
  template/truncation/runtime problems, then actual shell behavior.

That diagnosis order is a nice piece of engineering reasoning: before blaming the model for
writing bad scripts, prove the harness is not stealing its output.

Two Gemma 4 specifics make this phase genuinely necessary rather than bureaucratic. Unsloth's
docs record a bug where `use_cache=False` — which QLoRA tutorials commonly set, and which
`gradient_checkpointing=True` forces — corrupts Gemma 4 E2B/E4B attention (these models share KV
state across layers), producing garbage logits and diverging training loss. Unsloth also notes
that a training loss of 13–15 is *normal* for Gemma 4 E2B/E4B, and documents a separate
gradient-accumulation bug that inflates reported loss. A beginner would reasonably conclude that
training is broken; the plan's demand for recorded compatibility evidence exists precisely so
these known quirks are separated from genuine failures.

The phase ends with a baseline weakness report, and the GPU is released.

### Phase 3 — Build reviewed tasks from raw Pi evidence (CPU)

Now, and only now, look at your Pi session logs and build real tasks. The plan is unusually strict
about provenance, because a session log contains a lot of things that are *not* correctness
evidence.

What counts as raw evidence: the session JSONL branch, the original user requirements, the exact
commands and their arguments, the tool outputs, the source model and runtime settings, and the
initial files/bytes/permissions needed to reproduce the task. What does **not** count:
compaction summaries and assistant answers that *look* successful. Those are discovery aids.

Handling rules: preserve raw sources privately and create sanitized derivatives; mark
reconstructed environments as *reconstructed*, not as historical snapshots; if the original state
is missing, either reproduce the behavior in a newly authored fixture or exclude the task; and
remove secrets and private content from anything publishable.

Then build tasks to target the **measured** Phase 2 weaknesses, cluster them into families and
source clusters, and assign train/validation/test splits **before** generating variants — with
held-out families reserved to measure transfer.

**Why split by family and source cluster, and not by random shuffle?** Because near-duplicate
tasks leak. A paraphrased variant of a training task in the test set inflates your result. The
plan keeps variants, paraphrases, branches, and closely related source tasks in the same split,
and forbids choosing test membership by looking at model scores.

The current plan makes this concrete: build a relationship graph over shared source episodes,
forks, paraphrases, templates, and diagnostic derivatives, and assign whole connected components
to one split, targeting roughly 60/20/20 across train/validation/test while reporting the actual
counts achieved. Diagnostics and their derivatives never enter the final unseen test set, and a
small known-good shell regression subset — tasks the original baseline already solves — stays
locked inside validation for every later policy comparison.

Every task must pass the Phase 1 acceptance checks, and no generated answer ever becomes a
training target. Reference solutions may validate fixtures and graders; they are not examples to
imitate.

### Phase 4 — Screen training difficulty with the untouched policy

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

The real run, under the frozen ceilings. Periodically validate and upload recovery checkpoints.
Stop honestly on invalid rewards, numerical failures, persistent scoring outages, or functional
regressions — and classify interruptions as interruptions rather than quietly dropping the
affected steps.

Select one checkpoint **using validation only**. Never pick by final-test performance.

### Phase 8 — Evaluate unseen behavior and close the loop

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
2. **What raw material comes first?** The Pi JSONL entries and branch IDs, original requests,
   exact commands and tool outputs, source model settings, and initial files/bytes/modes.
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
| Provider, isolation capability, artifact storage, spend limits resolved before provisioning | No paid resources on assumptions |
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

A small pilot may well remain inconclusive. The plan explicitly says: report the effect estimate
and the interval instead of expanding scope to force a positive finding. A working trainer is a
technical success, not proof of model improvement.

The default outcome is an **exploratory** estimate. Calling the result *confirmatory* requires a
precision/power assessment before final-test outcomes are opened, and the claim can never be
upgraded — nor the test set grown — in response to observed final-test scores.

**The statistics matter here.** The unit of evidence is the *source cluster*, not the number of
fixture variants or sampled responses, because those are not independent. A bootstrap over
clusters is what makes the confidence interval honest. Reporting a point estimate over 100
correlated fixture variants would be a way to manufacture significance, and the plan's insistence
on counting independent clusters is designed to prevent exactly that.

---

## 10. Where to start, concretely

Phase 0's repository setup is done; what comes next is its two preflights, then the Phase 1
specification. All of it is CPU-only and cheap:

1. **Run the source preflight.** Locate the user-designated Pi sessions, inspect up to ten
   representative sessions locally, and check that at least five plausible exercises exist
   across the initial categories. Record schema versions, available command/tool evidence,
   missing filesystem state, reconstruction effort, and exclusions in
   `reports/source-preflight.md` — sanitized counts and provenance hashes only. If the source
   material cannot support five exercises, stop for a dataset-scope decision.
2. **Record the runtime capability contract.** Write down the grading runner's host requirements
   — architecture, namespaces, resource limits, unprivileged execution, fixture/result
   transport, external verifier access, availability on candidate GPU host types — in
   `reports/runtime-capabilities.md`, *before* picking an engine. The initial cross-machine
   target is a pinned Linux/amd64 grading image; macOS development may use emulation. When this
   gate opens, research current engine options with exa/Context7: Docker with a digest-pinned
   image, Podman rootless, or `bubblewrap`/`nsjail` with a seccomp profile for a lighter-weight
   sandbox.
3. **Specify, then implement, the Phase 1 contracts.** Write and review the five exact prompts
   (D01–D05 above), invocation examples, typed `TaskRecord`/`GradeResult` schema examples,
   reward tables, and the scoring failure protocol *before* writing runner code. Then lock a
   CUDA-free CPU environment, fresh per-candidate fixtures, and fixed utility versions, locale,
   and timezone. Do not assume a container freezes the clock; if a task depends on the time,
   define a reference time explicitly.
4. **Build the five exercises end to end**, with the positive / alternate / wrong / repeatable
   evidence attached to each.
5. **Then** scale to ~20 diagnostics, and only after that think about GPU work.

The preflights and all of Phase 1 are CPU-only. No GPU is needed yet, and nothing is blocked on
the pending GPU provider/storage decisions.

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
- GRPO paper (DeepSeekMath): https://huggingface.co/papers/2501.12948
- Pi session format: https://pi.dev/docs/latest/session-format
- Gemma 4: https://deepmind.google/models/gemma/gemma-4/

Fetch these at the moment a phase begins rather than trusting a summary — including this one.
Documentation in this area moves quickly, and PLAN.md explicitly says so.
