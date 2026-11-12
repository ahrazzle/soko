"""Standards-compliant Model Context Protocol (MCP) stdio JSON-RPC 2.0 server for Domain-General Formal Verification & Sokoban Eval."""
from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from . import __version__
from .analyzer import inspect_room
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
from .formal_kernel import (
    LEASE_EXAMPLE_MD,
    certify_formal_lower_bound,
    define_formal_system,
    export_formal_ledger,
    solve_formal_system,
    triage_formal_portfolio,
    verify_formal_trace,
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
    "Domain-General Formal-Systems & Verified-Bar MCP Server v0.2.0 implementing the Foundation-0 and Proven-Commons "
    "methodology: (1) Use the 6 `formal_*` tools (`formal_define_system`, `formal_verify_trace`, `formal_solve_system`, "
    "`formal_certify_lower_bound`, `formal_triage_portfolio`, `formal_export_ledger`) to model ANY discrete planning, "
    "scheduling, protocol safety, or optimization problem as an AST-sandboxed dual-checker state system with mandatory "
    "negative controls, mutation-kill gates, exact Dijkstra / Beam / Window-LNS search, and Quotient Homomorphism or "
    "Inductive Potential lower-bound proofs; (2) Use the 8 hardened `soko_*` tools for triple-oracle PuzzleScript / "
    "Sokobanteg Frontier verification, Chiral-Mirror Tube Beam optimization, and collision-free Quotient-PDB IDA* floor proving."
)

