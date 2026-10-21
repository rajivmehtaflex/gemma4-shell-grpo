"""V01–V05: additional authored variant diagnostics (Phase 1, ~20 total).

These five extend the three families with distinct emphases (flat-copy
collision handling, size aggregation, safe listing, line slicing, argmax
selection). All are authored Phase 1 diagnostics in the development pool.
"""

from __future__ import annotations

import hashlib
import random

from ..fixtures import GroundTruth, mkdir, put, symlink
from ..verifiers import (
    CheckResult,
    FixtureVerdict,
    VerifyContext,
    score_copied_fraction,
    score_simple,
)
from .base import FixtureCase, Task, WrongScript, register

PROMPT_TAIL = (
    "The environment provides a pinned GNU toolset (bash, coreutils, findutils, grep, sed, "
    "gawk) with LC_ALL=C and TZ=UTC, and has no network access. "
    "Respond with exactly one Bash script in a single ```bash fenced code block."
)


# ---------------------------------------------------------------------------
# V01 — flat copy with collision refusal
# ---------------------------------------------------------------------------


def _v01_main(root, rng: random.Random) -> GroundTruth:
    required: dict[str, str] = {}
    for name, data in [
        ("a.log", b"alpha log\n"),
        ("nested/b.log", b"beta log\n"),
        ("deep/deeper/c.log", b"gamma log\n"),
    ]:
        put(root / "src", name, data)
        required[name.rsplit("/", 1)[-1]] = hashlib.sha256(data).hexdigest()
    put(root / "src", "notes.txt", b"not a log\n")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": required})


def _v01_collision(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "one/app.log", b"first app log\n")
    put(root / "src", "two/app.log", b"second app log\n")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], expects_failure=True, expected_exit=None)


def _v01_empty_src(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "notes.txt", b"no logs\n")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": {}})


def _v01_collision_verify(ctx: VerifyContext) -> FixtureVerdict:
    """Nonzero exit and zero writes anywhere (dst must stay empty)."""
    verdict = FixtureVerdict()
    verdict.checks.append(
        CheckResult("exit_nonzero", ctx.exit_code != 0, True, f"exit={ctx.exit_code}")
    )
    from ..verifiers import violation_if_changed

    if violation_if_changed(ctx, verdict, "", label="tree"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0
    return verdict


def _v01_verify(ctx: VerifyContext) -> FixtureVerdict:
    return score_copied_fraction(
        ctx, ctx.truth.extra["dest"], ctx.truth.extra["required"], source_scope="src"
    )


register(
    Task(
        task_id="V01",
        family_id="copy-flat",
        source_cluster_id="v01-cluster",
        prompt=(
            "Write a single Bash script that copies every regular file whose name ends in "
            "`.log` (case-sensitive) from anywhere under the directory tree of its first "
            "argument directly into its second argument (flattened: basenames only, no "
            "subdirectory structure). Skip symlinks. If two or more selected files share the "
            "same basename, print a diagnostic to stderr and exit with a nonzero status "
            "without writing anything. Otherwise exit 0 after copying. The destination "
            "already exists as an empty directory; write nothing outside it and leave the "
            "source tree byte-identical. " + PROMPT_TAIL
        ),
        invocation="solution.sh <source-dir> <dest-dir>",
        fixtures=[
            FixtureCase("v01-main", 0.5, True, _v01_main, _v01_verify),
            FixtureCase("v01-collision", 0.35, False, _v01_collision, _v01_collision_verify),
            FixtureCase("v01-empty-src", 0.15, False, _v01_empty_src, _v01_verify),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "copies nothing: no progress on main"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-late-check.sh", "zero",
                "detects collisions only after writing (mutation on collision fixture)",
            ),
            WrongScript(
                "wrong-silent-overwrite.sh", "zero",
                "writes through collisions and exits 0 (collision fixture: tree mutated)",
            ),
        ],
        notes="Authored Phase 1 variant: collision detection must precede any write.",
    )
)


# ---------------------------------------------------------------------------
# V02 — total size of direct .txt files
# ---------------------------------------------------------------------------


def _v02_main(root, rng: random.Random) -> GroundTruth:
    sizes = {}
    for name in ["a.txt", "my report.txt", "-dash.txt"]:
        data = b"z" * rng.randint(10, 200)
        put(root / "root", name, data)
        sizes[name] = len(data)
    put(root / "root", "notes.md", b"excluded\n")
    mkdir(root / "root", "nested")
    put(root / "root", "nested/deep.txt", b"x" * 999)  # nested: excluded
    symlink(root / "root", "link.txt", "a.txt")  # symlink: excluded
    return GroundTruth(argv=["root"], expected_stdout=f"{sum(sizes.values())}\n".encode())


