"""S01–S04: file-operation diagnostics from the Pi practice-session campaign.

Prompts are the frozen briefs (pi-sessions/tasks/S0x.md) submitted verbatim to
Pi; fixtures follow pi-sessions/fixtures/S0x.md exactly. These tasks are
authored; the campaign candidates are Pi-derived practice runs.
"""

from __future__ import annotations

import hashlib
import random

from ..fixtures import GroundTruth, mkdir, put, seeded_bytes, symlink
from ..verifiers import (
    CheckResult,
    FixtureVerdict,
    VerifyContext,
    violation_if_changed,
)
from .base import FixtureCase, Task, WrongScript, register

PROVENANCE = {
    "campaign": "ten-authored-pi-practice-sessions",
    "campaign_role": (
        "development pool; excluded from the final unseen test set; never an SFT target"
    ),
}


def _expected_nul(relpaths: list[str]) -> bytes:
    return b"".join(p.encode() + b"\x00" for p in sorted(relpaths, key=lambda s: s.encode()))


# ---------------------------------------------------------------------------
# S01 — count direct .txt files (with exit-2 discipline)
# ---------------------------------------------------------------------------


def _s01_main(root, rng: random.Random) -> GroundTruth:
    names = ["a.txt", "my report.txt", "-leading-dash.txt", "tab\tname.txt", "line1\nline2.txt"]
    for name in names:
        put(root / "root", name, seeded_bytes(rng, 3))
    put(root / "root", "notes.md", b"not txt\n")
    put(root / "root", "report.TXT", b"case must not match\n")
    put(root / "root", "plain-file", b"no extension\n")
    mkdir(root / "root", "nested")
    put(root / "root", "nested/deep.txt", b"nested not counted\n")
    symlink(root / "root", "link-to-a.txt", "a.txt")
    return GroundTruth(argv=["root"], expected_stdout=b"5\n")


def _s01_empty(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "root")
    return GroundTruth(argv=["root"], expected_stdout=b"0\n")


def _s01_edge(root, rng: random.Random) -> GroundTruth:
    mkdir(root / "root", "nested")
    put(root / "root", "nested/x.txt", b"nested\n")
    symlink(root / "root", "symlink.txt", "missing-target")
    put(root / "root", "b.txt.bak", b"backup\n")
    return GroundTruth(argv=["root"], expected_stdout=b"0\n")


def _s01_noarg(root, rng: random.Random) -> GroundTruth:
    return GroundTruth(argv=[], expects_failure=True, expected_exit=2)


def _s01_notdir(root, rng: random.Random) -> GroundTruth:
    put(root, "plainfile", b"a regular file, not a directory\n")
    return GroundTruth(argv=["plainfile"], expects_failure=True, expected_exit=2)


def _s01_unreadable(root, rng: random.Random) -> GroundTruth:
    import os

    mkdir(root, "root")
    put(root / "root", "hidden.txt", b"unreadable from outside\n")
    os.chmod(root / "root", 0o000)
    return GroundTruth(argv=["root"], expects_failure=True, expected_exit=2)


register(
    Task(
        task_id="S01",
        family_id="file-select-count",
        source_cluster_id="s01-cluster",
        prompt=(
            "Write a Bash script that counts regular files whose names end in `.txt` "
            "(lowercase, case-sensitive) located directly inside the directory given as its "
            "first argument. Never descend into subdirectories and never count symlinks, even "
            "symlinks pointing at `.txt` files. Print exactly the decimal count followed by a "
            "single newline. Filenames may contain spaces, leading dashes, tabs, or newline "
            "characters. If the argument is missing, is not a directory, or cannot be read, "
            "print a diagnostic to stderr, write nothing to stdout, exit with status 2, and "
            "change nothing on disk."
        ),
        invocation="solution.sh <directory>",
        fixtures=[
            FixtureCase("s01-main", 0.3, True, _s01_main),
            FixtureCase("s01-empty", 0.1, False, _s01_empty),
            FixtureCase("s01-edge", 0.1, False, _s01_edge),
            FixtureCase("s01-noarg", 0.15, False, _s01_noarg),
            FixtureCase("s01-notdir", 0.15, False, _s01_notdir),
            FixtureCase("s01-unreadable", 0.2, False, _s01_unreadable),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing: no progress on main"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-hardcode.sh", "partial",
                "echo 5 — passes main (progress) but fails empty/edge and every exit-2 fixture",
            ),
            WrongScript(
                "wrong-follows-links.sh", "zero",
                "counts symlinks (find default or glob on link name)",
            ),
        ],
        notes="Frozen campaign brief S01; shares template lineage with D01.",
        provenance_extra={
            **PROVENANCE,
            "brief": "pi-sessions/tasks/S01.md",
            "fixture_spec": "pi-sessions/fixtures/S01.md",
        },
    )
)