ROOM_INPUT_PROPERTIES: Dict[str, Any] = {
    "room_id": {
        "type": "string",
        "description": "Optional built-in Sokoban Eval Frontier room ID (e.g. 'I-1', 'II-22', 'III-14', 'III-14-15x7', 'III-15', 'III-20', 'III-22'). Omit when passing custom 'part' and 'grid'.",
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
    # ==================== SOKOBAN EVAL SUITE (8 TOOLS, BACKWARD-COMPATIBLE + HARDENED) ====================
    {
        "name": "soko_capabilities",
        "description": "Report available backends and missing implementations in this checkout.",
        "inputSchema": {"type": "object", "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_list_rooms",
        "title": "List Built-In Frontier Benchmark Rooms",
        "description": "List built-in Sokoban Eval Frontier rooms, proven floors, shortest-known targets, live records, and verified reference routes.",
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
        "title": "Triple-Oracle Fail-Closed Differential Route Verifier",
        "description": "Replay a U/D/L/R/A move sequence through independent PuzzleScriptOracle, FlatBitmaskOracle, and C++20 soko_engine, checking per-frame 64-bit FNV-1a trajectory digests across every step t=0..L and returning SHA-256 checker pins.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **ROOM_INPUT_PROPERTIES,
                "route": {
                    "type": "string",
                    "description": "Move string composed of U, D, L, R, and A (Action: switch active hero).",
                },
                "require_cpp": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, reject if the C++20 third oracle is unavailable (even if both Python oracles match).",
                },
            },
            "required": ["route"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_optimize_route",
        "title": "Optimize Seed Route via Windowed BFS & Chiral-Mirror Tube Beam",
        "description": "Shorten a valid seed route using Exact Sliding-Window BFS, Chiral-Mirror (X/Y/Rot180) Role-Agnostic Tube Beam Search, and Iterative Tube Refinement (reproducing III-20 87 -> 84). Triple-verifies any improvement.",
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
                    "description": "Beam width per depth layer for Chiral-Mirror and Iterative Tube Beam.",
                },
                "window_len": {
                    "type": "integer",
                    "default": 14,
                    "minimum": 8,
                    "maximum": 24,
                    "description": "Sliding window length for exact BFS subpath shortcutting.",
                },
                "budget_sec": {
                    "type": "integer",
                    "default": 35,
                    "minimum": 4,
                    "maximum": 180,
                    "description": "Total compute budget in seconds across optimization stages.",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_solve_room",
        "title": "Solve Room From Scratch via Diversified Beam Search",
        "description": "Search for a winning U/D/L/R/A move sequence from scratch without a seed route using bucket-diversified C++20 beam search plus exact window polishing and triple-oracle verification.",
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
        "title": "Certify Lower Bound via Exact-State-TT & Quotient-PDB IDA*",
        "description": "Prove a machine-checked lower bound (floor >= B) using collision-free exact-DynState transposition-table IDA*, automatic Bard+Druid Quotient-PDB construction, and runtime step-consistency assertions (h(s) <= 1 + h(s')) on every transition.",
        "inputSchema": {
            "type": "object",
            "properties": {
                **ROOM_INPUT_PROPERTIES,
                "max_bound": {"type": "integer", "default": 32, "minimum": 1, "maximum": 200},
                "budget_sec": {"type": "integer", "default": 12, "minimum": 2, "maximum": 120},
            },
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "soko_run_planted_bug_audit",
        "title": "Run 10-Mutation & Cross-Oracle Proven-Commons Audit",
        "description": "Verify 0 discrepancies between PuzzleScriptOracle and FlatBitmaskOracle across all benchmark vectors AND inject 10 realistic PuzzleScript physics bugs to confirm 10/10 mutation kills.",
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
    {
        "name": "soko_verify_tcb_lock",
        "title": "Verify Runtime SHA256SUMS Manifest & TCB Checker Pins",
        "description": "Verify runtime cryptographic SHA-256 hashes of all tracked repository files against SHA256SUMS and return SHA-256 pins for every Python and C++20 checker.",
        "inputSchema": {"type": "object", "additionalProperties": False},
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    # ==================== DOMAIN-GENERAL FORMAL-SYSTEMS SUITE (6 UNIVERSAL TOOLS) ====================
    {
        "name": "formal_define_system",
        "title": "Register & Lock Any Problem as a Dual-Checker Formal System",
        "description": "Register an arbitrary state-transition system via AST-sandboxed pure Python `spec_code` and algorithmically distinct `impl_code` (`initial_state`, `actions`, `step`, `is_goal`, optional `invariant`, `step_cost`, `project_obs`), enforcing alpha-skeleton distinctness, 100% rejection of `must_fail_controls`, 100% kill on `planted_mutations`, and bounded BFS differential parity.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "system_id": {"type": "string", "description": "Unique identifier for the formal system (e.g. 'lease_fencing_v2')."},
                "description": {"type": "string", "description": "Concise description of the modeled domain and safety/optimality properties."},
                "spec_code": {"type": "string", "description": "Declarative Python specification defining `initial_state()`, `actions(s)`, `step(s, a)`, `is_goal(s)`, and optional `invariant(s)`, `step_cost(s, a, ns)`, `project_obs(s)`."},
                "impl_code": {"type": "string", "description": "Independent zero-shared-code implementation of the same system (e.g. bit-packed int or flat tuple representation; must have a distinct AST skeleton from `spec_code`)."},
                "positive_witnesses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "trace": {"type": "array"},
                            "expect_goal": {"type": "boolean"},
                        },
                        "required": ["trace"],
                    },
                },
                "must_fail_controls": {
                    "type": "array",
                    "description": "Mandatory negative-control traces that BOTH checkers must reject as invalid/non-goal.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "trace": {"type": "array"},
                        },
                        "required": ["trace"],
                    },
                },
                "planted_mutations": {
                    "type": "array",
                    "description": "Optional defective specification variants that must be 100% killed by the witness/control/fuzz suite.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "bug_id": {"type": "string"},
                            "description": {"type": "string"},
                            "mutated_code": {"type": "string"},
                        },
                        "required": ["mutated_code"],
                    },
                },
                "bounded_fuzz_nodes": {"type": "integer", "default": 400, "minimum": 1, "maximum": 20000},
                "exact_arithmetic_only": {"type": "boolean", "default": True},
                "strict_bar": {"type": "boolean", "default": True},
                "allow_invariant_violations_in_fuzz": {
                    "type": "boolean",
                    "default": False,
                    "description": "Set true when modeling a buggy protocol whose reachable invariant violations you intend to hunt with `formal_solve_system(mode='find_invariant_violation')`.",
                },
            },
            "required": ["system_id", "spec_code", "impl_code"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "formal_verify_trace",
        "title": "Dual-Checker Premise-Explicit Trace Verifier",
        "description": "Replay a candidate action trace step-by-step across BOTH hash-locked checkers (`SPEC` and `IMPL`), verifying rolling SHA-256 transcript parity and returning a `VERIFIED` goal witness or invariant counterexample certificate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "system_id": {"type": "string"},
                "trace": {"type": "array", "description": "Ordered sequence of actions."},
                "verification_goal": {
                    "type": "string",
                    "enum": ["goal_witness", "invariant_counterexample"],
                    "default": "goal_witness",
                },
                "require_exact_terminal_goal": {"type": "boolean", "default": True},
            },
            "required": ["system_id", "trace"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "formal_solve_system",
        "title": "Solve, Model-Check, or Window-Optimize Any Formal System",
        "description": "Find a minimum-cost goal witness (`mode='reach_goal'`), find a shortest safety-bug counterexample (`mode='find_invariant_violation'`, proving global safety `PROVEN` if the complete state space exhausts cleanly!), or compress a valid seed trajectory via Sliding-Window Dijkstra LNS (`mode='optimize_trace'`).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "system_id": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["reach_goal", "find_invariant_violation", "optimize_trace"],
                    "default": "reach_goal",
                },
                "strategy": {
                    "type": "string",
                    "enum": ["exact_dijkstra", "diversified_beam"],
                    "default": "exact_dijkstra",
                },
                "max_states": {"type": "integer", "default": 50000, "minimum": 10, "maximum": 500000},
                "max_cost": {"type": "integer", "default": 1000, "minimum": 1, "maximum": 1000000},
                "beam_width": {"type": "integer", "default": 2000, "minimum": 10, "maximum": 50000},
                "bucket_cap": {"type": "integer", "default": 50, "minimum": 1, "maximum": 5000},
                "seed_trace": {"type": "array", "description": "Required when mode='optimize_trace'."},
                "window_len": {"type": "integer", "default": 8, "minimum": 2, "maximum": 30},
            },
            "required": ["system_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "formal_certify_lower_bound",
        "title": "Certify Lower Bound via Quotient Homomorphism or Inductive Potential",
        "description": "Machine-check `OPT >= claimed_lower_bound` using zero-trust finite Quotient Graph Homomorphism (`project(s)`) or Inductive Ranking Potential (`potential(s)` satisfying `V(s) <= cost(s,a,s') + V(s')` and `goal(s) => V(s) <= 0`), returning a `PROVEN` deductive certificate when the domain is closed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "system_id": {"type": "string"},
                "proof_mode": {
                    "type": "string",
                    "enum": ["quotient_homomorphism", "inductive_potential"],
                },
                "certificate_code": {
                    "type": "string",
                    "description": "Pure Python module defining `project(state)` (for quotient_homomorphism) or `potential(state)` (for inductive_potential), plus optional `enumerate_states()`.",
                },
                "claimed_lower_bound": {"type": "integer"},
                "max_concrete_states": {"type": "integer", "default": 100000, "minimum": 10, "maximum": 500000},
            },
            "required": ["system_id", "proof_mode", "certificate_code", "claimed_lower_bound"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "formal_triage_portfolio",
        "title": "Rank Open Problem Instances by Expected Verified Gain",
        "description": "Score and prioritize a portfolio of open problem instances using upper/lower bound slack, holdout upside, branching complexity, and chiral symmetry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "proven_floor": {"type": "integer"},
                            "shortest_known": {"type": "integer"},
                            "live_record": {"type": "integer"},
                            "active_cells": {"type": "integer"},
                            "eff_branching": {"type": "number"},
                            "has_chiral_symmetry": {"type": "boolean"},
                        },
                        "required": ["id", "proven_floor", "live_record"],
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "formal_export_ledger",
        "title": "Export Cryptographic Epistemic Claim & TCB Ledger",
        "description": "Export all registered dual-checker systems, `PROVEN` / `VERIFIED` certificates, SHA-256 checker pins, and validated external claims (`PROVEN`, `VERIFIED`, `KNOWN`, `CONJECTURE`).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "extra_claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "claim_id": {"type": "string"},
                            "statement": {"type": "string"},
                            "epistemic_status": {
                                "type": "string",
                                "enum": ["PROVEN", "VERIFIED", "KNOWN", "CONJECTURE"],
                            },
                            "witness_or_proof_sha256": {"type": "string"},
                        },
                        "required": ["claim_id", "statement", "epistemic_status"],
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
        "description": "How spec/code separation, triple-oracle replay, planted-bug auditing, chiral-mirror tube beam, and exact-TT Quotient-PDB IDA* map to Verified Bar v2.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "soko://benchmarks/frontier",
        "name": "Sokoban Eval Frontier Benchmark Registry",
        "description": "Built-in Frontier rooms, proven floors, shortest-known targets, and verified routes (including the 84-key III-20 record).",
        "mimeType": "application/json",
    },
    {
        "uri": "soko://rules/puzzlescript-trilogy",
        "name": "Heroes of Sokoban I, II, & III Exact Mechanics Reference",
        "description": "Exact tile legend, Action switch cycle order, hero movement laws, Bard 5x5 aura fixed-point rules, Druid transmutations, and Late phase order.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "formal://methodology/foundation0-verified-bar",
        "name": "Foundation-0 & Proven-Commons Domain-General Formal Modeling Guide",
        "description": "How to represent any planning, protocol, scheduling, or combinatorial problem as a formally verified dual-checker system.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "formal://examples/lease-fencing-spec",
        "name": "Worked Example: Distributed Lease Protocol Model Checking & Epoch Fencing Proof",
        "description": "How `formal_*` tools discover split-brain bugs in unfenced advisory leases and prove global safety under monotonic epoch fencing.",
        "mimeType": "text/markdown",
    },
]

