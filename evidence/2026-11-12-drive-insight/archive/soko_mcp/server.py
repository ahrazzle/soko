"""Standards-compliant Model Context Protocol (MCP) stdio JSON-RPC 2.0 server for Verified-Bar Sokoban."""
from __future__ import annotations
import json
import sys
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from . import __version__
from .analyzer import inspect_room
from .engine_bridge import (
    ensure_cpp_engine, optimize_route_verified, prove_floor_verified,
    resolve_room_input, solve_room_verified, verify_route_dual,
)
from .oracle import FRONTIER_ROOMS, run_planted_bug_audit

SUPPORTED_PROTOCOLS = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28"]
SERVER_INFO = {"name": "soko-verified-mcp", "version": __version__}
SERVER_INSTRUCTIONS = (
    "Verified-Bar Sokoban & PuzzleScript MCP server (declarative oracle + C++20 chiral-mirror tube-beam "
    "optimizer, window BFS, 10-mutation planted-bug suite, and step-consistent IDA* floor prover)."
)
RO_ANNOT = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}
ROOM_PROPS: Dict[str, Any] = {
    "room_id": {"type": "string", "description": "Built-in Frontier room ID (e.g. 'I-1', 'II-22', 'III-14', 'III-15', 'III-20', 'III-22')."},
    "part": {"type": "integer", "enum": [1, 2, 3], "description": "Game part (1, 2, or 3) when passing custom grid."},
    "grid": {"type": "array", "items": {"type": "string"}, "description": "Rectangular ASCII room rows."},
}

def _tool(name: str, title: str, desc: str, props: Dict[str, Any], req: Optional[List[str]] = None) -> Dict[str, Any]:
    schema: Dict[str, Any] = {"type": "object", "properties": props, "additionalProperties": False}
    if req:
        schema["required"] = req
    return {"name": name, "title": title, "description": desc, "inputSchema": schema, "annotations": RO_ANNOT}

TOOLS: List[Dict[str, Any]] = [
    _tool("soko_list_rooms", "List Frontier Rooms", "List built-in Frontier benchmark rooms, floors, records, and C++20 readiness.", {}),
    _tool("soko_inspect_room", "Inspect Room Symmetries & Chirality", "Analyze X/Y/180 symmetries, hero chirality, switch deficits, and Bard constraints.", ROOM_PROPS),
    _tool("soko_verify_route", "Dual-Oracle Route Verifier", "Replay a U/D/L/R/A route in Python + C++20 and emit a SHA-256 VERIFIED certificate.",
          {**ROOM_PROPS, "route": {"type": "string", "description": "Move string (U/D/L/R/A)."}}, ["route"]),
    _tool("soko_optimize_route", "Optimize Route (Window BFS + Chiral Tube Beam)",
          "Shorten a valid route via Windowed BFS, Chiral-Mirror Tube Beam, and Iterative Refinement.",
          {**ROOM_PROPS, "seed_route": {"type": "string"}, "beam_width": {"type": "integer", "default": 40000},
           "window_len": {"type": "integer", "default": 14}, "budget_sec": {"type": "integer", "default": 35}}),
    _tool("soko_solve_room", "Solve Room From Scratch", "Find a verified winning route from scratch via bucket-diversified C++20 beam search.",
          {**ROOM_PROPS, "max_depth": {"type": "integer", "default": 120}, "beam_width": {"type": "integer", "default": 40000},
           "budget_sec": {"type": "integer", "default": 20}}),
    _tool("soko_prove_floor", "Prove Step-Consistent Lower Bound", "Prove floor >= B via IDA* with runtime h(s) <= 1 + h(s') edge checks.",
          {**ROOM_PROPS, "max_bound": {"type": "integer", "default": 25}, "budget_sec": {"type": "integer", "default": 12}}),
    _tool("soko_run_planted_bug_audit", "Run 10-Mutation Planted-Bug Audit", "Verify 10/10 PuzzleScript engine bug mutations are caught.",
          {"extra_vectors": {"type": "array", "items": {"type": "object"}}}),
]

