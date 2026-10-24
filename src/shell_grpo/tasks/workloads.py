"""W01–W02: manifest-verify family (Phase 5 top-up, authored-only).

Fifth train-pool family, authored after Phase 4 screening confirmed only 4 of
the required 5 families (reports/screening.md). Solution pattern — content
hashing against/into a sha256sum-style manifest — is distinct from every
existing train family. These tasks are TRAIN-POOL material (screened, then
trained on); they are not held-out test tasks.
"""

from __future__ import annotations

import hashlib
import random

from ..fixtures import GroundTruth, mkdir, put
from ..verifiers import (
    CheckResult,
    FixtureVerdict,
    VerifyContext,
    check_exit_equals,
    check_stdout_exact,
    score_simple,
    violation_if_changed,
)
from .base import FixtureCase, Task, WrongScript, register

_TOPUP_PROVENANCE = {
    "source": "authored",
    "pool": "development_pool",
    "campaign": "phase5-family-topup",
    "rationale": (
        "fifth train family (manifest-verify) authored 2026-10-24 after the "
        "Phase 4 gate confirmed 4/5 families; screened under both seeds"
    ),
}

_T2 = "  "  # sha256sum text-mode separator: two spaces


def _err(argv: list[str], exit_code: int = 2) -> GroundTruth:
    return GroundTruth(argv=argv, expects_failure=True, expected_exit=exit_code)


# ---------------------------------------------------------------------------
# W01 — verify a sha256 manifest (family: manifest-verify)
# ---------------------------------------------------------------------------

_W01_BETA = b"beta content\n"
_W01_GAMMA = b"gamma line\n"
_W01_GAMMA_MUT = b"gamma line CHANGED\n"
_W01_ALPHA = b"alpha\n"
_W01_GHOST_SHA = hashlib.sha256(b"never present\n").hexdigest()


def _w01_main_verify(ctx: VerifyContext) -> FixtureVerdict:
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 0))
    verdict.checks.append(check_stdout_exact(ctx, b"b.txt: ok\nsub/c.txt: ok\na.txt: ok\n"))
    if violation_if_changed(ctx, verdict, "", label="inputs"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


def _w01_mixed_verify(ctx: VerifyContext) -> FixtureVerdict:
    """One mismatch + one missing: exact status lines in manifest order, exit 1.

    Declared expects_failure=True (nonzero exit) so the engine does not
    pre-classify the run; the verifier still demands the exact stdout.
    """
    verdict = FixtureVerdict()
    verdict.checks.append(check_exit_equals(ctx, 1))
    verdict.checks.append(check_stdout_exact(
        ctx, b"b.txt: ok\nsub/c.txt: mismatch\nghost.txt: missing\n"))
    if violation_if_changed(ctx, verdict, "", label="inputs"):
        verdict.score = 0.0
        return verdict
    verdict.score = 1.0 if all(c.passed for c in verdict.checks) else 0.0
    return verdict


def _w01_main(root, rng: random.Random) -> GroundTruth:
    put(root / "dir", "b.txt", _W01_BETA)
    mkdir(root / "dir", "sub")
    put(root / "dir", "sub/c.txt", _W01_GAMMA)
    put(root / "dir", "a.txt", _W01_ALPHA)
    manifest = b"".join(
        hashlib.sha256(data).hexdigest().encode() + _T2.encode() + rel.encode() + b"\n"
        for rel, data in [("b.txt", _W01_BETA), ("sub/c.txt", _W01_GAMMA), ("a.txt", _W01_ALPHA)]
    )
    put(root, "manifest.txt", manifest)
    return GroundTruth(argv=["dir", "manifest.txt"])


def _w01_mixed(root, rng: random.Random) -> GroundTruth:
    put(root / "dir", "b.txt", _W01_BETA)
    mkdir(root / "dir", "sub")
    put(root / "dir", "sub/c.txt", _W01_GAMMA_MUT)  # bytes differ from manifest
    manifest = b"".join(
        hashlib.sha256(data).hexdigest().encode() + _T2.encode() + rel.encode() + b"\n"
        for rel, data in [
            ("b.txt", _W01_BETA),
            ("sub/c.txt", _W01_GAMMA),      # hash of the ORIGINAL bytes
            ("ghost.txt", b""),
        ]
    )
    put(root, "manifest.txt", manifest)
    return GroundTruth(argv=["dir", "manifest.txt"], expects_failure=True, expected_exit=1)


def _w01_empty(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "dir")
    put(root, "manifest.txt", b"")
    return GroundTruth(argv=["dir", "manifest.txt"], expected_stdout=b"")


register(Task(
    task_id="W01", family_id="manifest-verify", source_cluster_id="w-cluster",
    prompt=(
        "Write a single Bash script that takes two arguments: a directory and a "
        "checksum manifest file. The manifest contains one entry per line in "
        "sha256sum text format: a 64-hex-character SHA-256 digest, then two "
        "spaces, then a path relative to the directory. For every manifest "
        "entry, in manifest order, print exactly one line: `<path>: ok` when "
        "the file's actual SHA-256 matches, `<path>: mismatch` when the file "
        "exists but its digest differs, and `<path>: missing` when the file "
        "does not exist. Print nothing else. Exit 0 when every entry is ok, "
        "otherwise exit 1. Files in the directory that are not listed in the "
        "manifest are ignored. If the argument count is wrong, the first "
        "argument is not a directory, or the manifest is missing or "
        "unreadable, print a diagnostic to stderr, write nothing to stdout, "
        "and exit with status 2. Leave both inputs byte-identical. "
        "The environment provides a pinned GNU toolset (bash, coreutils, "
        "findutils, grep, sed, gawk) with LC_ALL=C and TZ=UTC, and has no "
        "network access. Respond with exactly one Bash script in a single "
        "```bash fenced code block."
    ),
    invocation="solution.sh <directory> <manifest-file>",
    fixtures=[
        FixtureCase("w01-main", 0.4, True, _w01_main, _w01_main_verify),
        FixtureCase("w01-mixed", 0.3, False, _w01_mixed, _w01_mixed_verify),
        FixtureCase("w01-empty-manifest", 0.1, True, _w01_empty,
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("w01-noargs", 0.1, False, lambda root, rng: _err([]),
                    lambda ctx: score_simple(ctx, None, expects_failure=True, expected_exit=2)),
        FixtureCase("w01-baddir", 0.1, False,
                    lambda root, rng: _err(["no-such-dir", "manifest.txt"]),
                    lambda ctx: score_simple(ctx, None, expects_failure=True, expected_exit=2)),
    ],
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints a diagnostic and exits 1: no progress"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-always-ok.sh", "partial",
                    "prints ok without hashing: passes main/errors, fails mixed"),
        WrongScript("wrong-sorted-output.sh", "partial",
                    "sorts status lines instead of manifest order: fails both content fixtures"),
    ],
    provenance_extra=dict(_TOPUP_PROVENANCE, variant="verify"),
))

