"""T1–T6: held-out test families (Phase 3, authored-only).

Six task families whose solution patterns are distinct from every development
family (file-select/copy/move/count/aggregate/repair families): dedup+order,
column projection, suffix rename, zero-byte janitor, head-tail pair, line
numbering. Per DESIGN.md these stay out of the development pool entirely and
form the reserved test components; they must never be trained on.
"""

from __future__ import annotations

import random

from ..fixtures import GroundTruth, mkdir, put, symlink
from ..verifiers import (
    CheckResult,
    FixtureVerdict,
    VerifyContext,
    check_exit_equals,
    score_simple,
    violation_if_changed,
)
from .base import FixtureCase, Task, WrongScript, register

PROMPT_TAIL = (
    "The environment provides a pinned GNU toolset (bash, coreutils, findutils, grep, sed, "
    "gawk) with LC_ALL=C and TZ=UTC, and has no network access. "
    "Respond with exactly one Bash script in a single ```bash fenced code block."
)

HOLDOUT_PROVENANCE = {
    "source": "authored",
    "pool": "held_out_test",
    "campaign": "phase3-task-bank",
    "rationale": (
        "reserved test family: solution pattern distinct from every development family; "
        "authored 2026-10-22 under the authored-only decision"
    ),
}


def _err(argv: list[str], exit_code: int = 2) -> GroundTruth:
    return GroundTruth(argv=argv, expects_failure=True, expected_exit=exit_code)


# ---------------------------------------------------------------------------
# T1 — dedup + order (family: dedup-order)
# ---------------------------------------------------------------------------


def _t1_file(root, rng: random.Random, content: bytes) -> GroundTruth:
    put(root, "input.txt", content)
    return GroundTruth(argv=["input.txt"])


def _unique_sorted(lines: list[bytes]) -> bytes:
    seen = sorted(set(lines))
    return b"".join(l + b"\n" for l in seen)


def _unique_first_seen(lines: list[bytes]) -> bytes:
    out, seen = [], set()
    for line in lines:
        if line not in seen:
            seen.add(line)
            out.append(line)
    return b"".join(l + b"\n" for l in out)


_T1_MAIN = b"zebra\napple\nzebra\nApple\napple  \n-dash line\napple\nmy line\napple\n"
_T1_DUPES_ONLY = b"same\nsame\nsame\n"


def _t1a_cases():
    return [
        FixtureCase("t1a-main", 0.4, True,
                    lambda root, rng: _t1_file(root, rng, _T1_MAIN),
                    lambda ctx: score_simple(ctx, _unique_sorted(_T1_MAIN.splitlines()))),
        FixtureCase("t1a-empty", 0.15, False,
                    lambda root, rng: _t1_file(root, rng, b""),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t1a-dupes-only", 0.15, False,
                    lambda root, rng: _t1_file(root, rng, _T1_DUPES_ONLY),
                    lambda ctx: score_simple(ctx, b"same\n")),
        FixtureCase("t1a-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t1a-missing", 0.15, False, lambda root, rng: _err(["input.txt"])),
    ]


register(Task(
    task_id="T1a", family_id="dedup-order", source_cluster_id="t1-cluster",
    prompt=(
        "Write a single Bash script that reads the file named by its first argument and "
        "prints its distinct lines sorted ascending by bytes in C locale order, one per "
        "line, with duplicates removed globally (case-sensitive; trailing spaces make a "
        "line distinct). Print nothing else and exit 0; an empty file produces no output. "
        "If the argument is missing or the file does not exist or cannot be read, print a "
        "diagnostic to stderr, write nothing to stdout, and exit with status 2. Leave the "
        "input byte-identical. " + PROMPT_TAIL
    ),
    invocation="solution.sh <input-file>",
    fixtures=_t1a_cases(),
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-keeps-dupes.sh", "zero", "plain sort: duplicates remain, main wrong"),
        WrongScript("wrong-hardcode.sh", "partial",
                    "hardcoded main output: passes main and error fixtures, "
                    "fails the distinct-data fixtures"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="sorted-unique"),
))