PROMPTS: List[Dict[str, Any]] = [
    {
        "name": "break_room_record",
        "description": "Step-by-step Verified-Bar workflow for analyzing a room, auditing the oracle, and shortening a record route.",
        "arguments": [
            {"name": "room_id", "description": "Built-in room ID (e.g. 'III-20' or 'II-22') or 'custom'", "required": True},
        ],
    },
    {
        "name": "certify_room_floor",
        "description": "Step-by-step workflow for certifying a machine-checked lower bound with honest epistemic tagging.",
        "arguments": [
            {"name": "room_id", "description": "Built-in room ID or 'custom'", "required": True},
        ],
    },
    {
        "name": "model_problem_formally",
        "description": "Guided workflow to encode any arbitrary problem as a dual-checker formal system, solve it, and close LB == UB.",
        "arguments": [
            {"name": "problem_summary", "description": "Natural-language description of the target problem", "required": True},
        ],
    },
    {
        "name": "prove_protocol_safety",
        "description": "Guided workflow to hunt invariant counterexamples in a stateful protocol and prove global safety after patching.",
        "arguments": [
            {"name": "protocol_name", "description": "Name of the state machine or distributed protocol", "required": True},
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
            "# Proven-Commons Verified Bar Applied to Sokoban Eval\n\n"
            "1. **Spec / Implementation Separation:** `soko_mcp/oracle.py` is a readable declarative Python reference "
            "interpreter; `cpp/soko_engine.cpp` is a zero-allocation C++20 bit/array solver.\n"
            "2. **Dual-Oracle Differential Replay:** Every winning route must pass frame-by-frame replay in BOTH engines "
            "with identical final ASCII boards before receiving `epistemic_status = VERIFIED`.\n"
            "3. **Planted-Bug Mutation Audit:** `soko_run_planted_bug_audit` injects 10 realistic PuzzleScript physics bugs "
            "and requires 10/10 detection.\n"
            "4. **Chiral-Mirror & Iterative Tube Beam:** When `soko_inspect_room` detects symmetric walls/goals paired with "
            "asymmetric hero slots, `soko_optimize_route` reflects the seed trajectory across the symmetry axis into a "
            "role-agnostic target tube and iteratively refines shorter trajectories.\n"
            "5. **Step-Consistent Lower Bounds:** `soko_prove_floor` asserts `h(s) <= 1 + h(s')` on every expanded edge "
            "so heuristic bugs fail closed rather than silently pruning optimal branches.\n"
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
    if uri == "formal://methodology/foundation0-verified-bar":
        from . import formal_kernel as fk

        text = (fk.__doc__ or "").strip()
        return {"uri": uri, "mimeType": "text/markdown", "text": text}
    if uri == "formal://examples/lease-fencing-spec":
        return {"uri": uri, "mimeType": "text/markdown", "text": LEASE_EXAMPLE_MD}
    raise KeyError(f"Unknown resource URI: {uri}")


def _get_prompt_messages(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    room_id = arguments.get("room_id", "III-20")
    if name == "break_room_record":
        return {
            "description": f"Verified-Bar record-breaking workflow for room {room_id}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Apply the Proven-Commons Verified Bar workflow to optimize room `{room_id}`:\n"
                            f"1. Call `soko_inspect_room` on `{room_id}` to identify exact dungeon symmetries, hero-switch chirality, and bottlenecks.\n"
                            f"2. Call `soko_verify_route` on the current baseline route to confirm `VERIFIED` baseline replay.\n"
                            f"3. Call `soko_optimize_route` to run Windowed BFS + Chiral-Mirror Tube Beam + Iterative Tube Refinement.\n"
                            f"4. Report the verified route, SHA-256 digest, keys saved, and exact epistemic status (`VERIFIED` for validity, `CONJECTURE` if optimality above proven floor remains open)."
                        ),
                    },
                }
            ],
        }
    if name == "certify_room_floor":
        return {
            "description": f"Step-consistent lower-bound certification workflow for room {room_id}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Certify a machine-checked lower bound for room `{room_id}`:\n"
                            f"1. Call `soko_run_planted_bug_audit` to confirm 10/10 engine mutation catches.\n"
                            f"2. Call `soko_prove_floor` on `{room_id}` and report `proven_floor`, `nodes_expanded`, and `edge_consistency_checks`."
                        ),
                    },
                }
            ],
        }
    if name == "model_problem_formally":
        summary = arguments.get("problem_summary", "the target problem")
        return {
            "description": "Domain-general formal modeling workflow",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Model `{summary}` as a dual-checker formal system:\n"
                            "1. Call `formal_define_system` with distinct `spec_code` and `impl_code`, negative controls, and optional planted mutations.\n"
                            "2. Call `formal_solve_system` (reach_goal or find_invariant_violation) and `formal_verify_trace` on any witness.\n"
                            "3. Call `formal_certify_lower_bound` when a deductive or finite LB certificate is available; export claims with `formal_export_ledger`."
                        ),
                    },
                }
            ],
        }
    if name == "prove_protocol_safety":
        protocol = arguments.get("protocol_name", "the protocol")
        return {
            "description": "Protocol safety model-checking workflow",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Prove global safety for `{protocol}`:\n"
                            "1. Register the protocol with `formal_define_system` (set `allow_invariant_violations_in_fuzz` if hunting bugs).\n"
                            "2. Run `formal_solve_system` with mode `find_invariant_violation`; dual-verify counterexamples with `formal_verify_trace`.\n"
                            "3. After patching, re-run exhaustive search; export `PROVEN` / `VERIFIED` status via `formal_export_ledger`."
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
        res = verify_route_dual(part, grid, str(args["route"]))
        if rid:
            res["room_id"] = rid
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
            seed_route=str(seed),
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

    if name == "formal_define_system":
        return define_formal_system(
            system_id=str(args["system_id"]),
            spec_code=str(args["spec_code"]),
            impl_code=str(args["impl_code"]),
            description=str(args.get("description", "")),
            positive_witnesses=args.get("positive_witnesses"),
            must_fail_controls=args.get("must_fail_controls"),
            planted_mutations=args.get("planted_mutations"),
            bounded_fuzz_nodes=int(args.get("bounded_fuzz_nodes", 400)),
            exact_arithmetic_only=bool(args.get("exact_arithmetic_only", True)),
            strict_bar=bool(args.get("strict_bar", True)),
            allow_invariant_violations_in_fuzz=bool(args.get("allow_invariant_violations_in_fuzz", False)),
        )

    if name == "formal_verify_trace":
        return verify_formal_trace(
            system_id=str(args["system_id"]),
            trace=args["trace"],
            verification_goal=str(args.get("verification_goal", "goal_witness")),
            require_exact_terminal_goal=bool(args.get("require_exact_terminal_goal", True)),
        )

    if name == "formal_solve_system":
        return solve_formal_system(
            system_id=str(args["system_id"]),
            mode=str(args.get("mode", "reach_goal")),
            strategy=str(args.get("strategy", "exact_dijkstra")),
            max_states=int(args.get("max_states", 50000)),
            max_cost=int(args.get("max_cost", 1000)),
            beam_width=int(args.get("beam_width", 2000)),
            bucket_cap=int(args.get("bucket_cap", 50)),
            seed_trace=args.get("seed_trace"),
            window_len=int(args.get("window_len", 8)),
        )

    if name == "formal_certify_lower_bound":
        return certify_formal_lower_bound(
            system_id=str(args["system_id"]),
            proof_mode=str(args["proof_mode"]),
            certificate_code=str(args["certificate_code"]),
            claimed_lower_bound=int(args["claimed_lower_bound"]),
            max_concrete_states=int(args.get("max_concrete_states", 100000)),
        )

    if name == "formal_triage_portfolio":
        return triage_formal_portfolio(items=list(args["items"]))

    if name == "formal_export_ledger":
        return export_formal_ledger(extra_claims=args.get("extra_claims"))

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