# ---------------------------------------------------------------------------
# W02 — generate a sha256 manifest (family: manifest-verify)
# ---------------------------------------------------------------------------


def _w02_main(root, rng: random.Random) -> GroundTruth:
    files = [("a.txt", b"alpha\n"), ("b d.txt", b"space name\n"), ("sub/c.txt", b"gamma line\n")]
    mkdir(root, "dir")
    for rel, data in files:
        put(root / "dir", rel, data)
    expected = b"".join(
        hashlib.sha256(data).hexdigest().encode() + _T2.encode() + rel.encode() + b"\n"
        for rel, data in sorted(files, key=lambda kv: kv[0].encode())
    )
    return GroundTruth(argv=["dir"], expected_stdout=expected)


def _w02_empty(root, rng: random.Random) -> GroundTruth:
    mkdir(root, "dir")
    return GroundTruth(argv=["dir"], expected_stdout=b"")


register(Task(
    task_id="W02", family_id="manifest-verify", source_cluster_id="w-cluster",
    prompt=(
        "Write a single Bash script that takes one argument: a directory. It "
        "prints a sha256sum-compatible checksum manifest for every regular "
        "file anywhere under that directory, one file per line: the file's "
        "64-hex-character SHA-256 digest, then exactly two spaces, then the "
        "file's path relative to the argument directory. Lines must be sorted "
        "by relative path in ascending byte order (C locale). Print nothing "
        "else and exit 0; an empty directory produces no output. If the "
        "argument is missing or is not a directory, print a diagnostic to "
        "stderr, write nothing to stdout, and exit with status 2. Never modify "
        "the directory or its files; symbolic links, if any, are never "
        "followed. The environment provides a pinned GNU toolset (bash, "
        "coreutils, findutils, grep, sed, gawk) with LC_ALL=C and TZ=UTC, and "
        "has no network access. Respond with exactly one Bash script in a "
        "single ```bash fenced code block."
    ),
    invocation="solution.sh <directory>",
    fixtures=[
        FixtureCase("w02-main", 0.5, True, _w02_main,
                    lambda ctx: score_simple(ctx, _w02_main_expected())),
        FixtureCase("w02-empty", 0.15, True, _w02_empty,
                    lambda ctx: score_simple(ctx, b"")),
        FixtureCase("w02-noargs", 0.15, False, lambda root, rng: _err([]),
                    lambda ctx: score_simple(ctx, None, expects_failure=True, expected_exit=2)),
        FixtureCase("w02-notdir", 0.2, False,
                    lambda root, rng: (
                        put(root, "plainfile", b"regular file\n"),
                        _err(["plainfile"]),
                    )[1],
                    lambda ctx: score_simple(ctx, None, expects_failure=True, expected_exit=2)),
    ],
    reference="reference.sh", alternate="alternate.sh",
    wrongs=[
        WrongScript("wrong-noop.sh", "zero", "prints a diagnostic and exits 1: no progress"),
        WrongScript("wrong-empty.sh", "zero", "empty file (invalid_script)"),
        WrongScript("wrong-one-space.sh", "partial",
                    "single-space separator: main fails on the byte-exact format"),
        WrongScript("wrong-unsorted.sh", "partial",
                    "enumeration order, not byte-sorted paths: main fails"),
    ],
    provenance_extra=dict(_TOPUP_PROVENANCE, variant="generate"),
))


def _w02_main_expected() -> bytes:
    files = [("a.txt", b"alpha\n"), ("b d.txt", b"space name\n"), ("sub/c.txt", b"gamma line\n")]
    return b"".join(
        hashlib.sha256(data).hexdigest().encode() + _T2.encode() + rel.encode() + b"\n"
        for rel, data in sorted(files, key=lambda kv: kv[0].encode())
    )