register(Task(
    task_id="T1b", family_id="dedup-order", source_cluster_id="t1-cluster",
    prompt=(
        "Write a single Bash script that reads the file named by its first argument and "
        "prints its distinct lines in order of their FIRST appearance (duplicates removed; "
        "a later duplicate never reprints the line). Print nothing else and exit 0; an "
        "empty file produces no output. If the argument is missing or the file does not "
        "exist or cannot be read, print a diagnostic to stderr, write nothing to stdout, "
        "and exit with status 2. Leave the input byte-identical. " + PROMPT_TAIL
    ),
    invocation="solution.sh <input-file>",
    fixtures=[
        FixtureCase("t1b-main", 0.4, True,
                    lambda root, rng: _t1_file(root, rng, _T1_MAIN),
                    lambda ctx: score_simple(ctx, _unique_first_seen(_T1_MAIN.splitlines()))),
        FixtureCase("t1b-empty", 0.15, False,
                    lambda root, rng: _t1_file(root, rng, b""),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t1b-single", 0.15, False,
                    lambda root, rng: _t1_file(root, rng, b"only line\n"),
                    lambda ctx: score_simple(ctx, b"only line\n")),
        FixtureCase("t1b-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t1b-missing", 0.15, False, lambda root, rng: _err(["input.txt"])),
    ],
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-sorted.sh", "zero", "sort -u: wrong order for first-seen semantics"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="first-seen-unique"),
))


# ---------------------------------------------------------------------------
# T2 — column projection (family: column-projection)
# ---------------------------------------------------------------------------


def _t2_file(root, rng: random.Random, content: bytes) -> GroundTruth:
    put(root, "input.tsv", content)
    return GroundTruth(argv=["input.tsv"])


_T2_MAIN = b"key1\tvalue one\nkey2\tvalue two\nKey3\tvalue three\n"


def _t2a_cases():
    return [
        FixtureCase("t2a-main", 0.4, True,
                    lambda root, rng: _t2_file(root, rng, _T2_MAIN),
                    lambda ctx: score_simple(ctx, b"value one\nvalue two\nvalue three\n")),
        FixtureCase("t2a-empty", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b""),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t2a-three-fields", 0.15, False,
                    lambda root, rng: (
                        put(root, "input.tsv", b"a\tb\tc\n"),
                        _err(["input.tsv"]),
                    )[1],
                    lambda ctx: score_simple(ctx, None, expects_failure=True, expected_exit=2)),
        FixtureCase("t2a-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t2a-missing", 0.15, False, lambda root, rng: _err(["input.tsv"])),
    ]


register(Task(
    task_id="T2a", family_id="column-projection", source_cluster_id="t2-cluster",
    prompt=(
        "Write a single Bash script that reads a headerless two-column TSV file named by "
        "its first argument and prints only the second field of every row, one per line, "
        "byte-for-byte. Every row must have exactly two tab-separated fields; if any row "
        "has a different field count, print a diagnostic to stderr, write nothing to "
        "stdout, and exit with status 2. An empty file produces no output and exit 0. A "
        "missing or unreadable input file is also exit 2 with empty stdout. Leave the "
        "input byte-identical. " + PROMPT_TAIL
    ),
    invocation="solution.sh <input-file>",
    fixtures=_t2a_cases(),
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-cut-novalidate.sh", "partial",
                    "cut -f2 without validation: solves main, prints through "
                    "malformed rows"),
        WrongScript("wrong-field1.sh", "zero", "prints the first field instead"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="field2"),
))

register(Task(
    task_id="T2b", family_id="column-projection", source_cluster_id="t2-cluster",
    prompt=(
        "Write a single Bash script that reads a headerless two-column TSV file named by "
        "its first argument and prints one line per row with the two fields swapped: "
        "`second<TAB>first`, byte-for-byte. Every row must have exactly two tab-separated "
        "fields; any other field count prints a diagnostic to stderr and exits with status "
        "2 with empty stdout. An empty file produces no output and exit 0. A missing or "
        "unreadable input file is also exit 2. Leave the input byte-identical. "
        + PROMPT_TAIL
    ),
    invocation="solution.sh <input-file>",
    fixtures=[
        FixtureCase("t2b-main", 0.4, True,
                    lambda root, rng: _t2_file(root, rng, _T2_MAIN),
                    lambda ctx: score_simple(
                        ctx, b"value one\tkey1\nvalue two\tkey2\nvalue three\tKey3\n")),
        FixtureCase("t2b-empty", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b""),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t2b-one-field", 0.15, False,
                    lambda root, rng: (
                        put(root, "input.tsv", b"only\n"),
                        _err(["input.tsv"]),
                    )[1],
                    lambda ctx: score_simple(ctx, None, expects_failure=True, expected_exit=2)),
        FixtureCase("t2b-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t2b-unreadable", 0.15, False,
                    lambda root, rng: (
                        put(root, "input.tsv", b"secret\trow\n", mode=0o000),
                        _err(["input.tsv"]),
                    )[1]),
    ],
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-same-order.sh", "zero", "echoes rows unchanged (no swap)"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="swap"),
))