def _v02_empty(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "root")
    return GroundTruth(argv=["root"], expected_stdout=b"0\n")


def _v02_decoys(root, rng: random.Random) -> GroundTruth:
    mkdir(root / "root", "nested")
    put(root / "root", "nested/deep.txt", b"only nested txt\n")
    symlink(root / "root", "link.txt", "missing")
    put(root / "root", "b.txt.bak", b"backup\n")
    return GroundTruth(argv=["root"], expected_stdout=b"0\n")


register(
    Task(
        task_id="V02",
        family_id="file-select-aggregate",
        source_cluster_id="v02-cluster",
        prompt=(
            "Write a single Bash script that computes the total size in bytes of all regular "
            "files whose names end in `.txt` (lowercase, case-sensitive) located directly "
            "inside the directory given as its first argument. Never descend into "
            "subdirectories and never count symlinks. Print exactly the decimal total "
            "followed by a single newline and exit 0; a directory with no such files prints "
            "`0`. Filenames may contain spaces, tabs, and leading dashes. Do not modify "
            "anything. " + PROMPT_TAIL
        ),
        invocation="solution.sh <directory>",
        fixtures=[
            FixtureCase("v02-main", 0.5, True, _v02_main),
            FixtureCase("v02-empty", 0.25, False, _v02_empty),
            FixtureCase("v02-decoys", 0.25, False, _v02_decoys),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-count-not-bytes.sh", "zero",
                "prints the file count instead of the byte total",
            ),
            WrongScript(
                "wrong-recursive.sh", "zero",
                "includes nested txt bytes: no progress fixture passes",
            ),
        ],
        notes="Authored Phase 1 variant: selection plus byte arithmetic.",
    )
)


# ---------------------------------------------------------------------------
# V03 — safe entry listing (repair)
# ---------------------------------------------------------------------------

V03_STARTER = """#!/bin/bash
for f in $(ls "$1"); do
    echo "$f"
done
"""


def _v03_main(root, rng: random.Random) -> GroundTruth:
    names = ["plain.txt", "my file.txt", "-dash.txt", "tab\tname.txt", ".hidden"]
    expected = b""
    for name in names:
        put(root / "root", name, b"data\n")
        expected += name.encode() + b"\n"
    return GroundTruth(argv=["root"], expected_stdout=expected)


def _v03_empty(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "root")
    return GroundTruth(argv=["root"], expected_stdout=b"")


def _v03_noargs(root, rng: random.Random) -> GroundTruth:
    return GroundTruth(argv=[], expects_failure=True, expected_exit=2)


def _v03_notdir(root, rng: random.Random) -> GroundTruth:
    put(root, "plainfile", b"regular file\n")
    return GroundTruth(argv=["plainfile"], expects_failure=True, expected_exit=2)


register(
    Task(
        task_id="V03",
        family_id="repair-listing",
        source_cluster_id="v03-cluster",
        prompt=(
            "The Bash script below should print the name of every entry located directly "
            "inside the directory given as its first argument, one name per line, in any "
            "order, but it is broken: parsing `ls` mangles names containing spaces or tabs, "
            "and names beginning with a dash leak into other commands. Repair it so every "
            "entry name — including dotfiles and names with spaces, tabs, or leading dashes, "
            "but never names containing newlines — is printed exactly, one per line. If the "
            "argument is missing or is not a directory, print a diagnostic to stderr, write "
            "nothing to stdout, and exit with status 2; otherwise exit 0. Do not modify "
            "anything.\n\n"
            "```bash\n" + V03_STARTER + "```\n\n" + PROMPT_TAIL
        ),
        invocation="solution.sh <directory>",
        fixtures=[
            FixtureCase("v03-main", 0.5, True, _v03_main),
            FixtureCase("v03-empty", 0.2, False, _v03_empty),
            FixtureCase("v03-noargs", 0.15, False, _v03_noargs),
            FixtureCase("v03-notdir", 0.15, False, _v03_notdir),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-starter.sh", "zero",
                "the ls-parsing starter: splits 'my file.txt' into two lines",
            ),
            WrongScript(
                "wrong-loses-dotfiles.sh", "partial",
                "glob * without dotglob: misses .hidden (4/5 names)",
            ),
        ],
        notes="Authored Phase 1 repair variant: ls parsing and dotfiles.",
    )
)


# ---------------------------------------------------------------------------
# V04 — line slicing
# ---------------------------------------------------------------------------


