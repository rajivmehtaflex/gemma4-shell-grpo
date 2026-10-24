#!/usr/bin/env python3
"""Phase 5 dataset packaging: build manifests/dataset-v1.json for release
bank-v2 and verify the external payload on the private HF repo.

The manifest is the single reconstruction contract: bank hash, task/split
membership, per-task weights, fixture seed schedule, verifier bundle hashes,
grader image digest, model/template identity, and the HF payload URIs with
SHA-256s. `--verify` re-checks every hash (local files + remote HF objects)
without writing anything. Stdlib only (no huggingface_hub dependency).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HF_REPO = "rajivmehtapy/gemma4-shell-grpo-artifacts"
HF_PREFIX = "p5/dataset-v1"
BANK_DIR = REPO / "data" / "dataset" / "bank-v2"
PAYLOADS = [  # repo-relative paths shipped to the private HF repo
    "data/dataset/bank-v2/bank.jsonl",
    "data/dataset/bank-v2/manifest.json",
]
EXAMPLES_GLOB = "data/examples/scripts/*"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hf_token() -> str:
    return Path.home().joinpath(".cache/huggingface/token").read_text().strip()


def hf_url(rel: str) -> str:
    return f"https://huggingface.co/{HF_REPO}/resolve/main/{HF_PREFIX}/{rel}"


def hf_upload(rel: str, local: Path) -> None:
    try:
        from huggingface_hub import HfApi

        HfApi().upload_file(
            path_or_fileobj=str(local), path_in_repo=f"{HF_PREFIX}/{rel}",
            repo_id=HF_REPO, repo_type="model",
        )
    except ImportError:
        import subprocess

        subprocess.run(
            ["hf", "upload", HF_REPO, str(local), f"{HF_PREFIX}/{rel}", "--repo-type=model"],
            check=True,
        )


def hf_sha(rel: str) -> str:
    """Digest of the remote object (lfs oid for LFS pointers, else the bytes)."""
    token = hf_token()
    req = urllib.request.Request(
        f"https://huggingface.co/api/models/{HF_REPO}/tree/main/{HF_PREFIX}/{rel}",
        headers={"Authorization": f"Bearer {token}"},
    )
    info = json.load(urllib.request.urlopen(req))
    if isinstance(info, list):
        info = info[0]
    if info.get("lfs"):
        return info["lfs"]["oid"]
    req = urllib.request.Request(hf_url(rel), headers={"Authorization": f"Bearer {token}"})
    return hashlib.sha256(urllib.request.urlopen(req).read()).hexdigest()


def make_examples_tar(out: Path) -> None:
    with tarfile.open(out, "w:gz") as tar:
        for path in sorted(REPO.glob(EXAMPLES_GLOB)):
            tar.add(path, arcname=str(path.relative_to(REPO)))


def build() -> int:
    import yaml

    pilot = yaml.safe_load((REPO / "configs" / "grpo-pilot.yaml").read_text())
    bank_manifest = json.loads((BANK_DIR / "manifest.json").read_text())
    bank_records = [json.loads(l) for l in (BANK_DIR / "bank.jsonl").read_text().splitlines()]

    # payloads: bank files + the candidate-script examples tarball
    tmp = Path(tempfile.mkdtemp())
    examples_tgz = tmp / "examples-scripts.tar.gz"
    make_examples_tar(examples_tgz)

    for rel in PAYLOADS:
        hf_upload(f"{Path(rel).parent.name}/{Path(rel).name}", REPO / rel)
    hf_upload("examples-scripts.tar.gz", examples_tgz)

    pool = pilot["dataset"]["accepted_training_pool"]
    manifest = {
        "schema_version": "1.0.0",
        "manifest_id": "dataset-v1",
        "release": bank_manifest["release"],
        "release_seed": bank_manifest["seed"],
        "bank_sha256": bank_manifest["bank_sha256"],
        "task_count": bank_manifest["task_count"],
        "split_task_counts": bank_manifest["split_task_counts"],
        "component_count": bank_manifest["component_count"],
        "reward_version": bank_manifest["reward_version"],
        "tasks": [
            {
                "task_id": r["task_id"],
                "split": r["split"],
                "component": r["component"],
                "family": r["family_id"],
                "pool": r.get("pool", "development_pool"),
                "train_weight": 1.0 if r["task_id"] in pool else 0.0,
                "prompt_sha256": hashlib.sha256(r["prompt"].encode()).hexdigest(),
            }
            for r in bank_records
        ],
        "accepted_training_pool": pool,
        "excluded_reserve": pilot["dataset"]["excluded_reserve"],
        "fixture_seed_schedule": pilot["dataset"]["fixture_seed_schedule"],
        "verifier_bundle": {
            rel: sha256_file(REPO / rel)
            for rel in [
                "src/shell_grpo/contracts.py",
                "src/shell_grpo/verifiers.py",
                "src/shell_grpo/fixtures.py",
                "src/shell_grpo/rewards.py",
                "src/shell_grpo/runner.py",
                "src/shell_grpo/ns_exec.py",
                "configs/runner.yaml",
                "containers/grader/Dockerfile",
            ]
        },
        "config_bundle": {
            rel: sha256_file(REPO / rel)
            for rel in [
                "configs/grpo-pilot.yaml",
                "configs/grpo-main.yaml",
                "configs/model.yaml",
                "configs/dataset.yaml",
            ]
        },
        "model_identity": {
            "repo_id": "unsloth/gemma-4-E4B-it",
            "revision": "4e22d7e59e078e63a14f351efdc5232ed366b621",
            "template": "gemma-4-thinking (frozen in src/shell_grpo/generate.py)",
        },
        "payloads": {
            f"{Path(rel).parent.name}/{Path(rel).name}": {"sha256": sha256_file(REPO / rel)}
            for rel in PAYLOADS
        } | {
            "examples-scripts.tar.gz": {"sha256": sha256_file(examples_tgz)},
        },
        "payload_uri_prefix": f"hf://{HF_REPO}/{HF_PREFIX}",
        "notes": [
            "grader-only fields (fixtures, verifiers, wrong-script expectations) never enter policy prompts; prompts are the `prompt` field of bank.jsonl records",
            "bank-v1 remains frozen at data/dataset/bank-v1/ (Phase 3 release)",
        ],
    }
    out = REPO / "manifests" / "dataset-v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out} ({len(manifest['tasks'])} tasks)")
    print("payloads:", json.dumps(manifest["payloads"], indent=1))
    return 0


def verify() -> int:
    manifest = json.loads((REPO / "manifests" / "dataset-v1.json").read_text())
    problems = []
    if manifest["bank_sha256"] != sha256_file(BANK_DIR / "bank.jsonl"):
        problems.append("bank.jsonl hash != manifest.bank_sha256")
    for rel, meta in manifest["payloads"].items():
        local = REPO / rel
        if local.exists() and sha256_file(local) != meta["sha256"]:
            problems.append(f"{rel}: local file drifted")
        remote = hf_sha(rel)
        if remote != meta["sha256"]:
            problems.append(f"{rel}: remote HF hash mismatch ({remote[:12]}…)")
    for rel, want in manifest["verifier_bundle"].items():
        got = sha256_file(REPO / rel)
        if got != want:
            problems.append(f"verifier bundle drift: {rel}")
    if problems:
        print("VERIFY FAILED:")
        for p in problems:
            print(" -", p)
        return 1
    print("VERIFY OK: bank, payloads (local+remote HF), verifier bundle all match dataset-v1.json")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["build", "verify"])
    args = parser.parse_args()
    return build() if args.action == "build" else verify()


if __name__ == "__main__":
    raise SystemExit(main())
