"""CLI entrypoint for `mde_soko` (`verify`, `rederive`, `prose-check`, `build-datasets`, `compile`, `eval`)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Sequence

from soko_mcp.integrity import verify_source_manifest

from .compiler import compile_soko_p2b_from_npz, verify_zero_byte_rederivation
from .datasets_builder import build_all_soko_mde_datasets, verify_soko_datasets_integrity
from .lineage import verify_soko_lineage
from .prose_gate import check_markdown_files
from .scrub import soko_repo_root


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mde_soko", description="Sokoban Eval MDE (`mde:soko-eval`) CLI.")
    parser.add_argument("--repo-root", type=Path, default=None, help="Path to `soko` repository root.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("verify", help="Verify TCB integrity, Plane 1 lineage, datasets SHA256SUMS, and 9/9 re-derivation.")
    sub.add_parser("rederive", help="Run CPU float64 9/9-file 0-byte re-derivation check.")
    sub.add_parser("build-datasets", help="Deterministically rebuild mde_soko/datasets/*.")

    p_prose = sub.add_parser("prose-check", help="Run standalone vendored prose & duplicate-block gate.")
    p_prose.add_argument("files", nargs="*", type=Path, help="Markdown files (defaults to mde_soko/*.md + spec/*.md).")

    p_comp = sub.add_parser("compile", help="Compile mde:soko-eval P2-B + P2-A + sabotage from harvested .npz.")
    p_comp.add_argument("--base-gguf", type=Path, required=True, help="Local Qwen3.5-4B GGUF checkpoint.")

    p_eval = sub.add_parser("eval", help="Run live llama-server evaluation across validation_16 + 18-room S0-S3.")
    p_eval.add_argument("--base-gguf", type=Path, default=None, help="Local Qwen3.5-4B GGUF checkpoint.")
    p_eval.add_argument("--slots", type=int, default=8, help="Parallel llama-server slots.")

    args = parser.parse_args(argv)
    root = (args.repo_root or soko_repo_root()).resolve()

    if args.cmd == "verify":
        tcb = verify_source_manifest(root, root / "SHA256SUMS")
        lin = verify_soko_lineage(repo_root=root)
        ds = verify_soko_datasets_integrity(repo_root=root)
        with tempfile.TemporaryDirectory(prefix="mde_soko_cli_rederive_") as td:
            red = verify_zero_byte_rederivation(
                expected_dir=root / "mde_soko" / "artifacts" / "p2b",
                rederive_dir=Path(td),
                activations_npz=root / "mde_soko" / "artifacts" / "harvested_soko_activations.npz",
                repo_root=root,
            )
        md_files = sorted((root / "mde_soko").rglob("*.md"))
        prose_findings = check_markdown_files(md_files, check_dupes=True) if md_files else []
        tcb_ok = bool(tcb["source_integrity_verified"])
        ok = bool(tcb_ok and lin["ok"] and ds["ok"] and red["zero_byte_diff_all"] and not prose_findings)
        out = {
            "ok": ok,
            "soko_tcb_integrity": {"ok": tcb_ok, "checked_files": tcb["files_verified"]},
            "plane1_lineage": {"ok": lin["ok"]},
            "datasets_integrity": ds,
            "rederivation_9_of_9": {"zero_byte_diff_all": red["zero_byte_diff_all"], "checked_count": red["checked_count"]},
            "prose_findings_count": len(prose_findings),
        }
        sys.stdout.write(json.dumps(out, indent=2, sort_keys=True) + "\n")
        return 0 if ok else 1

    if args.cmd == "rederive":
        with tempfile.TemporaryDirectory(prefix="mde_soko_cli_rederive_") as td:
            red = verify_zero_byte_rederivation(
                expected_dir=root / "mde_soko" / "artifacts" / "p2b",
                rederive_dir=Path(td),
                activations_npz=root / "mde_soko" / "artifacts" / "harvested_soko_activations.npz",
                repo_root=root,
            )
        sys.stdout.write(json.dumps(red, indent=2, sort_keys=True) + "\n")
        return 0 if red["zero_byte_diff_all"] else 1

    if args.cmd == "build-datasets":
        res = build_all_soko_mde_datasets(repo_root=root)
        sys.stdout.write(json.dumps(res, indent=2, sort_keys=True) + "\n")
        return 0

    if args.cmd == "prose-check":
        targets = list(args.files) if args.files else sorted((root / "mde_soko").rglob("*.md"))
        findings = check_markdown_files(targets, check_dupes=True)
        if findings:
            sys.stderr.write(json.dumps(findings, indent=2) + "\n")
            return 1
        sys.stdout.write(json.dumps({"ok": True, "checked_files": len(targets)}) + "\n")
        return 0

    if args.cmd == "compile":
        base_sha = _sha256_file(args.base_gguf.resolve())
        res = compile_soko_p2b_from_npz(
            activations_npz=root / "mde_soko" / "artifacts" / "harvested_soko_activations.npz",
            output_dir=root / "mde_soko" / "artifacts" / "p2b",
            base_weights_sha256=base_sha,
            repo_root=root,
        )
        sys.stdout.write(json.dumps(res, indent=2, sort_keys=True) + "\n")
        return 0

    if args.cmd == "eval":
        from .runner import run_full_soko_live_evaluation

        rec = run_full_soko_live_evaluation(
            repo_root=root,
            base_gguf=args.base_gguf,
            parallel_slots=int(args.slots),
        )
        sys.stdout.write(json.dumps({"ok": True, "git_head_sha": rec["provenance"]["git_head_sha"]}) + "\n")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
