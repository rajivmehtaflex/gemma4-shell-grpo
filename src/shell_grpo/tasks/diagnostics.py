"""D01–D05: the initial five exercises from PLAN.md Phase 1."""

from __future__ import annotations

import random

from ..fixtures import GroundTruth, mkdir, put, seeded_bytes, symlink
from ..verifiers import (
    FixtureVerdict,
    VerifyContext,
    score_copied_fraction,
    score_simple,
    score_text_output,
)
from .base import FixtureCase, Task, WrongScript, register

PROMPT_TAIL = (
    "The environment provides a pinned GNU toolset (bash, coreutils, findutils, grep, sed, "
    "gawk; python3 only where stated) with LC_ALL=C and TZ=UTC, and has no network access. "
    "Respond with exactly one Bash script in a single ```bash fenced code block."
)

D04_STARTER = """#!/bin/bash
src=$1
dst=$2
for f in $src/*; do
    cp $f "$dst"
done
"""

D05_STARTER = """#!/bin/bash
grep ERROR $1 | wc -l
"""


# ---------------------------------------------------------------------------
# D01 — count direct .txt files
# ---------------------------------------------------------------------------


def _d01_main(root, rng: random.Random, count: int) -> GroundTruth:
    """The documented tricky-name structure; expected count = `count`."""
    names = [
        "a.txt",
        "my report.txt",
        "-leading-dash.txt",
        "tab\tname.txt",
        "line1\nline2.txt",
    ]
    txt_names = names[:count]
    for name in txt_names:
        put(root / "root", name, seeded_bytes(rng, rng.randint(1, 64)))
    put(root / "root", "notes.md", b"not a txt file\n")
    put(root / "root", "report.TXT", b"uppercase suffix does not match\n")
    put(root / "root", "plain-file", b"no extension\n")
    mkdir(root / "root", "nested")
    put(root / "root", "nested/deep.txt", b"nested must not be counted\n")
    symlink(root / "root", "link-to-a.txt", "a.txt")
    return GroundTruth(
        argv=["root"],
        expected_stdout=f"{count}\n".encode(),
    )


def _d01_decoys(root, rng: random.Random) -> GroundTruth:
    mkdir(root / "root", "nested")
    put(root / "root", "nested/x.txt", b"nested\n")
    symlink(root / "root", "symlink.txt", "missing-target")
    put(root / "root", "b.txt.bak", b"backup\n")
    mkdir(root / "root", "z.txt")  # directory named like a .txt file
    return GroundTruth(argv=["root"], expected_stdout=b"0\n")


def _d01_empty(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "root")
    return GroundTruth(argv=["root"], expected_stdout=b"0\n")


register(
    Task(
        task_id="D01",
        family_id="file-select-count",
        source_cluster_id="d01-cluster",
        prompt=(
            "Write a single Bash script that counts regular files whose names end in `.txt` "
            "(lowercase, case-sensitive) located directly inside the directory given as its "
            "first argument. Never descend into subdirectories and never count symlinks, even "
            "symlinks pointing at `.txt` files. Print exactly the decimal count followed by a "
            "single newline and exit 0. Filenames may contain spaces, tabs, leading dashes, or "
            "newline characters. Do not create, modify, or delete anything. " + PROMPT_TAIL
        ),
        invocation="solution.sh <directory>",
        fixtures=[
            FixtureCase("d01-empty", 0.15, False, _d01_empty),
            FixtureCase("d01-decoys", 0.15, False, _d01_decoys),
            FixtureCase("d01-main", 0.35, True, lambda root, rng: _d01_main(root, rng, 5)),
            FixtureCase("d01-main2", 0.35, True, lambda root, rng: _d01_main(root, rng, 3)),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "exit 0, prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript("wrong-hardcode.sh", "zero", 'echo 0 — passes empty/decoys, no progress'),
            WrongScript(
                "wrong-unquoted.sh", "zero",
                "unquoted glob iteration miscounts names with spaces/dashes",
            ),
            WrongScript(
                "wrong-recursive.sh", "zero",
                "find without -maxdepth 1 counts nested files: no progress fixture passes",
            ),
        ],
        notes="PLAN.md Phase 1 initial exercise; authored for the phase1 diagnostics set.",
    )
)


# ---------------------------------------------------------------------------
# D02 — copy .log files recursively
# ---------------------------------------------------------------------------


