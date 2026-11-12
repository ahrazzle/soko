"""MCP stdio JSON-RPC server for Sokoban differential replay and bounded exact-state search."""
from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from . import __version__
from .analyzer import inspect_room
from .evidence import digest
from .engine_bridge import (
    ensure_cpp_engine,
    get_capabilities,
    optimize_route_verified,
    prove_floor_verified,
    resolve_room_input,
    solve_room_verified,
    verify_route_dual,
    verify_tcb_lock,
)
from .oracle import FRONTIER_ROOMS, run_planted_bug_audit

SUPPORTED_PROTOCOLS = [
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
    "2026-07-28",
]

SERVER_INFO = {
    "name": "soko-verified-mcp",
    "version": __version__,
}

SERVER_INSTRUCTIONS = (
    "Sokoban differential replay and bounded exact-state search through nine soko_* MCP tools. "
    "VERIFIED on a route means at least two local checkers executed and agreed on survival, exact win, "
    "steps, final grid, and trajectory digest, with required checker source hashes present. "
    "Use canonical starting rooms, read search termination and budget fields, and treat built-in registry "
    "floors and reference routes as historical metadata."
)

ROOM_INPUT_PROPERTIES: Dict[str, Any] = {
    "room_id": {
        "type": "string",
        "description": "Optional built-in Sokoban Eval Frontier room ID (e.g. 'I-1', 'II-22', 'III-14', 'III-15', 'III-20', 'III-22'). Omit when passing custom 'part' and 'grid'.",
    },
    "part": {
        "type": "integer",
        "enum": [1, 2, 3],
        "description": "Heroes of Sokoban game part (1 = Part I, 2 = Part II: Monsters, 3 = Part III: The Bard and The Druid). Required when 'room_id' is omitted.",
    },
    "grid": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Rectangular ASCII room rows using PuzzleScript symbols (# wall, . floor, G goal, * crate, O goblin, L/R dragons, {/} switches, [/] doors, M monster gate, F/T/W/P/B/D active heroes, 1..6 inactive heroes).",
    },
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "soko_capabilities",
        "description": "Report available backends and missing implementations in this checkout.",
        "inputSchema": {"type": "object", "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_list_rooms",
        "title": "List Built-In Frontier Benchmark Rooms",
        "description": "List built-in Frontier room metadata and reference routes from the repository registry, including historical floor and record fields.",
        "inputSchema": {"type": "object", "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_inspect_room",
        "title": "Inspect Room Symmetries, Chirality & Bottlenecks",
        "description": "Analyze a built-in room_id or custom (part, grid) for X/Y/180-degree dungeon symmetries, hero-switch chirality opportunities, switch-weighing deficits, and Bard rigid-translation constraints.",
        "inputSchema": {
            "type": "object",
            "properties": ROOM_INPUT_PROPERTIES,
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_verify_route",
        "title": "Dual-Oracle Differential Route Verifier",
        "description": "Replay a canonical starting room through the Python specification oracle, flat bitmask oracle, and C++ engine when compiled; return instance-bound differential evidence (evidence_level differential_replay).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **ROOM_INPUT_PROPERTIES,
                "route": {
                    "type": "string",
                    "description": "Move string composed of U, D, L, R, and A (Action: switch active hero).",
                },
            },
            "required": ["route"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_optimize_route",
        "title": "Shorten a Seed Route with Bounded Exact BFS",
        "description": "Try a shorter route with time- and state-bounded exact BFS; retain the seed if no improvement is found. Replay every candidate independently. Python window BFS is the fallback when C++ is unavailable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **ROOM_INPUT_PROPERTIES,
                "seed_route": {
                    "type": "string",
                    "description": "Valid U/D/L/R/A winning route to optimize (if omitted for a built-in room_id, uses the room's reference or prior record route).",
                },
                "beam_width": {
                    "type": "integer",
                    "default": 40000,
                    "minimum": 2000,
                    "maximum": 120000,
                    "description": "Legacy name: maximum total retained BFS states (native hard ceiling 200000).",
                },
                "window_len": {
                    "type": "integer",
                    "default": 14,
                    "minimum": 8,
                    "maximum": 22,
                    "description": "Window length for the Python fallback only; ignored by native exact BFS.",
                },
                "budget_sec": {
                    "type": "integer",
                    "default": 35,
                    "minimum": 4,
                    "maximum": 180,
                    "description": "Search-phase time budget in seconds; compilation and independent replay are additional.",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_solve_room",
        "title": "Solve a Room with Bounded Exact BFS",
        "description": "Search with exact-state BFS and time/state caps, then independently replay a winning route. beam_width is the legacy name for the total state cap.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **ROOM_INPUT_PROPERTIES,
                "max_depth": {"type": "integer", "default": 120, "minimum": 1, "maximum": 500},
                "beam_width": {"type": "integer", "default": 40000, "minimum": 2000, "maximum": 120000},
                "budget_sec": {"type": "integer", "default": 20, "minimum": 2, "maximum": 180},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_prove_floor",
        "title": "Compute a Local Exhaustive-Search Lower Bound",
        "description": "Run capped exact-state BFS in the local C++ engine and report exhausted goal depths with termination_reason and completed_depth; quotient PDB stays disabled (quotient_pdb_enabled false).",
        "inputSchema": {
            "type": "object",
            "properties": {
                **ROOM_INPUT_PROPERTIES,
                "max_bound": {"type": "integer", "default": 25, "minimum": 1, "maximum": 200},
                "budget_sec": {"type": "integer", "default": 12, "minimum": 2, "maximum": 120},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_verify_tcb_lock",
        "title": "Verify Runtime SHA256SUMS TCB Lock",
        "description": "Verify repository source files against SHA256SUMS (lock_scope source_manifest) and report the compiled binary hash separately as provenance.",
        "inputSchema": {"type": "object", "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_run_planted_bug_audit",
        "title": "Run 10-Mutation Proven-Commons Planted-Bug Audit",
        "description": "Inject 10 realistic PuzzleScript physics bugs into the specification oracle (single-push collapse, rule-order swap, Bard Manhattan/post-move bugs, non-weighing walls, Wizard adjacent swap, inactive Priest heal, sequential Goblin kill, hero-cycle swap, missing Cancel) and verify 10/10 detection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "extra_vectors": {
                    "type": "array",
                    "description": "Optional additional regression test vectors to include in the mutation audit.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "part": {"type": "integer", "enum": [1, 2, 3]},
                            "grid": {"type": "array", "items": {"type": "string"}},
                            "route": {"type": "string"},
                            "expect_alive": {"type": "boolean"},
                            "expect_win": {"type": "boolean"},
                        },
                        "required": ["part", "grid", "route"],
                    },
                }
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
]

RESOURCES: List[Dict[str, Any]] = [
    {
        "uri": "soko://methodology/verified-bar",
        "name": "Proven-Commons Verified Bar Methodology for PuzzleScript",
        "description": "How local differential replay, bounded search, and source integrity relate to the Proven-Commons Verified Bar in this checkout.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "soko://benchmarks/frontier",
        "name": "Sokoban Eval Frontier Benchmark Registry",
        "description": "Historical built-in Frontier metadata and reference routes; current public records may differ.",
        "mimeType": "application/json",
    },
    {
        "uri": "soko://rules/puzzlescript-trilogy",
        "name": "Heroes of Sokoban I, II, & III Exact Mechanics Reference",
        "description": "Exact tile legend, Action switch cycle order, hero movement laws, Bard 5x5 aura fixed-point rules, Druid transmutations, and Late phase order.",
        "mimeType": "text/markdown",
    },
]

PROMPTS: List[Dict[str, Any]] = [
    {
        "name": "break_room_record",
        "description": "Step-by-step workflow for room analysis, oracle audit, and bounded route shortening with differential replay.",
        "arguments": [
            {"name": "room_id", "description": "Built-in room ID (e.g. 'III-20' or 'II-22') or 'custom'", "required": True},
        ],
    },
    {
        "name": "certify_room_floor",
        "description": "Step-by-step workflow for a bounded exhaustive-search lower bound with explicit epistemic tagging.",
        "arguments": [
            {"name": "room_id", "description": "Built-in room ID or 'custom'", "required": True},
        ],
    },
]


def _read_resource_content(uri: str) -> Dict[str, Any]:
    if uri == "soko://benchmarks/frontier":
        return {
            "uri": uri,
            "mimeType": "application/json",
            "text": json.dumps(FRONTIER_ROOMS, indent=2),
        }
    if uri == "soko://methodology/verified-bar":
        text = (
            "# Local evidence and the Verified Bar\n\n"
            "Routes are checked by matching outputs from the Python specification oracle, flat bitmask oracle, "
            "and C++ engine when present, bound to the input, route, and checker hashes. "
            "Agreement is differential replay evidence under those local rules.\n"
            "Native search uses exact-state BFS with explicit time and state caps; completed goal depths "
            "support a reported lower bound. Accepted bounds use search_algorithm exact_bfs with "
            "quotient_pdb_enabled false in current builds.\n"
            "The source manifest checks committed source file hashes; the compiled binary hash is recorded "
            "as provenance. The ten-mutation audit exercises the local oracles on planted physics bugs.\n"
            "This checkout has not completed Proven-Commons Verified Bar review.\n"
        )
        return {"uri": uri, "mimeType": "text/markdown", "text": text}
    if uri == "soko://rules/puzzlescript-trilogy":
        text = (
            "# Heroes of Sokoban Trilogy Exact Mechanics\n\n"
            "- **Keys:** `U`, `D`, `L`, `R`, `A` (`Action` switches active hero in LEGEND order `1->2->3->4->5->6->1`, scanning x=0..W-1, y=0..H-1).\n"
            "- **Fighter (`F`/`1`):** Pushes arbitrarily long colinear chains of `Moveable` (`*`, inactive heroes `1..6`, monsters) if an empty cell follows.\n"
            "- **Thief (`T`/`2`):** Steps into an empty cell and pulls 1 `Moveable` immediately behind.\n"
            "- **Wizard (`W`/`3`):** Fires a warpball; swaps with first `Moveable` hit, or steps 1 empty tile if hitting `Static` (`#`, closed doors, `M`, or Part III edge).\n"
            "- **Priest (`P`/`4`):** Walks into empty cells; active `P` and inactive `4` shield themselves and orthogonal heroes from Goblin/Dragon `Dying` and Druid petrification.\n"
            "- **Bard (`B`/`5`, Part III):** 5x5 Chebyshev `Note` aura is computed at the END of the prior turn; charmed Moveables + Bard translate rigidly to fixed point (`Cancel` if Bard cannot step).\n"
            "- **Druid (`D`/`6`, Part III):** Walks into empty cells or transmutes `*`/`O` -> `#`, `#` -> `*`, unshielded inactive hero -> `#`. In Part III, `#` counts as `Weighing` on switches.\n"
        )
        return {"uri": uri, "mimeType": "text/markdown", "text": text}
    raise KeyError(f"Unknown resource URI: {uri}")


def _get_prompt_messages(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    room_id = arguments.get("room_id", "III-20")
    if name == "break_room_record":
        return {
            "description": f"Bounded route optimization workflow for room {room_id}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Apply the repository evidence workflow to shorten a route on room `{room_id}`:\n"
                            f"1. Call `soko_inspect_room` on `{room_id}` to identify exact dungeon symmetries, hero-switch chirality, and bottlenecks.\n"
                            f"2. Call `soko_verify_route` on the current baseline route to confirm `VERIFIED` differential replay.\n"
                            f"3. Call `soko_optimize_route` with bounded exact BFS; report `search.termination_reason` and `search.completed_depth` when the C++ backend ran, otherwise `backend` and `stages`.\n"
                            f"4. Report the verified route, certificate digest, keys saved, and epistemic_status from verification."
                        ),
                    },
                }
            ],
        }
    if name == "certify_room_floor":
        return {
            "description": f"Bounded exhaustive-search lower bound workflow for room {room_id}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Establish a bounded exhaustive-search lower bound for room `{room_id}`:\n"
                            f"1. Call `soko_run_planted_bug_audit` to confirm 10/10 planted mutation catches.\n"
                            f"2. Call `soko_prove_floor` on `{room_id}` and report epistemic_status, proven_floor, nodes_expanded, edge_consistency_checks, termination_reason, and completed_depth from search."
                        ),
                    },
                }
            ],
        }
    raise KeyError(f"Unknown prompt name: {name}")


