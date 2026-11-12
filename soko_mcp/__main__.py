"""Entry point for `python3 -m soko_mcp` (MCP stdio server by default, plus CLI subcommands)."""
from __future__ import annotations

import argparse
import json
import sys

from .server import dispatch_tool_call, serve_stdio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="soko-verified-mcp",
        description="Sokoban differential replay and bounded exact-state search MCP server.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("serve", help="Run the MCP JSON-RPC 2.0 server over stdio (default when no args given).")
    sub.add_parser("capabilities", help="Report available backends and missing implementations.")
    sub.add_parser("list-rooms", help="List built-in Frontier metadata and reference routes from the registry.")
    sub.add_parser("audit", help="Run the 10-mutation & cross-oracle Proven-Commons Audit.")
    sub.add_parser("tcb-lock", help="Verify runtime SHA256SUMS manifest and TCB checker hashes.")

    p_ins = sub.add_parser("inspect", help="Inspect symmetries and bottlenecks of a room.")
    p_ins.add_argument("--room", required=True, help="Built-in room ID (e.g. III-20)")

    p_ver = sub.add_parser("verify", help="Differential replay of a U/D/L/R/A route across local checkers.")
    p_ver.add_argument("--room", required=True, help="Built-in room ID (e.g. III-20)")
    p_ver.add_argument("--route", required=True, help="Move sequence (U/D/L/R/A)")

    p_opt = sub.add_parser("optimize", help="Shorten a seed with bounded exact BFS (Python window fallback).")
    p_opt.add_argument("--room", required=True, help="Built-in room ID (e.g. III-20)")
    p_opt.add_argument("--route", default="", help="Optional seed route (defaults to room's baseline route)")
    p_opt.add_argument("--beam-width", type=int, default=40000)
    p_opt.add_argument("--budget-sec", type=int, default=35)

    p_flr = sub.add_parser("prove-floor", help="Compute a capped exact-state BFS lower bound via the C++ engine.")
    p_flr.add_argument("--room", required=True, help="Built-in room ID (e.g. I-1, III-14, III-22)")
    p_flr.add_argument("--max-bound", type=int, default=32)
    p_flr.add_argument("--budget-sec", type=int, default=10)

    args = parser.parse_args(argv)
    if args.cmd in (None, "serve"):
        return serve_stdio()
    if args.cmd == "capabilities":
        out = dispatch_tool_call("soko_capabilities", {})
    elif args.cmd == "list-rooms":
        out = dispatch_tool_call("soko_list_rooms", {})
    elif args.cmd == "audit":
        out = dispatch_tool_call("soko_run_planted_bug_audit", {})
    elif args.cmd == "tcb-lock":
        out = dispatch_tool_call("soko_verify_tcb_lock", {})
    elif args.cmd == "inspect":
        out = dispatch_tool_call("soko_inspect_room", {"room_id": args.room})
    elif args.cmd == "verify":
        out = dispatch_tool_call("soko_verify_route", {"room_id": args.room, "route": args.route})
    elif args.cmd == "optimize":
        payload = {"room_id": args.room, "beam_width": args.beam_width, "budget_sec": args.budget_sec}
        if args.route:
            payload["seed_route"] = args.route
        out = dispatch_tool_call("soko_optimize_route", payload)
    elif args.cmd == "prove-floor":
        out = dispatch_tool_call(
            "soko_prove_floor",
            {"room_id": args.room, "max_bound": args.max_bound, "budget_sec": args.budget_sec},
        )
    else:
        return 1

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