RESOURCES: List[Dict[str, Any]] = [
    {"uri": "soko://methodology/verified-bar", "name": "Proven-Commons Verified Bar Methodology", "mimeType": "text/markdown"},
    {"uri": "soko://benchmarks/frontier", "name": "Sokoban Eval Frontier Benchmark Registry", "mimeType": "application/json"},
    {"uri": "soko://rules/puzzlescript-trilogy", "name": "Heroes of Sokoban I-III Mechanics", "mimeType": "text/markdown"},
]

PROMPTS: List[Dict[str, Any]] = [
    {"name": "break_room_record", "description": "Verified-Bar workflow to inspect, verify, chiral-optimize, and certify a room record.",
     "arguments": [{"name": "room_id", "required": True}]},
    {"name": "certify_room_floor", "description": "Workflow to run planted-bug audit and certify a step-consistent lower bound.",
     "arguments": [{"name": "room_id", "required": True}]},
]

def _read_resource(uri: str) -> Dict[str, Any]:
    if uri == "soko://benchmarks/frontier":
        return {"uri": uri, "mimeType": "application/json", "text": json.dumps(FRONTIER_ROOMS, indent=2)}
    if uri == "soko://methodology/verified-bar":
        return {"uri": uri, "mimeType": "text/markdown", "text": (
            "# Proven-Commons Verified Bar for Sokoban Eval\n"
            "1. Spec/Code separation (`oracle.py` vs `cpp/soko_engine.cpp`).\n"
            "2. Dual-oracle differential replay on every candidate route (`VERIFIED`).\n"
            "3. 10/10 Planted-Bug mutation audit (`soko_run_planted_bug_audit`).\n"
            "4. Chiral-Mirror & Iterative Tube Beam (`soko_optimize_route`, `87 -> 84` on `III-20`).\n"
            "5. Runtime step-consistent IDA* lower bounds (`h(s) <= 1 + h(s')` checked per edge).\n"
        )}
    if uri == "soko://rules/puzzlescript-trilogy":
        return {"uri": uri, "mimeType": "text/markdown", "text": (
            "# Heroes of Sokoban I-III Rules\n"
            "Keys: U,D,L,R,A (switches 1->2->3->4->5->6->1 scanning x=0..W-1, y=0..H-1).\n"
            "F pushes Moveable chains; T pulls 1 Moveable; W swaps along ray or steps 1 against Static; "
            "P/4 shields orthogonal heroes; B translates 5x5 prior-turn Note aura; D transmutes # <-> * and O/hero -> #.\n"
        )}
    raise KeyError(f"Unknown resource URI: {uri}")