# ---------------------------------------------------------------------------
# T3 — suffix/prefix rename (family: rename-batch)


def _t3_prefix_verify(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    truth = ctx.truth.extra
    renamed = truth["renamed"]
    placed = 0
    for name in renamed:
        old_entry = ctx.post.get(f"dir/{name}")
        new_name = f"backup-{name}"
        new_entry = ctx.post.get(f"dir/{new_name}")
        if old_entry is None and new_entry is not None and new_entry.kind == "file":
            placed += 1
    verdict.checks.append(
        CheckResult("renamed_correctly", placed == len(renamed), True,
                    f"{placed}/{len(renamed)} prefixed renames")
    )
    survivors_ok = (
        ctx.pre.get("dir/keep.txt") is not None
        and ctx.post.get("dir/keep.txt") is not None
        and ctx.pre["dir/keep.txt"].to_dict() == ctx.post["dir/keep.txt"].to_dict()
        and ctx.post.get("dir/link.conf") is not None
    )
    verdict.checks.append(
        CheckResult("others_untouched", survivors_ok, True, "symlink and keep.txt intact")
    )
    if not survivors_ok:
        verdict.critical_violations.append("collateral_mutation")
    if verdict.critical_violations:
        verdict.score = 0.0
        return verdict
    verdict.score = placed / len(renamed) if renamed else 1.0
    return verdict

# ---------------------------------------------------------------------------


def _t3_collision_verify(ctx: VerifyContext) -> FixtureVerdict:
    """Refusal fixture: nonzero exit, tree byte-identical."""
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 2))
    if violation_if_changed(ctx, verdict, "", label="tree"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


def _t3_main(root, rng: random.Random) -> GroundTruth:
    import hashlib

    renamed = {}
    for name in ["page1.htm", "my page.htm", "-odd.htm"]:
        data = f"content of {name}\n".encode()
        put(root / "dir", name, data)
        renamed[name] = hashlib.sha256(data).hexdigest()
    put(root / "dir", "keep.html", b"already html\n")
    mkdir(root / "dir", "sub")
    put(root / "dir", "sub/deep.htm", b"nested must not rename\n")
    symlink(root / "dir", "link.htm", "page1.htm")
    return GroundTruth(argv=["dir"], extra={"renamed": renamed})


def _t3_rename_verify(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    truth = ctx.truth.extra
    renamed = truth["renamed"]
    placed = 0
    failures = []
    for name, sha in renamed.items():
        new_name = name[:-4] + ".html"
        old_entry = ctx.post.get(f"dir/{name}")
        new_entry = ctx.post.get(f"dir/{new_name}")
        if old_entry is None and new_entry is not None and new_entry.kind == "file" and new_entry.sha256 == sha:
            placed += 1
        else:
            state = "still-present" if old_entry is not None else "target-missing-or-wrong"
            failures.append(f"{name}: {state}")
    verdict.checks.append(
        CheckResult("renamed_correctly", placed == len(renamed), True,
                    f"{placed}/{len(renamed)} renamed with bytes intact"
                    + ("; " + "; ".join(failures[:6]) if failures else ""))
    )
    survivors_ok = True
    for rel in ["dir/keep.html", "dir/sub/deep.htm"]:
        pre, post = ctx.pre.get(rel), ctx.post.get(rel)
        if pre is None or post is None or pre.to_dict() != post.to_dict():
            survivors_ok = False
    if ctx.pre.get("dir/link.htm") is not None and ctx.post.get("dir/link.htm") is None:
        survivors_ok = False  # symlink must survive untouched
    verdict.checks.append(
        CheckResult("others_untouched", survivors_ok, True,
                    "non-matching entries and symlink intact" if survivors_ok else "collateral change")
    )
    if survivors_ok is False and placed == len(renamed):
        verdict.critical_violations.append("collateral_mutation: non-matching entries changed")
    if verdict.critical_violations:
        verdict.score = 0.0
        return verdict
    verdict.score = placed / len(renamed) if renamed else 1.0
    return verdict


def _t3_main_cases():
    return [
        FixtureCase("t3a-main", 0.5, True, _t3_main, _t3_rename_verify),
        FixtureCase("t3a-collision", 0.2, False,
                    lambda root, rng: (
                        put(root / "dir", "a.htm", b"x\n"),
                        put(root / "dir", "a.html", b"existing target\n"),
                        GroundTruth(argv=["dir"], expects_failure=True, expected_exit=2),
                    )[2],
                    _t3_collision_verify),
        FixtureCase("t3a-empty", 0.15, False,
                    lambda root, rng: (
                        mkdir(root, "dir"),
                        GroundTruth(argv=["dir"]),
                    )[1],
                    lambda ctx: _t3_collision_verify_no_exit(ctx)),
        FixtureCase("t3a-noargs", 0.15, False, lambda root, rng: _err([])),
    ]


def _t3_collision_verify_no_exit(ctx: VerifyContext) -> FixtureVerdict:
    """Empty-dir success fixture: exit 0, tree unchanged, no output."""
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 0))
    if violation_if_changed(ctx, verdict, "", label="tree"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


register(Task(
    task_id="T3a", family_id="rename-batch", source_cluster_id="t3-cluster",
    prompt=(
        "Write a single Bash script that renames every regular file whose name ends in "
        "`.htm` located directly inside the directory given as its first argument, "
        "changing only the suffix to `.html` (page1.htm becomes page1.html). Never touch "
        "subdirectories or symlinks. If any target name already exists in that directory, "
        "print a diagnostic to stderr and exit with status 2 WITHOUT renaming anything. "
        "If the argument is missing or is not a directory, also exit with status 2. With "
        "no matching files, exit 0 and change nothing. Leave every other entry "
        "byte-identical. Names may contain spaces and leading dashes. " + PROMPT_TAIL
    ),
    invocation="solution.sh <directory>",
    fixtures=_t3_main_cases(),
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "renames nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-partial-rename.sh", "zero",
                    "renames then hits a collision: mutates on the collision fixture"),
        WrongScript("wrong-recursive.sh", "zero", "renames nested files too (critical mutation)"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="htm-html"),
))