def dispatch_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if name == "soko_capabilities":
        return get_capabilities()
    if name == "soko_list_rooms":
        summary = {}
        for rid, meta in FRONTIER_ROOMS.items():
            summary[rid] = {
                "part": meta["part"],
                "title": meta["title"],
                "dimensions": f"{len(meta['grid'][0])}x{len(meta['grid'])}",
                "proven_floor": meta["proven_floor"],
                "shortest_known": meta["shortest_known"],
                "frontier_record": meta["frontier_record"],
                "reference_route_len": len(meta["reference_route"]),
            }
        capabilities = get_capabilities()
        return {"cpp_engine_ready": capabilities["cpp_engine_ready"], "capabilities": capabilities, "rooms": summary}

    if name == "soko_inspect_room":
        rid, part, grid, meta = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        out = inspect_room(part, grid)
        if rid and meta:
            out["room_id"] = rid
            out["title"] = meta["title"]
            out["benchmarks"] = {
                "proven_floor": meta["proven_floor"],
                "shortest_known": meta["shortest_known"],
                "frontier_record": meta["frontier_record"],
            }
        return out

    if name == "soko_verify_route":
        rid, part, grid, _ = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        if "route" not in args:
            raise ValueError("Missing required parameter 'route'")
        res = verify_route_dual(part, grid, args["route"])
        if rid:
            res["room_id"] = rid
            res.pop("certificate_sha256", None)
            res["certificate_sha256"] = digest(res)
        return res

    if name == "soko_optimize_route":
        rid, part, grid, meta = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        seed = args.get("seed_route")
        if not seed and meta:
            seed = meta.get("prior_record_route_87") or meta.get("reference_route")
        if not seed:
            raise ValueError("Provide 'seed_route' (or specify a built-in 'room_id' with a reference route).")
        res = optimize_route_verified(
            part=part,
            grid=grid,
            seed_route=seed,
            beam_width=int(args.get("beam_width", 40000)),
            window_len=int(args.get("window_len", 14)),
            budget_sec=int(args.get("budget_sec", 35)),
        )
        if rid:
            res["room_id"] = rid
        return res

    if name == "soko_solve_room":
        rid, part, grid, _ = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        res = solve_room_verified(
            part=part,
            grid=grid,
            max_depth=int(args.get("max_depth", 120)),
            beam_width=int(args.get("beam_width", 40000)),
            budget_sec=int(args.get("budget_sec", 20)),
        )
        if rid:
            res["room_id"] = rid
        return res

    if name == "soko_prove_floor":
        rid, part, grid, _ = resolve_room_input(args.get("room_id"), args.get("part"), args.get("grid"))
        res = prove_floor_verified(
            part=part,
            grid=grid,
            max_bound=int(args.get("max_bound", 25)),
            budget_sec=int(args.get("budget_sec", 12)),
        )
        if rid:
            res["room_id"] = rid
        return res

    if name == "soko_run_planted_bug_audit":
        return run_planted_bug_audit(args.get("extra_vectors"))

    if name == "soko_verify_tcb_lock":
        return verify_tcb_lock()

    raise KeyError(f"Unknown tool: {name}")


