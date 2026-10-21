"""S08–S10: script-repair diagnostics from the Pi campaign."""

from __future__ import annotations

import random

from ..fixtures import GroundTruth, mkdir, put, symlink
from ..verifiers import (
    CheckResult,
    FixtureVerdict,
    VerifyContext,
    check_exit_equals,
    check_stderr_nonempty,
    check_stdout_empty,
    violation_if_changed,
)
from .base import FixtureCase, Task, WrongScript, register
from .s_fileops import PROVENANCE, _err
from .s_text import S06_MAIN, S06_NONE, S06_TRICKY, _count_fixture, _unreadable_file

S08_STARTER = """#!/bin/bash
for f in $1/*; do
    cp $f "$2"
done
"""

S09_STARTER = """#!/bin/bash
pattern="$1"
file="$2"
grep "$pattern" "$file"
"""

S10_STARTER = """#!/bin/bash
count=$(grep "ERROR" "$1" | wc -l)
echo "$count"
"""

S09_INPUT = (
    "the quick brown fox\n"
    "value a.b appears here\n"
    "value aXb would match a regex\n"
    "line with -n as data\n"
    "path is /etc/config\n"
    "ERROR only for flavor\n"
).encode()


# ---------------------------------------------------------------------------
# S08 — repair misquoted copying
# ---------------------------------------------------------------------------


def _s08_main(root, rng: random.Random) -> GroundTruth:
    import hashlib

    required: dict[str, str] = {}
    files = [
        ("plain.txt", b"regular file\n"),
        ("my file.txt", b"space in name\n"),
        ("-dash.txt", b"leading dash\n"),
        ("tab\tname.txt", b"tab in name\n"),
        (".hidden", b"dotfile one\n"),
        (".cfg", b"dotfile two\n"),
    ]
    for name, data in files:
        put(root / "src", name, data)
        required[name] = hashlib.sha256(data).hexdigest()
    symlink(root / "src", "link-to-plain.txt", "plain.txt")
    mkdir(root / "src", "sub")
    put(root / "src", "sub/inner.txt", b"subdir must not copy\n")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": required})


def _copy_verify(ctx: VerifyContext) -> FixtureVerdict:
    from ..verifiers import score_copied_fraction

    return score_copied_fraction(
        ctx, ctx.truth.extra.get("dest", "dst"), ctx.truth.extra.get("required", {}),
        source_scope="src",
    )


def _s08_empty_src(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "src")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": {}})


def _s08_dst_missing(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "plain.txt", b"x\n")
    return _err(["src", "dst"])


def _s08_dst_notdir(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "plain.txt", b"x\n")
    put(root, "dst", b"regular file\n")
    return _err(["src", "dst"])


def _s08_dst_notempty(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "plain.txt", b"x\n")
    mkdir(root, "dst")
    put(root / "dst", "existing.txt", b"dst must stay unchanged\n")
    return _err(["src", "dst"])


def _s08_src_missing(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "dst")
    return _err(["src", "dst"])


def _s08_noargs(root, rng: random.Random) -> GroundTruth:
    return _err([])


register(
    Task(
        task_id="S08",
        family_id="repair-copy",
        source_cluster_id="s08-cluster",
        prompt=(
            "The Bash script below is supposed to copy every regular file located directly "
            "inside the directory named by its first argument into the directory named by its "
            "second argument, but it is broken. Repair it so that: filenames with spaces, "
            "tabs, leading dashes, or other awkward characters are handled correctly; only "
            "regular files are copied (symlinks are skipped, never followed); the destination "
            "must already exist as an empty directory, otherwise print a diagnostic to stderr "
            "and exit with status 2 before copying anything; the source directory and all its "
            "files remain byte-identical and in place afterwards. Keep the same two-argument "
            "interface and the same file name `solution.sh`. You may rewrite the contents "
            "completely as long as the interface and behavior are as specified.\n\n"
            "```bash\n" + S08_STARTER + "```\n"
        ),
        invocation="solution.sh <source-dir> <dest-dir>",
        fixtures=[
            FixtureCase("s08-main", 0.3, True, _s08_main, _copy_verify),
            FixtureCase("s08-empty-src", 0.1, False, _s08_empty_src, _copy_verify),
            FixtureCase("s08-dst-missing", 0.12, False, _s08_dst_missing),
            FixtureCase("s08-dst-notdir", 0.12, False, _s08_dst_notdir),
            FixtureCase("s08-dst-notempty", 0.12, False, _s08_dst_notempty),
            FixtureCase("s08-src-missing", 0.12, False, _s08_src_missing),
            FixtureCase("s08-noargs", 0.12, False, _s08_noargs),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "copies nothing: no progress on main"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-glob-only.sh", "partial",
                "quoted glob * but no dotfile handling: misses .hidden/.cfg (4/6)",
            ),
            WrongScript(
                "wrong-starter.sh", "zero",
                "the unmodified starter: word splitting, dash injection, no validation",
            ),
        ],
        notes=(
            "Frozen campaign brief S08; authored defective starter (recorded as authored in "
            "all provenance records). A bare * glob does not match dotfiles."
        ),
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S08.md",
                          "fixture_spec": "pi-sessions/fixtures/S08.md",
                          "starter": "authored defective starter, not a Pi mistake"},
    )
)