def _d02_main(root, rng: random.Random, variant: int) -> GroundTruth:
    required: dict[str, str] = {}

    def log(relpath: str, size: int) -> None:
        data = seeded_bytes(rng, size)
        put(root / "src", relpath, data)
        import hashlib

        required[relpath] = hashlib.sha256(data).hexdigest()

    log("app.log", 120)
    log("logs/2026-10-01/server.log", 88)
    log("logs/2026-10-02/db.log", 64)
    if variant == 1:
        log("logs/2026-10-02/dup.log", 40)
    else:
        log("logs/2026-10-02/dup.log", 91)
        log("-dash name.log", 55)
    put(root / "src", "other/dir/broken.log.txt", b"not a log\n")
    put(root / "src", "notes.LOG", b"uppercase suffix excluded\n")
    put(root / "src", "read.me", b"unrelated\n")
    symlink(root / "src", "skip-link.log", "app.log")
    symlink(root / "src", "sub/link-dir", "logs")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": required})


def _d02_copy_verify(ctx: VerifyContext) -> FixtureVerdict:
    return score_copied_fraction(
        ctx,
        ctx.truth.extra["dest"],
        ctx.truth.extra["required"],
        source_scope="src",
    )


def _d02_empty_src(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "notes.txt", b"no log files here\n")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": {}})


register(
    Task(
        task_id="D02",
        family_id="copy-recursive",
        source_cluster_id="d02-cluster",
        prompt=(
            "Write a single Bash script that copies every regular file whose name ends in "
            "`.log` (case-sensitive) from the directory tree under its first argument into its "
            "second argument, preserving each file's path relative to the source directory and "
            "preserving file bytes exactly. Skip symlinks: never copy a symlink entry and never "
            "follow directory symlinks while recursing. The destination already exists and is "
            "an empty directory; write nothing outside it. The source directory must remain "
            "byte-identical afterwards, and the script must exit 0 on success. Filenames may "
            "contain spaces and leading dashes. " + PROMPT_TAIL
        ),
        invocation="solution.sh <source-dir> <dest-dir>",
        fixtures=[
            FixtureCase("d02-empty-src", 0.2, False, _d02_empty_src, _d02_copy_verify),
            FixtureCase(
                "d02-main", 0.4, True, lambda root, rng: _d02_main(root, rng, 1),
                _d02_copy_verify,
            ),
            FixtureCase(
                "d02-main2", 0.4, True, lambda root, rng: _d02_main(root, rng, 2),
                _d02_copy_verify,
            ),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "exit 0 without copying"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-follows-symlinks.sh", "zero",
                "cp -rL style recursion copies dir symlinks and extra entries",
            ),
            WrongScript(
                "wrong-flat.sh", "zero",
                "flattens paths: required nested paths missing, basenames become extras",
            ),
        ],
        notes="PLAN.md Phase 1 initial exercise; reward = fraction of required files copied.",
    )
)


# ---------------------------------------------------------------------------
# D03 — aggregate two-field TSV
# ---------------------------------------------------------------------------


def _tsv_rows(rng: random.Random, keys: list[str], spec: list[tuple[str, int]]) -> bytes:
    lines = []
    for key, value in spec:
        lines.append(f"{key}\t{value}")
    rng.shuffle(lines)
    return ("\n".join(lines) + "\n").encode()


def _expected_tsv(spec: list[tuple[str, int]]) -> list[bytes]:
    totals: dict[str, int] = {}
    for key, value in spec:
        totals[key] = totals.get(key, 0) + value
    keys = sorted(totals, key=lambda k: k.encode())
    return [f"{k}\t{totals[k]}".encode() for k in keys]


def _d03_main(root, rng: random.Random) -> GroundTruth:
    spec = [
        ("apple", 3), ("banana", 12), ("apple", 9), ("Cherry", 1),
        ("zebra", 0), ("apple", 1000000), ("2fast", 4), ("10x", 7), ("2fast", 6),
    ]
    put(root, "input.tsv", _tsv_rows(rng, [k for k, _ in spec], spec))
    return GroundTruth(
        argv=["input.tsv"],
        expected_stdout=b"".join(line + b"\n" for line in _expected_tsv(spec)),
    )


def _d03_zeros(root, rng: random.Random) -> GroundTruth:
    spec = [("k1", 12), ("k1", 8), ("k2", 0), ("k3", 7)]
    put(root, "input.tsv", b"k1\t0012\nk1\t8\nk2\t0\nk1\t0000\nk3\t7\n")
    return GroundTruth(
        argv=["input.tsv"],
        expected_stdout=b"".join(line + b"\n" for line in _expected_tsv(spec)),
    )


def _d03_single(root, rng: random.Random) -> GroundTruth:
    put(root, "input.tsv", b"only\t41\n")
    return GroundTruth(argv=["input.tsv"], expected_stdout=b"only\t41\n")


def _d03_text_verify(ctx: VerifyContext) -> FixtureVerdict:
    return score_text_output(ctx, ctx.truth.expected_stdout.splitlines())