def _get_prompt(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    rid = args.get("room_id", "III-20")
    if name == "break_room_record":
        txt = (f"Optimize room `{rid}` under the Verified Bar:\n"
               f"1. Call `soko_inspect_room` on `{rid}`.\n2. Call `soko_verify_route` on baseline.\n"
               f"3. Call `soko_optimize_route` to run Window BFS + Chiral-Mirror Tube Beam + Iterative Refinement.")
        return {"description": f"Break record on {rid}", "messages": [{"role": "user", "content": {"type": "text", "text": txt}}]}
    if name == "certify_room_floor":
        txt = f"1. Call `soko_run_planted_bug_audit`.\n2. Call `soko_prove_floor` on `{rid}` and report `edge_consistency_checks`."
        return {"description": f"Certify floor on {rid}", "messages": [{"role": "user", "content": {"type": "text", "text": txt}}]}
    raise KeyError(f"Unknown prompt: {name}")

def dispatch_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "soko_list_rooms":
        return {"cpp_engine_ready": ensure_cpp_engine() is not None,
                "rooms": {k: {kk: vv for kk, vv in m.items() if kk != "grid"} for k, m in FRONTIER_ROOMS.items()}}
    if name == "soko_inspect_room":
        rid, part, grid, meta = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        out = inspect_room(part, grid)
        if rid and meta:
            out["room_id"] = rid; out["title"] = meta["title"]
        return out
    if name == "soko_verify_route":
        rid, part, grid, _ = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        res = verify_route_dual(part, grid, str(args["route"]))
        if rid: res["room_id"] = rid
        return res
    if name == "soko_optimize_route":
        rid, part, grid, meta = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        seed = args.get("seed_route") or (meta.get("prior_record_route_87") or meta.get("reference_route") if meta else None)
        if not seed: raise ValueError("Missing seed_route")
        res = optimize_route_verified(part, grid, str(seed), int(args.get("beam_width", 40000)),
                                      int(args.get("window_len", 14)), int(args.get("budget_sec", 35)))
        if rid: res["room_id"] = rid
        return res
    if name == "soko_solve_room":
        rid, part, grid, _ = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        res = solve_room_verified(part, grid, int(args.get("max_depth", 120)),
                                  int(args.get("beam_width", 40000)), int(args.get("budget_sec", 20)))
        if rid: res["room_id"] = rid
        return res
    if name == "soko_prove_floor":
        rid, part, grid, _ = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        res = prove_floor_verified(part, grid, int(args.get("max_bound", 25)), int(args.get("budget_sec", 12)))
        if rid: res["room_id"] = rid
        return res
    if name == "soko_run_planted_bug_audit":
        return run_planted_bug_audit(args.get("extra_vectors"))
    raise KeyError(f"Unknown tool: {name}")

def handle_jsonrpc_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None: return None
    if method == "initialize":
        rv = params.get("protocolVersion", "2025-03-26")
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": rv if rv in SUPPORTED_PROTOCOLS else "2025-03-26",
            "capabilities": {"tools": {"listChanged": False}, "resources": {"subscribe": False, "listChanged": False}, "prompts": {"listChanged": False}},
            "serverInfo": SERVER_INFO, "instructions": SERVER_INSTRUCTIONS,
        }}
    if method == "server/discover":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersions": SUPPORTED_PROTOCOLS, "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": SERVER_INFO, "instructions": SERVER_INSTRUCTIONS,
        }}
    if method == "ping": return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list": return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        tname, targs = params.get("name"), params.get("arguments") or {}
        if not tname or not any(t["name"] == tname for t in TOOLS):
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Unknown tool: {tname!r}"}}
        try:
            p = dispatch_tool_call(tname, targs)
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(p, indent=2)}], "structuredContent": p, "isError": False}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps({"error": str(exc), "tool": tname})}], "isError": True}}
    if method == "resources/list": return {"jsonrpc": "2.0", "id": mid, "result": {"resources": RESOURCES}}
    if method == "resources/read":
        try: return {"jsonrpc": "2.0", "id": mid, "result": {"contents": [_read_resource(params.get("uri", ""))]}}
        except KeyError as exc: return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": str(exc)}}
    if method == "prompts/list": return {"jsonrpc": "2.0", "id": mid, "result": {"prompts": PROMPTS}}
    if method == "prompts/get":
        try: return {"jsonrpc": "2.0", "id": mid, "result": _get_prompt(params.get("name", ""), params.get("arguments") or {})}
        except KeyError as exc: return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": str(exc)}}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method!r}"}}

def _read_msg(stream: BinaryIO) -> Optional[Tuple[Any, bool]]:
    while True:
        line = stream.readline()
        if not line: return None
        s = line.strip()
        if not s: continue
        if s.lower().startswith(b"content-length:"):
            n = int(s.split(b":", 1)[1].strip())
            while (hdr := stream.readline()) and hdr not in (b"\r\n", b"\n"): pass
            return json.loads(stream.read(n).decode("utf-8")), True
        return json.loads(s.decode("utf-8")), False

def _write_msg(stream: BinaryIO, payload: Any, use_cl: bool = False) -> None:
    enc = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    stream.write((f"Content-Length: {len(enc)}\r\n\r\n".encode("ascii") + enc) if use_cl else (enc + b"\n"))
    stream.flush()

def serve_stdio() -> int:
    try: ensure_cpp_engine()
    except Exception as exc: sys.stderr.write(f"[soko-verified-mcp] {exc}\n")
    while (item := _read_msg(sys.stdin.buffer)) is not None:
        msg, use_cl = item
        if isinstance(msg, list):
            if reps := [r for sub in msg if (r := handle_jsonrpc_message(sub)) is not None]:
                _write_msg(sys.stdout.buffer, reps, use_cl)
        elif isinstance(msg, dict) and (rep := handle_jsonrpc_message(msg)) is not None:
            _write_msg(sys.stdout.buffer, rep, use_cl)
    return 0