# ---------------------------------------------------------------------------
# S02 — copy .log files recursively (with full validation discipline)
# ---------------------------------------------------------------------------


def _s02_main(root, rng: random.Random) -> GroundTruth:
    required: dict[str, str] = {}

    def log(relpath: str, data: bytes) -> None:
        put(root / "src", relpath, data)
        required[relpath] = hashlib.sha256(data).hexdigest()

    log("app.log", b"a" * 120)
    log("logs/2026-10-01/server.log", b"s" * 88)
    log("logs/2026-10-02/db.log", b"d" * 64)
    log("logs/2026-10-02/dup.log", b"u" * 40)
    put(root / "src", "other/dir/broken.log.txt", b"not a log\n")
    put(root / "src", "notes.LOG", b"case must not match\n")
    put(root / "src", "read.me", b"unrelated\n")
    symlink(root / "src", "skip-link.log", "app.log")
    symlink(root / "src", "sub/link-dir", "logs")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": required})


def _copy_verify(ctx: VerifyContext) -> FixtureVerdict:
    from ..verifiers import score_copied_fraction

    return score_copied_fraction(
        ctx, ctx.truth.extra.get("dest", "dst"), ctx.truth.extra.get("required", {}),
        source_scope="src",
    )


def _s02_empty_src(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "notes.txt", b"no logs\n")
    mkdir(root, "dst")
    return GroundTruth(argv=["src", "dst"], extra={"dest": "dst", "required": {}})


def _err(argv: list[str]) -> GroundTruth:
    return GroundTruth(argv=argv, expects_failure=True, expected_exit=2)


def _s02_dst_missing(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "src")
    put(root / "src", "app.log", b"log\n")
    return _err(["src", "dst"])


def _s02_dst_notdir(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "app.log", b"log\n")
    put(root, "dst", b"regular file\n")
    return _err(["src", "dst"])


def _s02_dst_notempty(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "app.log", b"log\n")
    mkdir(root, "dst")
    put(root / "dst", "existing.txt", b"dst must stay unchanged\n")
    return _err(["src", "dst"])


def _s02_dst_inside(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "app.log", b"log\n")
    return _err(["src", "src/dest"])


def _s02_dst_equals(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "app.log", b"log\n")
    return _err(["src", "src"])


def _s02_src_missing(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "dst")
    return _err(["src", "dst"])


def _s02_noargs(root, rng: random.Random) -> GroundTruth:
    return _err([])


_S02_ERRORS = [
    ("s02-dst-missing", _s02_dst_missing),
    ("s02-dst-notdir", _s02_dst_notdir),
    ("s02-dst-notempty", _s02_dst_notempty),
    ("s02-dst-inside", _s02_dst_inside),
    ("s02-dst-equals", _s02_dst_equals),
    ("s02-src-missing", _s02_src_missing),
    ("s02-noargs", _s02_noargs),
]

register(
    Task(
        task_id="S02",
        family_id="copy-recursive",
        source_cluster_id="s02-cluster",
        prompt=(
            "Write a Bash script that copies every regular file whose name ends in `.log` "
            "(case-sensitive) from the directory tree under its first argument into its second "
            "argument, preserving each file's path relative to the source directory and "
            "preserving file bytes exactly. Skip symlinks: never copy a symlink entry and never "
            "follow directory symlinks while recursing. The destination must already exist as "
            "an empty directory; if it is missing, is not a directory, is not empty, or is "
            "located inside the source directory (or equals it), print a diagnostic to stderr, "
            "write nothing anywhere, and exit with status 2 — all validation before the first "
            "write. The source directory must remain byte-identical afterwards. Filenames may "
            "contain spaces and leading dashes."
        ),
        invocation="solution.sh <source-dir> <dest-dir>",
        fixtures=[
            FixtureCase("s02-main", 0.25, True, _s02_main, _copy_verify),
            FixtureCase("s02-empty-src", 0.05, False, _s02_empty_src, _copy_verify),
            *(
                FixtureCase(fid, 0.1, False, builder)
                for fid, builder in _S02_ERRORS
            ),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "copies nothing: no progress on main"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-follows-symlinks.sh", "zero",
                "cp -rL recursion copies the dir symlink (extra entries: critical)",
            ),
            WrongScript(
                "wrong-no-validation.sh", "zero",
                "copies happily into missing/nonempty destinations (mutation: critical)",
            ),
        ],
        notes="Frozen campaign brief S02; shares template lineage with D02.",
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S02.md",
                          "fixture_spec": "pi-sessions/fixtures/S02.md"},
    )
)


# ---------------------------------------------------------------------------
# S03 — move direct .bak files
# ---------------------------------------------------------------------------