register(Task(
    task_id="T3b", family_id="rename-batch", source_cluster_id="t3-cluster",
    prompt=(
        "Write a single Bash script that renames every regular file whose name ends in "
        "`.conf` located directly inside the directory given as its first argument by "
        "prefixing `backup-` to the name (old.conf becomes backup-old.conf). Never touch "
        "subdirectories or symlinks. If any target name already exists in that directory, "
        "print a diagnostic to stderr and exit with status 2 WITHOUT renaming anything. "
        "If the argument is missing or is not a directory, also exit with status 2. With "
        "no matching files, exit 0 and change nothing. Leave every other entry "
        "byte-identical. Names may contain spaces and leading dashes. " + PROMPT_TAIL
    ),
    invocation="solution.sh <directory>",
    fixtures=[
        FixtureCase("t3b-main", 0.5, True,
                    lambda root, rng: (
                        put(root / "dir", "app.conf", b"a\n"),
                        put(root / "dir", "my app.conf", b"b\n"),
                        put(root / "dir", "-weird.conf", b"c\n"),
                        put(root / "dir", "keep.txt", b"keep\n"),
                        symlink(root / "dir", "link.conf", "app.conf"),
                        GroundTruth(argv=["dir"], extra={
                            "renamed": {"app.conf": None, "my app.conf": None, "-weird.conf": None}}),
                    )[5],
                    _t3_prefix_verify),
        FixtureCase("t3b-collision", 0.2, False,
                    lambda root, rng: (
                        put(root / "dir", "a.conf", b"x\n"),
                        put(root / "dir", "backup-a.conf", b"existing target\n"),
                        GroundTruth(argv=["dir"], expects_failure=True, expected_exit=2),
                    )[2],
                    _t3_collision_verify),
        FixtureCase("t3b-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t3b-notdir", 0.15, False,
                    lambda root, rng: (
                        put(root, "plainfile", b"regular file\n"),
                        _err(["plainfile"]),
                    )[1]),
    ],
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "renames nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-suffix-not-prefix.sh", "zero", "renames to .conf.bak instead of prefixing"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="backup-prefix"),
))