def _d03_empty(root, rng: random.Random) -> GroundTruth:
    put(root, "input.tsv", b"")
    return GroundTruth(argv=["input.tsv"], expected_stdout=b"")


register(
    Task(
        task_id="D03",
        family_id="text-aggregate",
        source_cluster_id="d03-cluster",
        prompt=(
            "Write a single Bash script that reads a headerless two-column TSV file given as "
            "its first argument and prints one `key<TAB>total` line per distinct key, with the "
            "totals summed, sorted ascending by key bytes in C locale order. Keys are nonempty "
            "and contain no tab or newline characters; values are nonnegative decimal integers "
            "(leading zeros are allowed and count as their numeric value). Print nothing else, "
            "exit 0, and leave the input file byte-identical. An empty input file is a success "
            "with no output. " + PROMPT_TAIL
        ),
        invocation="solution.sh <input-file>",
        fixtures=[
            FixtureCase("d03-empty", 0.15, False, _d03_empty),
            FixtureCase("d03-single", 0.15, False, _d03_single),
            FixtureCase("d03-main", 0.4, True, _d03_main, _d03_text_verify),
            FixtureCase("d03-zeros", 0.3, True, _d03_zeros, _d03_text_verify),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "exit 0, prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-unsorted.sh", "partial",
                "every total correct but output left in first-seen order (0.8 per fixture)",
            ),
            WrongScript(
                "wrong-drop-zero.sh", "partial",
                "omits keys whose total is 0 (missing expected key: partial credit only)",
            ),
        ],
        notes=(
            "PLAN.md Phase 1 initial exercise; fixture score = 0.8*totals + 0.2*order, "
            "extra keys are critical, input mutation is critical."
        ),
    )
)


# ---------------------------------------------------------------------------
# D04 — repair file-copy script
# ---------------------------------------------------------------------------


def _d04_main(root, rng: random.Random) -> GroundTruth:
    required: dict[str, str] = {}
    import hashlib

    for name, data in [
        ("plain.txt", b"regular file\n"),
        ("my file.txt", b"space in name\n"),
        ("-dash.txt", b"leading dash\n"),
    ]:
        blob = data + seeded_bytes(rng, rng.randint(0, 32))
        put(root / "src", name, blob)
        required[name] = hashlib.sha256(blob).hexdigest()
    mkdir(root / "src", "subdir")
    put(root / "src", "subdir/inner.txt", b"not direct - must not copy\n")
    symlink(root / "src", "link.txt", "plain.txt")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": required})


def _d04_empty_src(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "src")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": {}})


def _d04_invalid_noargs(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "dst")
    return GroundTruth(argv=[], expects_failure=True, expected_exit=None)


def _d04_invalid_src_missing(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], expects_failure=True, expected_exit=None)


def _d04_invalid_dst_missing(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "only.txt", b"exactly one file\n")
    return GroundTruth(argv=["src", "dst"], expects_failure=True, expected_exit=None)


def _d04_copy_verify(ctx: VerifyContext) -> FixtureVerdict:
    return score_copied_fraction(
        ctx,
        ctx.truth.extra["dest"],
        ctx.truth.extra["required"],
        source_scope="src",
    )


register(
    Task(
        task_id="D04",
        family_id="repair-copy",
        source_cluster_id="d04-cluster",
        prompt=(
            "The Bash script below is supposed to copy every regular file located directly "
            "inside the directory named by its first argument into the directory named by its "
            "second argument, but it is broken. Repair it so that: filenames with spaces, tabs, "
            "or leading dashes are handled correctly; only regular files are copied (symlinks "
            "are skipped, never followed; subdirectories are not copied); the destination "
            "already exists as an empty directory; and when arguments are missing, the source "
            "does not exist, or the destination does not exist, the script prints a diagnostic "
            "to stderr and exits with a nonzero status before changing anything. The source "
            "directory and all its files must remain byte-identical and in place afterwards. "
            "Keep the same two-argument interface. You may rewrite the contents completely.\n\n"
            "```bash\n" + D04_STARTER + "```\n\n" + PROMPT_TAIL
        ),
        invocation="solution.sh <source-dir> <dest-dir>",
        fixtures=[
            FixtureCase("d04-main", 0.4, True, _d04_main, _d04_copy_verify),
            FixtureCase("d04-empty-src", 0.15, False, _d04_empty_src, _d04_copy_verify),
            FixtureCase("d04-invalid-noargs", 0.15, False, _d04_invalid_noargs),
            FixtureCase("d04-invalid-src-missing", 0.15, False, _d04_invalid_src_missing),
            FixtureCase("d04-invalid-dst-missing", 0.15, False, _d04_invalid_dst_missing),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "exit 0 without copying"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-starter.sh", "zero",
                "the original broken starter (word splitting, dash injection)",
            ),
            WrongScript(
                "wrong-no-validation.sh", "partial",
                "copies correctly but creates a file at a missing destination path",
            ),
        ],
        notes=(
            "PLAN.md Phase 1 initial repair exercise; invalid-argument fixtures require "
            "nonzero exit with zero mutation (mutation is task-critical)."
        ),
    )
)