def _s03_main(root, rng: random.Random) -> GroundTruth:
    moved: dict[str, str] = {}
    for name in ["old.bak", "my data.bak", "-dash.bak"]:
        data = f"payload of {name}\n".encode() + seeded_bytes(rng, 20)
        put(root / "src", name, data)
        moved[name] = hashlib.sha256(data).hexdigest()
    mkdir(root / "src", "deep")
    put(root / "src", "deep/nested.bak", b"nested must not move\n")
    symlink(root / "src", "link.bak", "old.bak")
    put(root / "src", "keep.txt", b"unselected\n")
    mkdir(root, "archive")
    return GroundTruth(
        argv=["src", "archive"],
        extra={"src": "src", "archive": "archive", "moved": moved},
    )


def _s03_move_verify(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    truth = ctx.truth.extra
    src, archive, moved = truth["src"], truth["archive"], truth["moved"]
    moved_entries = {f"{src}/{name}" for name in moved}

    src_changes = []
    pre_names = {n for n in ctx.pre if n.startswith(src + "/")}
    post_names = {n for n in ctx.post if n.startswith(src + "/")}
    unexpected_gone = (pre_names - post_names) - moved_entries
    if unexpected_gone:
        src_changes.append(f"lost: {sorted(unexpected_gone)[:4]}")
    created = post_names - pre_names
    if created:
        src_changes.append(f"appeared: {sorted(created)[:4]}")
    for name in sorted((pre_names & post_names) - moved_entries):
        if ctx.pre[name].to_dict() != ctx.post[name].to_dict():
            src_changes.append(f"changed: {name}")
    if src_changes:
        verdict.critical_violations.append(
            "source_damaged: " + "; ".join(src_changes[:6])
        )
    archive_names = {n for n in ctx.post if n.startswith(archive + "/")}
    expected_names = {f"{archive}/{name}" for name in moved}
    extras = sorted(archive_names - expected_names)
    if extras:
        verdict.critical_violations.append(f"extra_archive_entries: {extras[:6]}")
    placed = 0
    for name, sha in moved.items():
        entry = ctx.post.get(f"{archive}/{name}")
        gone_from_src = f"{src}/{name}" not in ctx.post
        if entry is not None and entry.kind == "file" and entry.sha256 == sha and gone_from_src:
            placed += 1
    verdict.checks.append(
        CheckResult(
            "moved_files_placed",
            placed == len(moved),
            True,
            f"{placed}/{len(moved)} moved (absent from source, bytes in archive)",
        )
    )
    verdict.checks.append(
        CheckResult(
            "unselected_untouched",
            not src_changes,
            True,
            "source intact apart from the moves" if not src_changes else "source damaged",
        )
    )
    if verdict.critical_violations:
        verdict.score = 0.0
        return verdict
    verdict.score = placed / len(moved) if moved else 1.0
    return verdict


def _s03_none(root, rng: random.Random) -> GroundTruth:
    put(root / "src", "keep.txt", b"no bak files\n")
    mkdir(root / "src", "deep")
    put(root / "src", "deep/notes.txt", b"unselected\n")
    mkdir(root, "archive")
    return GroundTruth(
        argv=["src", "archive"],
        extra={"src": "src", "archive": "archive", "moved": {}},
    )


def _s03_archive_missing(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "src")
    put(root / "src", "old.bak", b"x\n")
    return _err(["src", "archive"])


def _s03_archive_notempty(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "src")
    put(root / "src", "old.bak", b"x\n")
    mkdir(root, "archive")
    put(root / "archive", "existing.txt", b"archive must stay unchanged\n")
    return _err(["src", "archive"])


def _s03_archive_equals(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "src")
    put(root / "src", "old.bak", b"x\n")
    return _err(["src", "src"])


def _s03_archive_inside_src(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "src")
    put(root / "src", "old.bak", b"x\n")
    return _err(["src", "src/archive-sub"])


def _s03_src_inside_archive(root, rng: random.Random) -> GroundTruth:
    mkdir(root / "outer/src")
    put(root / "outer/src", "old.bak", b"x\n")
    return _err(["outer/src", "outer"])


def _s03_src_missing(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "archive")
    return _err(["src", "archive"])


def _s03_noargs(root, rng: random.Random) -> GroundTruth:
    return _err([])


_S03_ERRORS = [
    ("s03-archive-missing", _s03_archive_missing),
    ("s03-archive-notempty", _s03_archive_notempty),
    ("s03-archive-equals", _s03_archive_equals),
    ("s03-archive-inside-src", _s03_archive_inside_src),
    ("s03-src-inside-archive", _s03_src_inside_archive),
    ("s03-src-missing", _s03_src_missing),
    ("s03-noargs", _s03_noargs),
]

register(
    Task(
        task_id="S03",
        family_id="move-select",
        source_cluster_id="s03-cluster",
        prompt=(
            "Write a Bash script that moves every regular file whose name ends in `.bak` "
            "(case-sensitive) and that sits directly inside its first argument — never inside "
            "subdirectories, never symlinks — into the directory given as its second argument, "
            "keeping the original basenames. The archive directory must already exist, be "
            "empty, and lie completely outside the source directory: if it equals the source, "
            "is inside it, or contains the source as a subdirectory, refuse before touching "
            "anything. The same refusal applies when arguments are missing, the directories do "
            "not exist, or the archive is not empty: print a diagnostic to stderr and exit "
            "with status 2 without moving or modifying any file. Files that are not moved — "
            "including files in subdirectories and non-`.bak` files — must remain "
            "byte-identical and in place."
        ),
        invocation="solution.sh <source-dir> <archive-dir>",
        fixtures=[
            FixtureCase("s03-main", 0.35, True, _s03_main, _s03_move_verify),
            FixtureCase("s03-none", 0.15, False, _s03_none, _s03_move_verify),
            *(
                FixtureCase(fid, 1 / 14, False, builder)
                for fid, builder in _S03_ERRORS
            ),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "moves nothing: no progress on main"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-recursive.sh", "zero",
                "moves nested .bak files too (unexpected source loss: critical)",
            ),
            WrongScript(
                "wrong-copies.sh", "zero",
                "copies instead of moving: files remain in source, placed-count drops to 0",
            ),
        ],
        notes="Frozen campaign brief S03; new authored template.",
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S03.md",
                          "fixture_spec": "pi-sessions/fixtures/S03.md"},
    )
)


