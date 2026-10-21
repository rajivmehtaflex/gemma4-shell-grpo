"""Fixture instances: seeded construction, tree snapshots and hashing.

A fixture instance is a fresh directory tree built from a declared seed. The
grader snapshots the tree before and after candidate execution; verifiers
compare the two snapshots and the captured output against ground truth that
the builder recorded independently of any candidate.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class Entry:
    kind: str  # file | dir | symlink | other
    mode: int
    sha256: str | None
    target: str | None
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "mode": self.mode,
            "sha256": self.sha256,
            "target": self.target,
            "size": self.size,
        }


Snapshot = dict[str, Entry]


def hash_file_resilient(path: Path, mode: int) -> str:
    """Hash a regular file even when its mode denies the owner read access."""
    restore = None
    if not os.access(path, os.R_OK):
        restore = mode
        os.chmod(path, mode | 0o400)
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    finally:
        if restore is not None:
            os.chmod(path, restore)


def snapshot_tree(root: Path) -> Snapshot:
    """Record every entry under root (not root itself), never following symlinks."""
    entries: Snapshot = {}

    def visit(dirpath: Path, rel: str) -> None:
        st = dirpath.lstat()
        mode = stat.S_IMODE(st.st_mode)
        restore = None
        if not os.access(dirpath, os.R_OK | os.X_OK):
            restore = mode
            os.chmod(dirpath, mode | 0o700)
        try:
            names = sorted(os.listdir(dirpath))
            for name in names:
                path = dirpath / name
                relpath = f"{rel}/{name}" if rel else name
                lst = path.lstat()
                m = stat.S_IMODE(lst.st_mode)
                if stat.S_ISLNK(lst.st_mode):
                    entries[relpath] = Entry("symlink", m, None, os.readlink(path), 0)
                elif stat.S_ISDIR(lst.st_mode):
                    entries[relpath] = Entry("dir", m, None, None, 0)
                    visit(path, relpath)
                elif stat.S_ISREG(lst.st_mode):
                    entries[relpath] = Entry(
                        "file", m, hash_file_resilient(path, m), None, lst.st_size
                    )
                else:
                    entries[relpath] = Entry("other", m, None, None, 0)
        finally:
            if restore is not None:
                os.chmod(dirpath, restore)

    visit(root, "")
    return entries


def snapshot_digest(snapshot: Snapshot) -> str:
    canonical = json.dumps(
        {k: v.to_dict() for k, v in sorted(snapshot.items())},
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def make_readable(root: Path) -> None:
    """Restore owner rwx on everything so the instance can be inspected/removed."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dp = Path(dirpath)
        try:
            os.chmod(dp, stat.S_IMODE(dp.lstat().st_mode) | 0o700)
        except OSError:
            pass
        for name in filenames + dirnames:
            p = dp / name
            try:
                lst = p.lstat()
                if not stat.S_ISLNK(lst.st_mode):
                    os.chmod(p, stat.S_IMODE(lst.st_mode) | 0o600)
            except OSError:
                pass


def remove_tree(root: Path) -> None:
    if root.exists():
        make_readable(root)
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Builder helpers used by task modules
# ---------------------------------------------------------------------------


def put(root: Path, relpath: str, data: bytes, mode: int = 0o644) -> Path:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    os.chmod(path, mode)
    return path


def mkdir(root: Path, relpath: str, mode: int = 0o755) -> Path:
    path = root / relpath
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    return path


def symlink(root: Path, relpath: str, target: str) -> Path:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, path)
    return path


def seeded_bytes(rng: random.Random, size: int) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(size))


def seeded_text(rng: random.Random, lines: int, width: int = 24) -> bytes:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789 "
    out = []
    for _ in range(lines):
        out.append("".join(rng.choice(alphabet) for _ in range(width)))
    return ("\n".join(out) + "\n").encode()


# ---------------------------------------------------------------------------
# Ground truth and fixture instance records
# ---------------------------------------------------------------------------


@dataclass
class GroundTruth:
    """Everything the verifier needs, recorded by the builder before execution.

    expected_exit semantics: an int means the exact exit code (S-task failure
    fixtures declare 2); None with expects_failure=True means any nonzero exit
    satisfies the exit check (D-task failure fixtures declare "fail").
    """

    argv: list[str]
    expects_failure: bool = False
    expected_exit: int | None = 0
    expected_stdout: bytes | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class FixtureInstance:
    fixture_id: str
    seed: int
    root: Path
    truth: GroundTruth
    pre: Snapshot
    fixture_sha256: str


Builder = Callable[[Path, random.Random], GroundTruth]


def build_instance(fixture_id: str, seed: int, root: Path, builder: Builder) -> FixtureInstance:
    remove_tree(root)
    root.mkdir(parents=True)
    rng = random.Random(seed)
    truth = builder(root, rng)
    pre = snapshot_tree(root)
    payload = json.dumps(
        {
            "fixture_id": fixture_id,
            "seed": seed,
            "argv": truth.argv,
            "tree": snapshot_digest(pre),
        },
        sort_keys=True,
    )
    return FixtureInstance(
        fixture_id=fixture_id,
        seed=seed,
        root=root,
        truth=truth,
        pre=pre,
        fixture_sha256=hashlib.sha256(payload.encode()).hexdigest(),
    )