# ---------------------------------------------------------------------------
# S09 — repair option handling (literal search)
# ---------------------------------------------------------------------------


def _s09_term(
    term: str,
    expected_stdout: bytes | None,
    *,
    missing_file: bool = False,
    failure_exit: int | None = None,
):
    """failure_exit: when set, the fixture expects that exact nonzero exit."""
    def build(root, rng: random.Random) -> GroundTruth:
        if not missing_file:
            put(root, "input.txt", S09_INPUT)
        if failure_exit is not None:
            return GroundTruth(
                argv=[term, "input.txt"], expects_failure=True, expected_exit=failure_exit
            )
        return GroundTruth(argv=[term, "input.txt"], expected_stdout=expected_stdout)

    return build


def _s09_success_verify(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 0))
    expected = ctx.truth.expected_stdout or b""
    verdict.checks.append(
        CheckResult("stdout_exact", ctx.stdout == expected, True,
                    f"expected {len(expected)}B, got {len(ctx.stdout)}B")
    )
    if violation_if_changed(ctx, verdict, "", label="input"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


def _s09_nomatch_verify(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 1))
    verdict.checks.append(check_stdout_empty(ctx))
    if violation_if_changed(ctx, verdict, "", label="input"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


def _s09_error_verify(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 2))
    verdict.checks.append(check_stdout_empty(ctx))
    verdict.checks.append(check_stderr_nonempty(ctx))
    if violation_if_changed(ctx, verdict, "", label="input"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


def _s09_multiline_term(root, rng: random.Random) -> GroundTruth:
    put(root, "input.txt", S09_INPUT)
    return GroundTruth(argv=["a\nb", "input.txt"], expects_failure=True, expected_exit=2)


def _s09_unreadable(root, rng: random.Random) -> GroundTruth:
    put(root, "input.txt", b"ERROR hidden\n", mode=0o000)
    return GroundTruth(argv=["ERROR", "input.txt"], expects_failure=True, expected_exit=2)


register(
    Task(
        task_id="S09",
        family_id="repair-literal-search",
        source_cluster_id="s09-cluster",
        prompt=(
            "The Bash script below is a broken literal-search tool: it should print every "
            "line of the file named by its second argument that contains the search term "
            "given by its first argument, treated as a literal substring — never as a regular "
            "expression. Repair it so that: the term is matched literally, so characters like "
            "`.`, `*`, and `[` have no special meaning; a term beginning with a dash, such as "
            "`-n`, is treated as data and never as an option; an empty or missing term, or a "
            "term containing a newline, is rejected with a diagnostic on stderr and exit "
            "status 2; a missing or unreadable input file is also exit 2; matching lines are "
            "printed verbatim; the exit status is 0 when at least one line matches, exactly 1 "
            "when the file was read fine but nothing matched, and 2 only for genuine errors. "
            "Keep the same two-argument interface and the file name `solution.sh`.\n\n"
            "```bash\n" + S09_STARTER + "```\n"
        ),
        invocation="solution.sh <term> <input-file>",
        fixtures=[
            FixtureCase(
                "s09-literal-dot", 0.12, True,
                _s09_term("a.b", b"value a.b appears here\n"), _s09_success_verify,
            ),
            FixtureCase(
                "s09-dash-term", 0.12, True,
                _s09_term("-n", b"line with -n as data\n"), _s09_success_verify,
            ),
            FixtureCase(
                "s09-error-term", 0.08, True,
                _s09_term("ERROR", b"ERROR only for flavor\n"), _s09_success_verify,
            ),
            FixtureCase(
                "s09-nomatch", 0.1, False,
                _s09_term("zzz", None, failure_exit=1), _s09_nomatch_verify,
            ),
            FixtureCase(
                "s09-literal-brackets", 0.08, False,
                _s09_term("[x]", None, failure_exit=1), _s09_nomatch_verify,
            ),
            FixtureCase(
                "s09-empty-term", 0.1, False,
                _s09_term("", None, failure_exit=2), _s09_error_verify,
            ),
            FixtureCase(
                "s09-noargs", 0.1, False,
                lambda root, rng: GroundTruth(argv=[], expects_failure=True, expected_exit=2),
                _s09_error_verify,
            ),
            FixtureCase(
                "s09-multiline-term", 0.1, False, _s09_multiline_term, _s09_error_verify,
            ),
            FixtureCase(
                "s09-missing-file", 0.1, False,
                _s09_term("ERROR", None, missing_file=True, failure_exit=2), _s09_error_verify,
            ),
            FixtureCase(
                "s09-unreadable", 0.1, False, _s09_unreadable, _s09_error_verify,
            ),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-starter.sh", "partial",
                "the unmodified starter: literal-dot and dash fixtures fail, ERROR-term and errors pass",
            ),
            WrongScript(
                "wrong-grepi.sh", "partial",
                "grep -F is right but exit discipline lost: nomatch/brackets/errors fail",
            ),
        ],
        notes="Frozen campaign brief S09; new authored repair template.",
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S09.md",
                          "fixture_spec": "pi-sessions/fixtures/S09.md",
                          "starter": "authored defective starter, not a Pi mistake"},
    )
)


