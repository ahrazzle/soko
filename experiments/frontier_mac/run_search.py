"""Run the recovered searcher, then validate its candidate independently.

The C++ engine is an untrusted candidate generator. It is not the proof checker.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from replay_instance import replay


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--budget-sec", type=int, default=60)
    parser.add_argument("--beam-width", type=int, default=40000)
    parser.add_argument("--window", type=int, default=18)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (1 <= args.budget_sec <= 180 and 2000 <= args.beam_width <= 100000 and 8 <= args.window <= 24):
        parser.error("bounded experiment: budget 1..180, beam 2000..100000, window 8..24")
    instance = json.loads(args.instance.read_text())
    seed = replay(instance)
    if not seed["valid_winning_route"]:
        parser.error("seed does not pass independent replay")
    source = Path(__file__).with_name("recovered_engine.cpp")
    compiler = shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        parser.error("a C++20 compiler is required")
    result = {
        "evidence_level": "bounded_heuristic_search",
        "formal_proof_checked": False,
        "seed_certificate_sha256": seed["certificate_sha256"],
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "compiler": Path(compiler).name,
        "parameters": {"budget_sec": args.budget_sec, "beam_width": args.beam_width, "window": args.window},
        "warning": "The original budget bounds beam phases, not the total search. A separate process timeout bounds wall time.",
    }
    stage = "compiler_version"
    try:
        result["compiler"] = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]
        with tempfile.TemporaryDirectory() as directory:
            binary = str(Path(directory) / "search")
            stage = "compile"
            subprocess.run([compiler, "-O3", "-pthread", "-std=c++20", str(source), "-o", binary], check=True, timeout=60)
            grid = instance["grid"]
            payload = f"optimize {instance['part']} {len(grid[0])} {len(grid)} {args.beam_width} {args.window} {args.budget_sec}\n" + "\n".join(grid) + "\n" + instance["route"] + "\n"
            stage = "search"
            start = time.monotonic()
            try:
                process = subprocess.run([binary], input=payload, text=True, capture_output=True, check=True, timeout=args.budget_sec + 45)
                result["search"] = json.loads(process.stdout.strip().splitlines()[-1])
                stage = "candidate_replay"
                candidate = dict(instance, route=result["search"]["best_route"])
                result["candidate_certificate"] = replay(candidate)
                result["status"] = "CANDIDATE_ACCEPTED" if result["candidate_certificate"]["valid_winning_route"] else "CANDIDATE_REJECTED"
            except subprocess.TimeoutExpired:
                result["status"] = "TIMEOUT_NO_CANDIDATE_RETURNED"
            result["elapsed_seconds"] = round(time.monotonic() - start, 3)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError, KeyError, IndexError) as exc:
        result["status"] = "BACKEND_FAILED"
        result["error_type"] = type(exc).__name__
        result["error_stage"] = stage
        result["diagnostic"] = "The backend failed during " + stage + ". Raw process output is omitted to avoid exposing local paths."
        if isinstance(exc, subprocess.CalledProcessError):
            result["return_code"] = exc.returncode
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "elapsed_seconds") if k in result}, indent=2))
    return 0 if result["status"] == "CANDIDATE_ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