def handle_jsonrpc_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}

    if msg_id is None:
        return None

    if method == "initialize":
        req_ver = params.get("protocolVersion", "2025-03-26")
        neg_ver = req_ver if req_ver in SUPPORTED_PROTOCOLS else "2025-03-26"
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": neg_ver,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": SERVER_INFO,
                "instructions": SERVER_INSTRUCTIONS,
            },
        }

    if method == "server/discover":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersions": SUPPORTED_PROTOCOLS,
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": SERVER_INFO,
                "instructions": SERVER_INSTRUCTIONS,
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}
        if not tool_name or not any(t["name"] == tool_name for t in TOOLS):
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": f"Unknown tool: {tool_name!r}"},
            }
        try:
            payload = dispatch_tool_call(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
                    "structuredContent": payload,
                    "isError": False,
                },
            }
        except Exception as exc:
            err_payload = {"error": str(exc), "tool": tool_name}
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(err_payload, indent=2)}],
                    "isError": True,
                },
            }

    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"resources": RESOURCES}}

    if method == "resources/read":
        uri = params.get("uri", "")
        try:
            content = _read_resource_content(uri)
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"contents": [content]}}
        except KeyError as exc:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": str(exc)}}

    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"prompts": PROMPTS}}

    if method == "prompts/get":
        pname = params.get("name", "")
        pargs = params.get("arguments") or {}
        try:
            res = _get_prompt_messages(pname, pargs)
            return {"jsonrpc": "2.0", "id": msg_id, "result": res}
        except KeyError as exc:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32602, "message": str(exc)}}

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method!r}"},
    }