# ---------------------------------------------------------------------------
# S10 — repair swallowed pipeline errors (reuses S06's fixtures exactly)
# ---------------------------------------------------------------------------

_S10_CASES = [
    (fid.replace("s06-", "s10-"), weight, progress, builder)
    for fid, weight, progress, builder in [
        ("s06-main", 0.25, True, _count_fixture("a", S06_MAIN, 4)),
        ("s06-none", 0.1, False, _count_fixture("a", S06_NONE, 0)),
        ("s06-empty", 0.1, False, _count_fixture("a", b"", 0)),
        ("s06-tricky", 0.2, True, _count_fixture("a", S06_TRICKY, 3)),
        ("s06-missing", 0.1, False, lambda root, rng: _err(["input.log"])),
        ("s06-unreadable", 0.15, False, _unreadable_file("input.log")),
        ("s06-noargs", 0.1, False, lambda root, rng: _err([])),
    ]
]

register(
    Task(
        task_id="S10",
        family_id="repair-count",
        source_cluster_id="s10-cluster",
        prompt=(
            "The Bash script below is meant to print the number of lines of the file named "
            "by its first argument that contain the literal uppercase substring `ERROR`, but "
            "it has a serious defect: when the file is missing or cannot be read, the error "
            "is swallowed inside the pipeline and the script wrongly prints `0` and exits "
            "successfully. Repair it so that a missing or unreadable input file produces a "
            "diagnostic on stderr and exit status 2 with nothing on stdout, while a readable "
            "file — including an empty one or one with no matches — still prints the correct "
            "count followed by a newline and exits 0. The counting must remain a literal "
            "substring count, case-sensitive. You may keep the pipeline or replace it with "
            "any other valid implementation. Keep the same single-argument interface and the "
            "file name `solution.sh`.\n\n"
            "```bash\n" + S10_STARTER + "```\n"
        ),
        invocation="solution.sh <input-file>",
        fixtures=[FixtureCase(fid, w, prog, builder) for fid, w, prog, builder in _S10_CASES],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-starter.sh", "partial",
                "the unmodified starter: counts correctly but prints 0/exit 0 on missing input",
            ),
            WrongScript(
                "wrong-set-e.sh", "partial",
                "set -e cannot see through the pipeline: missing/unreadable still print 0",
            ),
        ],
        notes=(
            "Frozen campaign brief S10; reuses S06's fixture contents byte-for-byte so "
            "results are directly comparable across the template family."
        ),
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S10.md",
                          "fixture_spec": "pi-sessions/fixtures/S10.md",
                          "starter": "authored defective starter, not a Pi mistake"},
    )
)
