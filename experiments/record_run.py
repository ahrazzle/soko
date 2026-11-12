#!/usr/bin/env python3
"""Run one planned experiment with a wall limit and retained provenance.

Completion is not acceptance of a route or proof. Raw program output is retained
for separate evaluation, never interpreted as instructions or a verified gain.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_plan(plan: dict) -> None:
    if not isinstance(plan, dict) or plan.get("schema_version") != 1:
        raise ValueError("plan must have schema_version 1")
    for field in ("id", "question", "hypothesis", "intervention", "control", "prediction", "decision_rule"):
        if not isinstance(plan.get(field), str) or not plan[field].strip():
            raise ValueError(f"missing nonempty {field}")
    if plan.get("purpose") not in ("calibration", "candidate_search", "lower_bound_research"):
        raise ValueError("purpose must distinguish calibration, candidate_search or lower_bound_research")
    for field in ("instance", "baseline"):
        if not isinstance(plan.get(field), dict) or not plan[field]:
            raise ValueError(f"missing {field} identity")
    for field in ("source_url", "source_sha256"):
        if not isinstance(plan["instance"].get(field), str) or not plan["instance"][field]:
            raise ValueError(f"missing instance.{field}")
    digest = plan["instance"]["source_sha256"]
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("instance.source_sha256 must be a full lowercase SHA256")
    if not isinstance(plan["baseline"].get("as_of"), str) or not plan["baseline"]["as_of"]:
        raise ValueError("baseline requires an as_of observation date")
    budget = plan.get("wall_seconds")
    if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
        raise ValueError("wall_seconds must be finite and positive")
    if not isinstance(plan.get("tracked_files"), list) or not plan["tracked_files"]:
        raise ValueError("list the executable, implementation and input files to track")
    if not all(isinstance(p, str) and p for p in plan["tracked_files"]):
        raise ValueError("tracked_files must contain paths")
    artifacts = plan.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("artifacts must be a list of paths relative to the run directory")
    for name in artifacts:
        if not isinstance(name, str) or not name:
            raise ValueError("artifact paths must stay inside the run directory and avoid reserved report names")
        path = Path(name)
        if (not path.parts or path.is_absolute() or ".." in path.parts
                or str(path) in ("plan.json", "result.json", "stdout.log", "stderr.log")):
            raise ValueError("artifact paths must stay inside the run directory and avoid reserved report names")


def snapshot(root: Path, paths: list[str]) -> dict:
    return {name: sha256(root / name) for name in paths}


def resolve_executable(command: str, cwd: Path) -> Path | None:
    """Mirror the child's PATH lookup, including relative and empty entries."""
    cwd = cwd.absolute()
    if "/" in command:
        return cwd / command
    search_path = os.pathsep.join(str(cwd / entry) for entry in os.get_exec_path())
    found = shutil.which(command, path=search_path)
    # Preserve symlink spelling: resolving venv/bin/python to its base binary
    # before launch can change the interpreter's virtual environment.
    return Path(found) if found else None


def run(plan_path: Path, output: Path, command: list[str], cwd: Path) -> dict:
    raw_plan = plan_path.read_bytes()
    plan = json.loads(raw_plan)
    validate_plan(plan)
    if not command:
        raise ValueError("provide an explicit command after --")
    before = snapshot(cwd, plan["tracked_files"])
    # One directory per run: never overwrite a previous observation.
    output.mkdir(parents=True, exist_ok=False)
    (output / "plan.json").write_bytes(raw_plan)
    result = {
        "schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": hashlib.sha256(raw_plan).hexdigest(), "plan_id": plan["id"],
        "runner_sha256": sha256(Path(__file__)), "command": command, "cwd": str(cwd),
        "source_hashes_before": before, "wall_seconds": plan["wall_seconds"],
        "acceptance": "not_evaluated", "verified_gain": None,
    }
    executable = resolve_executable(command[0], cwd)
    result["executable"] = str(executable) if executable else None
    result["executable_sha256"] = sha256(executable) if executable and executable.is_file() else None
    started = time.monotonic()
    with (output / "stdout.log").open("wb") as stdout, (output / "stderr.log").open("wb") as stderr:
        try:
            if executable is None:
                raise FileNotFoundError("command was not found on the child's PATH")
            process = subprocess.Popen(command, executable=str(executable), cwd=cwd,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
        except OSError as exc:
            result.update(status="LAUNCH_FAILED", error_type=type(exc).__name__, returncode=None)
        else:
            try:
                code = process.wait(timeout=plan["wall_seconds"])
                result.update(status="COMPLETED" if code == 0 else "COMMAND_FAILED", returncode=code)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                # Kill remaining descendants even if their parent exited on TERM.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
                result.update(status="TIMED_OUT", returncode=process.returncode)
            finally:
                # This run owns its process group; do not leave workers running
                # after recording a completed parent or an interrupted run.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    after = {}
    for name in plan["tracked_files"]:
        try:
            after[name] = sha256(cwd / name)
        except OSError:
            after[name] = None
    result["source_hashes_after"] = after
    result["sources_unchanged"] = before == after
    if before != after:
        result["process_status"] = result["status"]
        result["status"] = "SOURCE_CHANGED"
    result["outputs"] = {name: sha256(output / name) for name in ("stdout.log", "stderr.log")}
    result["artifacts"] = {}
    missing = []
    for name in plan.get("artifacts", []):
        path = output / name
        try:
            if not path.resolve().is_relative_to(output.resolve()):
                raise ValueError("artifact escapes the run directory")
            if not path.is_file():
                raise ValueError("artifact must be a regular file")
            content = path.read_bytes()
            result["artifacts"][name] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
        except (OSError, ValueError, RuntimeError):
            missing.append(name)
    result["missing_artifacts"] = missing
    if missing and result["status"] == "COMPLETED":
        result["process_status"] = result["status"]
        result["status"] = "ARTIFACT_MISSING"
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        result = run(args.plan.resolve(), args.output.resolve(), command, args.cwd.resolve())
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({k: result[k] for k in ("status", "acceptance", "verified_gain", "elapsed_seconds")}))
    if result["status"] == "COMPLETED":
        return 0
    if result["status"] == "TIMED_OUT":
        return 124
    code = result.get("returncode")
    return code if type(code) is int and 0 < code < 126 else 1


if __name__ == "__main__":
    raise SystemExit(main())
