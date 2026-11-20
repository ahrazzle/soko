"""Plane 1 lineage computation and fail-closed staleness verification for `mde:soko-eval`."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .scrub import sha256_lf_bytes, soko_repo_root, write_clean_json_atomic

TRACKED_SOKO_PLANE1_RELPATHS: tuple[str, ...] = (
    "SHA256SUMS",
    "mde_soko/spec/plane1_soko_spec.md",
    "mde_soko/spec/zone-manifest.soko_eval.v0.1.json",
)


def compute_zone_manifest_id(zone_manifest_path: Path) -> str:
    obj = json.loads(zone_manifest_path.read_text(encoding="utf-8"))
    canon = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def compute_soko_plane1_lineage(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Compute exact Plane 1 lineage and locked `SHA256SUMS` verification dynamically."""
    root = (repo_root or soko_repo_root()).resolve()
    tracked_digests: dict[str, str] = {}
    tracked_bytes: dict[str, int] = {}

    for rel in TRACKED_SOKO_PLANE1_RELPATHS:
        fpath = root / rel
        if not fpath.is_file():
            raise FileNotFoundError(f"Missing tracked Plane 1 file: {rel}")
        digest, size = sha256_lf_bytes(fpath)
        tracked_digests[rel] = digest
        tracked_bytes[rel] = size

    # Verify every locked checker entry in root SHA256SUMS
    locked_ok = True
    locked_count = 0
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        exp_sha, rel_target = s.split(None, 1)
        rel_target = rel_target.strip()
        actual_sha = hashlib.sha256((root / rel_target).read_bytes()).hexdigest()
        locked_count += 1
        if actual_sha != exp_sha:
            locked_ok = False

    if not locked_ok:
        raise ValueError("Locked soko_mcp SHA256SUMS verification failed")

    tree_payload = "\n".join(f"{k}:{v}" for k, v in sorted(tracked_digests.items())).encode("utf-8")
    corpus_tree_sha256 = hashlib.sha256(tree_payload).hexdigest()
    zone_manifest_id = compute_zone_manifest_id(
        root / "mde_soko" / "spec" / "zone-manifest.soko_eval.v0.1.json"
    )

    spec_text = (root / "mde_soko" / "spec" / "plane1_soko_spec.md").read_text(encoding="utf-8")
    est_words = len(spec_text.split())

    return {
        "schema": "mde-soko-lineage/v0.1",
        "domain_id": "mde:soko-eval",
        "plane1_spec_relpath": "mde_soko/spec/plane1_soko_spec.md",
        "plane1_spec_sha256": tracked_digests["mde_soko/spec/plane1_soko_spec.md"],
        "plane1_spec_bytes": tracked_bytes["mde_soko/spec/plane1_soko_spec.md"],
        "plane1_spec_word_count": est_words,
        "zone_manifest_id": zone_manifest_id,
        "locked_soko_sha256sums_verified": locked_ok,
        "locked_soko_file_count": locked_count,
        "tracked_plane1_files": tracked_digests,
        "source_lineage": {
            "corpus_tree_sha256": corpus_tree_sha256,
            "soko_sha256sums_digest": tracked_digests["SHA256SUMS"],
            "contested_heads": [],
        },
    }


def write_soko_lineage_json(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or soko_repo_root()).resolve()
    lin = compute_soko_plane1_lineage(repo_root=root)
    write_clean_json_atomic(root / "mde_soko" / "spec" / "lineage.json", lin)
    return lin


def verify_soko_lineage(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or soko_repo_root()).resolve()
    lin_path = root / "mde_soko" / "spec" / "lineage.json"
    if not lin_path.is_file():
        return {"ok": False, "stale_lineage": True, "reason": "missing_lineage_json"}
    recorded = json.loads(lin_path.read_text(encoding="utf-8"))
    try:
        current = compute_soko_plane1_lineage(repo_root=root)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "stale_lineage": True, "reason": str(exc)}

    same = (
        recorded.get("plane1_spec_sha256") == current["plane1_spec_sha256"]
        and recorded.get("zone_manifest_id") == current["zone_manifest_id"]
        and recorded.get("tracked_plane1_files") == current["tracked_plane1_files"]
        and recorded.get("source_lineage") == current["source_lineage"]
    )
    return {
        "ok": same,
        "stale_lineage": not same,
        "corpus_tree_sha256": current["source_lineage"]["corpus_tree_sha256"],
        "zone_manifest_id": current["zone_manifest_id"],
    }
