#!/usr/bin/env python3
"""Capture bounded, reproducible MCP experiments without asserting optimality.

Uses only the standard library and the server's public stdio JSON-RPC interface.
An outer per-request timeout also kills the server's children. Run from any cwd.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time


class Client:
    def __init__(self, checkout: Path, timeout: float):
        self.timeout = timeout
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "soko_mcp"], cwd=checkout,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        self.request_id = 0
        self.pending = b""

    def call(self, method: str, params: dict | None = None) -> dict:
        self.request_id += 1
        request = {"jsonrpc": "2.0", "id": self.request_id, "method": method}
        if params is not None:
            request["params"] = params
        self.proc.stdin.write(json.dumps(request).encode() + b"\n")
        self.proc.stdin.flush()
        started = time.monotonic()
        while b"\n" not in self.pending:
            remaining = self.timeout - (time.monotonic() - started)
            if remaining <= 0 or not select.select([self.proc.stdout], [], [], remaining)[0]:
                raise TimeoutError(f"MCP request exceeded {self.timeout}s: {method}")
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError("MCP server closed stdout before replying")
            self.pending += chunk
        line, self.pending = self.pending.split(b"\n", 1)
        response = json.loads(line)
        if response.get("id") != self.request_id:
            raise RuntimeError("MCP response id mismatch")
        return {"request": request, "response": response,
                "elapsed_seconds": round(time.monotonic() - started, 6)}

    def close(self):
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait()
        self.proc.stdin.close()
        self.proc.stdout.close()


def source_hashes(root: Path) -> dict:
    paths = list((root / "soko_mcp").glob("*.py"))
    paths += [root / "cpp/soko_engine.cpp", root / "SHA256SUMS"]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--source-revision", help="Commit identifying an exported checkout, if known")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    root = args.checkout.resolve()
    evidence = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "source_revision": args.source_revision,
        "source_hashes_before": source_hashes(root),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "per_request_wall_timeout_seconds": args.timeout,
        "scope": "Local differential replay and bounded exact-state search for MCP stdio exercise captures.",
        "experiments": [],
    }
    client = Client(root, args.timeout)
    status = 0
    try:
        evidence["initialize"] = client.call("initialize", {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "soko-bounded-experiment", "version": "1"},
        })
        evidence["tools"] = client.call("tools/list")
        registry = client.call("resources/read", {"uri": "soko://benchmarks/frontier"})
        evidence["registry"] = registry
        for name, arguments in [
            ("soko_capabilities", {}),
            ("soko_verify_tcb_lock", {}),
            ("soko_verify_route", {"room_id": "I-1", "route": "URRRRRRRRRD"}),
            ("soko_optimize_route", {"room_id": "I-1", "seed_route": "URRRRRRRRRD",
                                     "window_len": 14, "beam_width": 2000, "budget_sec": 4}),
            ("soko_solve_room", {"room_id": "I-1", "max_depth": 12,
                                 "beam_width": 2000, "budget_sec": 2}),
            ("soko_optimize_route", {"room_id": "III-14", "window_len": 14,
                                     "beam_width": 2000, "budget_sec": 4}),
            ("soko_prove_floor", {"room_id": "III-14", "max_bound": 48, "budget_sec": 2}),
        ]:
            result = client.call("tools/call", {"name": name, "arguments": arguments})
            evidence["experiments"].append(result)
            reply = result["response"].get("result", {})
            if "error" in result["response"] or reply.get("isError"):
                status = 1
            data = reply.get("structuredContent", {})
            route = data.get("best_route", data.get("route"))
            if name in ("soko_optimize_route", "soko_solve_room") and route is not None:
                replay = client.call("tools/call", {
                    "name": "soko_verify_route",
                    "arguments": {"room_id": arguments["room_id"], "route": route},
                })
                evidence["experiments"].append(replay)
                checked = replay["response"].get("result", {}).get("structuredContent", {})
                if not (checked.get("valid_winning_route") and checked.get("differential_match")
                        and checked.get("engines_count", 0) >= 2):
                    status = 1
    except Exception as exc:
        evidence["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        status = 1
    finally:
        client.close()
        evidence["source_hashes_after"] = source_hashes(root)
        evidence["sources_unchanged"] = evidence["source_hashes_before"] == evidence["source_hashes_after"]
        if not evidence["sources_unchanged"]:
            status = 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"Evidence: {args.output}; exit={status}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