# ---------------------------------------------------------------------------
# T4 — zero-byte janitor (family: zero-janitor)
# ---------------------------------------------------------------------------


def _t4_main(root, rng: random.Random) -> GroundTruth:
    removed = []
    for rel in ["a/empty1.dat", "b/deep/empty two.dat", "-dash-empty.dat"]:
        put(root / "root", rel, b"")
        removed.append(rel)
    put(root / "root", "keep.dat", b"nonzero\n")
    put(root / "root", "a/full.dat", b"data\n")
    symlink(root / "root", "link-to-empty.dat", "a/empty1.dat")
    symlink(root / "root", "link-dir", "a")  # dir symlink: never followed
    return GroundTruth(argv=["root"], expected_stdout=b"".join(
        rel.encode() + b"\n" for rel in sorted(removed, key=lambda s: s.encode())),
        extra={"removed": set(removed)})


def _t4_remove_verify(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    truth = ctx.truth.extra
    removed = truth["removed"]
    gone = 0
    for rel in sorted(removed):
        if f"root/{rel}" not in ctx.post:
            gone += 1
    verdict.checks.append(
        CheckResult("removed_exactly", gone == len(removed), True,
                    f"{gone}/{len(removed)} zero-byte files removed")
    )
    survivors = ["root/keep.dat", "root/a/full.dat", "root/link-to-empty.dat", "root/link-dir"]
    survivors_ok = all(
        rel in ctx.post and ctx.post[rel].to_dict() == ctx.pre[rel].to_dict()
        for rel in survivors if rel in ctx.pre
    )
    extras = sorted(
        n for n in set(ctx.pre) - set(ctx.post)
        if n not in {f"root/{r}" for r in removed}
    )
    if extras:
        survivors_ok = False
    verdict.checks.append(
        CheckResult("survivors_intact", survivors_ok, True,
                    "non-matching entries untouched" if survivors_ok else f"lost: {extras[:6]}")
    )
    if extras:
        verdict.critical_violations.append(f"overdeleted: {extras[:6]}")
    if verdict.critical_violations:
        verdict.score = 0.0
        return verdict
    verdict.score = gone / len(removed) if removed else 1.0
    return verdict


def _t4_main_cases():
    return [
        FixtureCase("t4a-main", 0.5, True, _t4_main, _t4_remove_verify),
        FixtureCase("t4a-empty-tree", 0.15, False,
                    lambda root, rng: (
                        mkdir(root, "root"),
                        GroundTruth(argv=["root"], expected_stdout=b""),
                    )[1],
                    lambda ctx: _t4_unchanged_success(ctx)),
        FixtureCase("t4a-no-matches", 0.2, False,
                    lambda root, rng: (
                        put(root / "root", "only.dat", b"nonzero\n"),
                        GroundTruth(argv=["root"], expected_stdout=b""),
                    )[1],
                    lambda ctx: _t4_unchanged_success(ctx)),
        FixtureCase("t4a-noargs", 0.15, False, lambda root, rng: _err([])),
    ]


def _t4_unchanged_success(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 0))
    if violation_if_changed(ctx, verdict, "", label="tree"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0
    return verdict


register(Task(
    task_id="T4a", family_id="zero-janitor", source_cluster_id="t4-cluster",
    prompt=(
        "Write a single Bash script that deletes every zero-byte regular file anywhere "
        "under the directory tree of its first argument and prints each removed file's "
        "path relative to that argument, one per line, sorted in plain byte order. Never "
        "delete anything else: files with content, symlinks (even symlinks to empty "
        "files), and directory-symlink targets must all survive untouched; never follow "
        "directory symlinks. Print nothing else and exit 0. If the argument is missing or "
        "is not a directory, print a diagnostic to stderr and exit with status 2. "
        + PROMPT_TAIL
    ),
    invocation="solution.sh <directory>",
    fixtures=_t4_main_cases(),
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "deletes nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-follows-links.sh", "zero",
                    "follows the dir symlink: deletes through it (critical overdelete)"),
        WrongScript("wrong-deletes-nonzero.sh", "zero", "deletes every file (critical overdelete)"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="delete-empty"),
))