def _read_next_message(stream: BinaryIO) -> Optional[Tuple[Any, bool]]:
    """Read either a newline-delimited JSON-RPC message (MCP stdio standard) or Content-Length framed message."""
    while True:
        line = stream.readline()
        if not line:
            return None
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith(b"content-length:"):
            length = int(stripped.split(b":", 1)[1].strip())
            while True:
                hdr = stream.readline()
                if not hdr or hdr in (b"\r\n", b"\n"):
                    break
            body = stream.read(length)
            return json.loads(body.decode("utf-8")), True
        return json.loads(stripped.decode("utf-8")), False


def _write_message(stream: BinaryIO, payload: Any, use_content_length: bool = False) -> None:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    if use_content_length:
        header = f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii")
        stream.write(header + encoded)
    else:
        stream.write(encoded + b"\n")
    stream.flush()


def serve_stdio() -> int:
    try:
        ensure_cpp_engine()
    except Exception as exc:
        sys.stderr.write(f"[soko-verified-mcp] C++20 engine prebuild note: {exc}\n")

    stdin_bin = sys.stdin.buffer
    stdout_bin = sys.stdout.buffer

    while True:
        try:
            item = _read_next_message(stdin_bin)
        except Exception as exc:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
            _write_message(stdout_bin, err, False)
            continue
        if item is None:
            break
        msg, use_cl = item
        if isinstance(msg, list):
            replies = [r for sub in msg if (r := handle_jsonrpc_message(sub)) is not None]
            if replies:
                _write_message(stdout_bin, replies, use_cl)
        elif isinstance(msg, dict):
            reply = handle_jsonrpc_message(msg)
            if reply is not None:
                _write_message(stdout_bin, reply, use_cl)
    return 0