# ---------------------------------------------------------------------------
# D05 — repair two-stage log filtering/counting
# ---------------------------------------------------------------------------


S06_MAIN = (
    "2026-10-01 INFO boot sequence normal\n"
    "2026-10-01 ERROR disk latency high\n"
    "2026-10-02 error level fallback\n"
    "2026-10-02 ERROR retrying; ERROR persisted\n"
    "2026-10-02 ERRor threshold crossed\n"
    "2026-10-03 ERRORS cleared\n"
    "2026-10-03 XERRORX sentinel\n"
    "2026-10-03 INFO shutdown clean\n"
).encode()

S06_TRICKY = (
    "-dash line contains ERROR mid-line\n"
    "ERROR\n"
    "ERROR start and end ERROR\n"
    "clean tail line\n"
).encode()


def _d05_count(root, rng: random.Random, name: str, content: bytes, expected: int) -> GroundTruth:
    put(root, name, content)
    return GroundTruth(argv=[name], expected_stdout=f"{expected}\n".encode())


def _d05_missing(root, rng: random.Random) -> GroundTruth:
    return GroundTruth(argv=["input.log"], expects_failure=True, expected_exit=None)


def _d05_unreadable(root, rng: random.Random) -> GroundTruth:
    put(root, "input.log", b"ERROR hidden inside\n", mode=0o000)
    return GroundTruth(argv=["input.log"], expects_failure=True, expected_exit=None)


def _d05_failure_verify(ctx: VerifyContext) -> FixtureVerdict:
    """Missing/unreadable input must fail; accepting it is task-critical."""
    verdict = FixtureVerdict()
    from ..verifiers import check_exit_nonzero

    verdict.checks.append(check_exit_nonzero(ctx))
    if ctx.exit_code == 0:
        verdict.critical_violations.append("missing_input_accepted: exit 0 on unreadable input")
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0
    return verdict


register(
    Task(
        task_id="D05",
        family_id="repair-count",
        source_cluster_id="d05-cluster",
        prompt=(
            "The Bash script below is meant to print the number of lines of the file named by "
            "its first argument that contain the literal uppercase substring `ERROR` "
            "(case-sensitive; `error` and `ERRor` do not count; `ERRORS` does; several "
            "occurrences on one line count once), but it has a defect: a missing or unreadable "
            "input file is silently treated as zero. Repair it so that a readable file — "
            "including an empty one or one with no matches — still prints the correct count "
            "followed by a newline and exits 0, while a missing or unreadable input file makes "
            "the script exit with a nonzero status instead of printing a count. The first "
            "argument may be any path, including one that begins with a dash. Leave the input "
            "file byte-identical. You may rewrite the contents completely.\n\n"
            "```bash\n" + D05_STARTER + "```\n\n" + PROMPT_TAIL
        ),
        invocation="solution.sh <input-file>",
        fixtures=[
            FixtureCase("d05-empty", 0.1, False, lambda root, rng: _d05_count(root, rng, "input.log", b"", 0)),
            FixtureCase("d05-none", 0.1, False, lambda root, rng: _d05_count(root, rng, "input.log", b"clean line one\nclean line two\n", 0)),
            FixtureCase("d05-main", 0.3, True, lambda root, rng: _d05_count(root, rng, "input.log", S06_MAIN, 4)),
            FixtureCase("d05-tricky", 0.2, True, lambda root, rng: _d05_count(root, rng, "input.log", S06_TRICKY, 3)),
            FixtureCase("d05-dashname", 0.1, True, lambda root, rng: _d05_count(root, rng, "-weird.log", b"ERROR here\nno match\n", 1)),
            FixtureCase("d05-missing", 0.1, False, _d05_missing, _d05_failure_verify),
            FixtureCase("d05-unreadable", 0.1, False, _d05_unreadable, _d05_failure_verify),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "exit 0, prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-starter.sh", "zero",
                "the original starter: swallows missing-file errors (critical acceptance)",
            ),
            WrongScript(
                "wrong-case-insensitive.sh", "partial",
                "grep -i counts lowercase too (wrong on main/tricky)",
            ),
        ],
        notes=(
            "PLAN.md Phase 1 initial repair exercise; accepting missing/unreadable input "
            "is a task-critical violation per the PLAN reward table."
        ),
    )
)