register(Task(
    task_id="T4b", family_id="zero-janitor", source_cluster_id="t4-cluster",
    prompt=(
        "Write a single Bash script that counts the zero-byte regular files anywhere "
        "under the directory tree of its first argument and prints exactly that decimal "
        "count followed by a newline. Delete nothing; modify nothing. Never follow or "
        "count symlinks, even symlinks pointing at empty files. An empty tree or a tree "
        "with no zero-byte files prints `0`. If the argument is missing or is not a "
        "directory, print a diagnostic to stderr, write nothing to stdout, and exit with "
        "status 2. " + PROMPT_TAIL
    ),
    invocation="solution.sh <directory>",
    fixtures=[
        FixtureCase("t4b-main", 0.5, True,
                    lambda root, rng: _t4_main(root, rng),
                    lambda ctx: score_simple(ctx, b"3\n")),
        FixtureCase("t4b-empty-tree", 0.15, False,
                    lambda root, rng: (
                        mkdir(root, "root"),
                        GroundTruth(argv=["root"], expected_stdout=b"0\n"),
                    )[1],
                    lambda ctx: _t4_unchanged_success_stdout(ctx, b"0\n")),
        FixtureCase("t4b-no-matches", 0.2, False,
                    lambda root, rng: (
                        put(root / "root", "only.dat", b"nonzero\n"),
                        GroundTruth(argv=["root"], expected_stdout=b"0\n"),
                    )[1],
                    lambda ctx: _t4_unchanged_success_stdout(ctx, b"0\n")),
        FixtureCase("t4b-noargs", 0.15, False, lambda root, rng: _err([])),
    ],
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-deletes.sh", "zero", "counts then deletes (critical mutation)"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="count-only"),
))


def _t4_unchanged_success_stdout(ctx: VerifyContext, expected: bytes) -> FixtureVerdict:
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 0))
    from ..verifiers import check_stdout_exact

    verdict.checks.append(check_stdout_exact(ctx, expected))
    if violation_if_changed(ctx, verdict, "", label="tree"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


# ---------------------------------------------------------------------------
# T5 — head-tail pair (family: head-tail)
# ---------------------------------------------------------------------------


_T5_MAIN = b"alpha\nbravo\ncharlie\n\ndelta\n\n"
_T5_MAIN_EXPECTED = b"alpha\tdelta\n"


def _t5_cases():
    return [
        FixtureCase("t5a-main", 0.4, True,
                    lambda root, rng: _t2_file(root, rng, _T5_MAIN),
                    lambda ctx: score_simple(ctx, _T5_MAIN_EXPECTED)),
        FixtureCase("t5a-empty", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b""),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t5a-single", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b"only\n"),
                    lambda ctx: score_simple(ctx, b"only\tonly\n")),
        FixtureCase("t5a-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t5a-missing", 0.15, False, lambda root, rng: _err(["input.txt"])),
    ]


register(Task(
    task_id="T5a", family_id="head-tail", source_cluster_id="t5-cluster",
    prompt=(
        "Write a single Bash script that reads the file named by its first argument and "
        "prints exactly one line: its first line, a TAB character, then its last line "
        "(byte-for-byte, with a trailing newline). An empty file produces no output and "
        "exit 0. A file with a single line prints that line twice separated by a TAB. If "
        "the argument is missing or the file does not exist or cannot be read, print a "
        "diagnostic to stderr, write nothing to stdout, and exit with status 2. Leave the "
        "input byte-identical. " + PROMPT_TAIL
    ),
    invocation="solution.sh <input-file>",
    fixtures=_t5_cases(),
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-first-only.sh", "zero", "prints only the first line"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="all-lines"),
))

