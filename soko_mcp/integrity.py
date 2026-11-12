"""Strict, portable source-manifest checks; no claim of binary reproducibility.

After reviewing a source change, run ``python3 -m soko_mcp.integrity --write``
and review the manifest diff with the source diff. This is a consistency check
against a repository-owned manifest, not independent approval or authenticity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parent.parent
# Exact coverage is intentional: a valid hash of one unrelated file cannot
# substitute for the implementation that accepts certificates.
REQUIRED_SOURCES = (
    "cpp/soko_engine.cpp",
    "soko_mcp/__init__.py",
    "soko_mcp/__main__.py",
    "soko_mcp/analyzer.py",
    "soko_mcp/catalog.py",
    "soko_mcp/data/catalog.json",
    "soko_mcp/engine_bridge.py",
    "soko_mcp/evidence.py",
    "soko_mcp/flat_oracle.py",
    "soko_mcp/formal_kernel.py",
    "soko_mcp/integrity.py",
    "soko_mcp/oracle.py",
    "soko_mcp/original.py",
    "soko_mcp/play.py",
    "soko_mcp/server.py",
)


def confined_path(root: Path, relative: str) -> tuple[Path | None, str | None]:
    parts = relative.replace("\\", "/").split("/")
    if not relative or relative.startswith("/") or ".." in parts:
        return None, "absolute_empty_or_parent_path"
    if "\\" in relative or any(p in ("", ".") for p in parts):
        return None, "noncanonical_path"
    target = root / relative
    try:
        target.resolve().relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError):
        return None, "escapes_repo_root"
    return target, None


def verify_source_manifest(root: Path, manifest: Path) -> dict:
    result = {
        "manifest_present": manifest.is_file(),
        "manifest_sha256": None,
        "files_verified": 0,
        "mismatched_files": [],
        "missing_files": [],
        "unconfined_paths": [],
        "malformed_lines": [],
        "duplicate_entries": [],
        "missing_entries": [],
        "unexpected_entries": [],
        "read_errors": [],
    }
    entries = {}
    try:
        raw = manifest.read_bytes()
        result["manifest_sha256"] = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        result["read_errors"].append({"file": str(manifest), "error": type(exc).__name__})
        text = ""
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if match is None:
            result["malformed_lines"].append(number)
            continue
        digest, relative = match.groups()
        target, error = confined_path(root, relative)
        if error:
            result["unconfined_paths"].append({"file": relative, "reason": error})
            continue
        if relative in entries:
            result["duplicate_entries"].append(relative)
            continue
        entries[relative] = digest
        if relative not in REQUIRED_SOURCES:
            result["unexpected_entries"].append(relative)
            continue
        try:
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
        except FileNotFoundError:
            result["missing_files"].append(relative)
            continue
        except OSError as exc:
            result["read_errors"].append({"file": relative, "error": type(exc).__name__})
            continue
        if actual != digest:
            result["mismatched_files"].append({"file": relative, "expected": digest, "actual": actual})
        else:
            result["files_verified"] += 1
    result["missing_entries"] = sorted(set(REQUIRED_SOURCES) - set(entries))
    result["source_integrity_verified"] = bool(result["manifest_present"]) and not any(
        result[key] for key in (
            "mismatched_files", "missing_files", "unconfined_paths", "malformed_lines",
            "duplicate_entries", "missing_entries", "unexpected_entries", "read_errors",
        )
    )
    return result


def render_source_manifest(root: Path) -> str:
    lines = []
    for relative in REQUIRED_SOURCES:
        path, error = confined_path(root, relative)
        if error:
            raise ValueError(f"Cannot hash {relative}: {error}")
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Explicitly replace the source manifest after source review")
    args = parser.parse_args()
    manifest = REPO_ROOT / "SHA256SUMS"
    if args.write:
        manifest.write_text(render_source_manifest(REPO_ROOT), encoding="utf-8")
    result = verify_source_manifest(REPO_ROOT, manifest)
    print(json.dumps(result, indent=2))
    return 0 if result["source_integrity_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
