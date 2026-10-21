"""Fixture framework tests: snapshots, determinism, resilient hashing."""

import stat

from shell_grpo.fixtures import (
    build_instance,
    hash_file_resilient,
    mkdir,
    put,
    remove_tree,
    snapshot_digest,
    snapshot_tree,
    symlink,
)


def _demo_instance(tmp_path, seed):
    def build(root, rng):
        from shell_grpo.fixtures import GroundTruth

        put(root / "root", "a.txt", b"hello")
        put(root / "root", "locked", b"secret", mode=0o000)
        mkdir(root / "root", "sub")
        put(root / "root", "sub/deep.txt", b"nested")
        symlink(root / "root", "link", "a.txt")
        return GroundTruth(argv=["root"], expected_stdout=b"1\n")

    return build_instance("fx", seed, tmp_path / "inst", build)


def test_snapshot_records_all_entry_kinds(tmp_path):
    inst = _demo_instance(tmp_path, 1)
    kinds = {name: entry.kind for name, entry in inst.pre.items()}
    assert kinds["root/a.txt"] == "file"
    assert kinds["root/locked"] == "file"
    assert kinds["root/sub"] == "dir"
    assert kinds["root/link"] == "symlink"
    assert inst.pre["root/link"].target == "a.txt"
    remove_tree(inst.root)


def test_snapshot_hashes_unreadable_files(tmp_path):
    inst = _demo_instance(tmp_path, 1)
    locked = inst.pre["root/locked"]
    assert locked.mode == 0o000
    assert locked.sha256 is not None
    assert len(locked.sha256) == 64
    remove_tree(inst.root)


def test_same_seed_builds_identical_tree_hash(tmp_path):
    a = _demo_instance(tmp_path / "a", 123)
    b = _demo_instance(tmp_path / "b", 123)
    assert snapshot_digest(a.pre) == snapshot_digest(b.pre)
    assert a.fixture_sha256 == b.fixture_sha256
    remove_tree(a.root)
    remove_tree(b.root)


def test_different_sees_build_different_hashes(tmp_path):
    a = _demo_instance(tmp_path / "a", 1)
    b = _demo_instance(tmp_path / "b", 2)
    assert a.fixture_sha256 != b.fixture_sha256
    remove_tree(a.root)
    remove_tree(b.root)


def test_snapshot_detects_post_changes(tmp_path):
    inst = _demo_instance(tmp_path, 5)
    before = snapshot_digest(inst.pre)
    put(inst.root / "root", "a.txt", b"tampered")
    put(inst.root, "extra.txt", b"new")
    (inst.root / "root/sub/deep.txt").unlink()
    after = snapshot_tree(inst.root)
    assert snapshot_digest(after) != before
    diffs = set(after) ^ set(inst.pre)
    assert "extra.txt" in diffs
    remove_tree(inst.root)


def test_hash_file_resilient_restores_mode(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"data")
    p.chmod(0o000)
    digest = hash_file_resilient(p, stat.S_IMODE(p.lstat().st_mode))
    assert len(digest) == 64
    assert stat.S_IMODE(p.lstat().st_mode) == 0o000
    p.chmod(0o644)