def _slice_fixture(content: bytes, expected: bytes, *, missing: bool = False):
    def build(root, rng: random.Random) -> GroundTruth:
        if not missing:
            put(root, "input.txt", content)
        return GroundTruth(argv=["input.txt"], expected_stdout=expected)

    return build


_V04_BODY = b"one\ntwo\nthree\nfour\nfive\nsix\n"
_V04_SHORT = b"alpha\nbeta\n"


register(
    Task(
        task_id="V04",
        family_id="text-slice",
        source_cluster_id="v04-cluster",
        prompt=(
            "Write a single Bash script that prints lines 2 through 4 (inclusive, 1-indexed) "
            "of the file given as its first argument, preserving the lines byte-for-byte. If "
            "the file has fewer lines, print whichever of those lines exist; a file with "
            "fewer than two lines produces no output. Exit 0 on success. If the argument is "
            "missing, or the file does not exist or cannot be read, print a diagnostic to "
            "stderr, write nothing to stdout, and exit with status 2. Leave the input "
            "byte-identical. " + PROMPT_TAIL
        ),
        invocation="solution.sh <input-file>",
        fixtures=[
            FixtureCase("v04-main", 0.35, True, _slice_fixture(_V04_BODY, b"two\nthree\nfour\n")),
            FixtureCase("v04-short", 0.2, True, _slice_fixture(_V04_SHORT, b"beta\n")),
            FixtureCase("v04-single-line", 0.1, False, _slice_fixture(b"only\n", b"")),
            FixtureCase("v04-empty", 0.1, False, _slice_fixture(b"", b"")),
            FixtureCase("v04-missing", 0.1, False, _slice_fixture(None, None, missing=True),
                        ),
            FixtureCase(
                "v04-unreadable", 0.15, False,
                lambda root, rng: (
                    put(root, "input.txt", b"secret\nlines\n", mode=0o000),
                    GroundTruth(argv=["input.txt"], expects_failure=True, expected_exit=2),
                )[1],
            ),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-off-by-one.sh", "zero",
                "prints lines 1-3: both progress fixtures wrong, so no progress at all",
            ),
            WrongScript(
                "wrong-swallow.sh", "zero",
                "silences missing-file errors like the S10 starter (missing fixture exit 0)",
            ),
        ],
        notes="Authored Phase 1 variant: slicing edge cases plus error discipline.",
    )
)


# ---------------------------------------------------------------------------
# V05 — largest .log file selection
# ---------------------------------------------------------------------------


def _v05_main(root, rng: random.Random) -> GroundTruth:
    put(root / "root", "a/small.log", b"x" * 10)
    put(root / "root", "b/big one.log", b"y" * 500)
    put(root / "root", "-dash.log", b"z" * 50)
    put(root / "root", "read.me", b"excluded\n")
    symlink(root / "root", "link-dir", "b")
    symlink(root / "root", "link.log", "b/big one.log")
    return GroundTruth(argv=["root"], expected_stdout=b"b/big one.log\n")


def _v05_tie(root, rng: random.Random) -> GroundTruth:
    put(root / "root", "a/x.log", b"same" * 10)
    put(root / "root", "b/x.log", b"same" * 10)
    return GroundTruth(argv=["root"], expected_stdout=b"a/x.log\n")


def _v05_none(root, rng: random.Random) -> GroundTruth:
    put(root / "root", "notes.txt", b"no logs at all\n")
    return GroundTruth(argv=["root"], expected_stdout=b"")


register(
    Task(
        task_id="V05",
        family_id="file-select-argmax",
        source_cluster_id="v05-cluster",
        prompt=(
            "Write a single Bash script that finds the largest regular file whose name ends "
            "in `.log` (case-sensitive) anywhere under the directory tree of its first "
            "argument and prints its path relative to that argument — without a leading "
            "`./` — followed by a single newline. Never follow or select symlinks. If "
            "several files tie for the largest size, print the one whose relative path comes "
            "first in plain byte order. If there are no matching files, print nothing and "
            "exit 0. Do not modify anything. Paths may contain spaces and leading dashes. "
            + PROMPT_TAIL
        ),
        invocation="solution.sh <directory>",
        fixtures=[
            FixtureCase("v05-main", 0.4, True, _v05_main),
            FixtureCase("v05-tie", 0.4, True, _v05_tie),
            FixtureCase("v05-none", 0.2, False, _v05_none),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-first-match.sh", "partial",
                "prints the first .log found instead of the largest: main fails, tie passes by luck",
            ),
            WrongScript(
                "wrong-maxdepth.sh", "zero",
                "checks only the top level: misses the nested winner; tie fixture prints nothing",
            ),
        ],
        notes="Authored Phase 1 variant: argmax selection with a deterministic tie rule.",
    )
)