# ---------------------------------------------------------------------------
# S04 — CSV file inventory (NUL-delimited, byte-sorted)
# ---------------------------------------------------------------------------


def _s04_main(root, rng: random.Random) -> GroundTruth:
    relpaths = [
        "data.csv",
        "my table.csv",
        "-dash.csv",
        "multi\nline.csv",
        "a/b/c/deep.csv",
        "a/zz.csv",
        "a.csv/a.csv",
    ]
    for rel in relpaths:
        put(root / "root", rel, b"csv-bytes," + rel.encode() + b"\n")
    put(root / "root", "export.CSV", b"case excluded\n")
    put(root / "root", "read.me", b"excluded\n")
    symlink(root / "root", "link.csv", "data.csv")
    symlink(root / "root", "link-dir", "a")
    return GroundTruth(argv=["root"], expected_stdout=_expected_nul(relpaths))


def _s04_empty(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "root")
    return GroundTruth(argv=["root"], expected_stdout=b"")


def _s04_noarg(root, rng: random.Random) -> GroundTruth:
    return _err([])


def _s04_notdir(root, rng: random.Random) -> GroundTruth:
    put(root, "plainfile", b"regular file\n")
    return _err(["plainfile"])


def _s04_unreadable(root, rng: random.Random) -> GroundTruth:
    import os
    import stat as st

    mkdir(root, "root")
    os.chmod(root / "root", 0o000)
    return _err(["root"])


register(
    Task(
        task_id="S04",
        family_id="file-list-nul",
        source_cluster_id="s04-cluster",
        prompt=(
            "Write a Bash script that lists every regular file whose name ends in `.csv` "
            "(case-sensitive) anywhere under its first argument, one path per entry, printed "
            "relative to that argument without a leading `./`. Separate entries with NUL bytes "
            "— not newlines — because relative paths may contain spaces, tabs, leading dashes, "
            "and newline characters. Sort the entries by their relative-path bytes in C locale "
            "order (plain byte sort). Skip symlinks: neither list nor follow them. Do not "
            "modify anything. If the argument is missing, is not a directory, or cannot be "
            "read, print a diagnostic to stderr, write nothing to stdout, and exit with "
            "status 2. An empty tree is a success with empty output."
        ),
        invocation="solution.sh <directory>",
        fixtures=[
            FixtureCase("s04-main", 0.4, True, _s04_main),
            FixtureCase("s04-empty", 0.1, False, _s04_empty),
            FixtureCase("s04-noarg", 0.15, False, _s04_noarg),
            FixtureCase("s04-notdir", 0.15, False, _s04_notdir),
            FixtureCase("s04-unreadable", 0.2, False, _s04_unreadable),
        ],
        reference="reference.sh",
        alternate="alternate.sh",
        wrongs=[
            WrongScript("wrong-noop.sh", "zero", "prints nothing"),
            WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
            WrongScript(
                "wrong-newline-delimited.sh", "zero",
                "uses newlines instead of NUL separators (byte-exact mismatch)",
            ),
            WrongScript(
                "wrong-unsorted.sh", "zero",
                "walk order instead of byte sort: exact-output mismatch",
            ),
        ],
        notes="Frozen campaign brief S04; new authored template.",
        provenance_extra={**PROVENANCE, "brief": "pi-sessions/tasks/S04.md",
                          "fixture_spec": "pi-sessions/fixtures/S04.md"},
    )
)