_T5B_MAIN = b"\nalpha\n\nbravo\n\n"
register(Task(
    task_id="T5b", family_id="head-tail", source_cluster_id="t5-cluster",
    prompt=(
        "Write a single Bash script that reads the file named by its first argument, "
        "ignores empty lines entirely, and prints exactly one line: the first non-empty "
        "line, a TAB character, then the last non-empty line (byte-for-byte, trailing "
        "newline). A file with no non-empty lines — including an empty file — produces no "
        "output and exit 0. A file with exactly one non-empty line prints it twice "
        "separated by a TAB. If the argument is missing or the file does not exist or "
        "cannot be read, print a diagnostic to stderr, write nothing to stdout, and exit "
        "with status 2. Leave the input byte-identical. " + PROMPT_TAIL
    ),
    invocation="solution.sh <input-file>",
    fixtures=[
        FixtureCase("t5b-main", 0.4, True,
                    lambda root, rng: _t2_file(root, rng, _T5B_MAIN),
                    lambda ctx: score_simple(ctx, b"alpha\tbravo\n")),
        FixtureCase("t5b-empty", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b""),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t5b-blank-only", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b"\n\n\n"),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t5b-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t5b-unreadable", 0.15, False,
                    lambda root, rng: (
                        put(root, "input.txt", b"secret\n", mode=0o000),
                        _err(["input.txt"]),
                    )[1]),
    ],
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-counts-blank.sh", "zero",
                    "treats blank lines as content: wrong first/last on main"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="skip-blank"),
))


# ---------------------------------------------------------------------------
# T6 — line numbering (family: line-numbering)
# ---------------------------------------------------------------------------


_T6_MAIN = b"alpha\n\nbravo line\n-dash line\n"


def _t6a_cases():
    return [
        FixtureCase("t6a-main", 0.4, True,
                    lambda root, rng: _t2_file(root, rng, _T6_MAIN),
                    lambda ctx: score_simple(ctx, b"1:alpha\n2:\n3:bravo line\n4:-dash line\n")),
        FixtureCase("t6a-empty", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b""),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t6a-single", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b"only\n"),
                    lambda ctx: score_simple(ctx, b"1:only\n")),
        FixtureCase("t6a-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t6a-missing", 0.15, False, lambda root, rng: _err(["input.txt"])),
    ]


register(Task(
    task_id="T6a", family_id="line-numbering", source_cluster_id="t6-cluster",
    prompt=(
        "Write a single Bash script that reads the file named by its first argument and "
        "prints every line prefixed with its 1-based line number, a colon, then the line "
        "byte-for-byte — no padding, so the format is exactly `N:line` (empty lines "
        "become `N:`). Print nothing else and exit 0; an empty file produces no output. "
        "If the argument is missing or the file does not exist or cannot be read, print a "
        "diagnostic to stderr, write nothing to stdout, and exit with status 2. Leave the "
        "input byte-identical. " + PROMPT_TAIL
    ),
    invocation="solution.sh <input-file>",
    fixtures=_t6a_cases(),
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-padded.sh", "zero", "cat -n style padding: format mismatch"),
        WrongScript("wrong-starts-at-zero.sh", "zero", "numbers from 0: every line wrong"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="number-all"),
))

register(Task(
    task_id="T6b", family_id="line-numbering", source_cluster_id="t6-cluster",
    prompt=(
        "Write a single Bash script that reads the file named by its first argument and "
        "prints its non-empty lines prefixed with their 1-based position among the "
        "NON-EMPTY lines, as `N:line` with no padding. Empty lines pass through unchanged "
        "with no prefix and do not consume a number. Print nothing else and exit 0; an "
        "empty file or a file of only empty lines produces no output. If the argument is "
        "missing or the file does not exist or cannot be read, print a diagnostic to "
        "stderr, write nothing to stdout, and exit with status 2. Leave the input "
        "byte-identical. " + PROMPT_TAIL
    ),
    invocation="solution.sh <input-file>",
    fixtures=[
        FixtureCase("t6b-main", 0.4, True,
                    lambda root, rng: _t2_file(root, rng, _T6_MAIN),
                    lambda ctx: score_simple(ctx, b"1:alpha\n\n2:bravo line\n3:-dash line\n")),
        FixtureCase("t6b-empty", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b""),
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("t6b-blank-only", 0.15, False,
                    lambda root, rng: _t2_file(root, rng, b"\n\n\n"),
                    lambda ctx: score_simple(ctx, b"\n\n\n")),
        FixtureCase("t6b-noargs", 0.15, False, lambda root, rng: _err([])),
        FixtureCase("t6b-missing", 0.15, False, lambda root, rng: _err(["input.txt"])),
    ],
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-numbers-all.sh", "zero",
                    "numbers every line: empty lines numbered (main mismatch)"),
    ],
    pool="held_out_test", provenance_extra=dict(HOLDOUT_PROVENANCE, variant="number-nonblank"),
))
