import json
from pathlib import Path
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from soko_mcp.engine_bridge import verify_route_dual  # noqa: E402
from soko_mcp.oracle import FRONTIER_ROOMS  # noqa: E402


class McpStdioClient:
    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "soko_mcp"],
            cwd=str(REPO_ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._next_id = 1

    def request(self, method: str, params: dict | None = None) -> dict:
        req_id = self._next_id
        self._next_id += 1
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            stderr = self.proc.stderr.read().decode("utf-8", errors="replace") if self.proc.stderr else ""
            raise RuntimeError(f"MCP server closed stdout unexpectedly. stderr:\n{stderr}")
        return json.loads(line.decode("utf-8"))

    def notify(self, method: str, params: dict | None = None) -> None:
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        assert self.proc.stdin is not None
        self.proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        self.proc.wait(timeout=10)
        if self.proc.stderr:
            self.proc.stderr.close()
        if self.proc.stdout:
            self.proc.stdout.close()


class SokoAndFormalVerifiedMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = McpStdioClient()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def test_01_initialize_and_discover(self) -> None:
        init = self.client.request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "unittest-client", "version": "2.0"},
            },
        )
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(init["result"]["serverInfo"]["version"], "0.2.0")
        self.assertIn("tools", init["result"]["capabilities"])
        self.client.notify("notifications/initialized")

        disc = self.client.request("server/discover")
        self.assertIn("2026-07-28", disc["result"]["protocolVersions"])

    def test_02_list_primitives_resources_and_prompts(self) -> None:
        tools = self.client.request("tools/list")["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertEqual(
            names,
            {
                "soko_list_rooms",
                "soko_inspect_room",
                "soko_verify_route",
                "soko_optimize_route",
                "soko_solve_room",
                "soko_prove_floor",
                "soko_run_planted_bug_audit",
                "soko_verify_tcb_lock",
                "formal_define_system",
                "formal_verify_trace",
                "formal_solve_system",
                "formal_certify_lower_bound",
                "formal_triage_portfolio",
                "formal_export_ledger",
            },
        )
        resources = self.client.request("resources/list")["result"]["resources"]
        self.assertEqual(len(resources), 5)
        r_bench = self.client.request("resources/read", {"uri": "soko://benchmarks/frontier"})
        bench_data = json.loads(r_bench["result"]["contents"][0]["text"])
        self.assertIn("III-20", bench_data)
        self.assertIn("III-14-15x7", bench_data)

        r_lease = self.client.request("resources/read", {"uri": "formal://examples/lease-fencing-spec"})
        self.assertIn("Epoch-Fenced", r_lease["result"]["contents"][0]["text"])

        prompts = self.client.request("prompts/list")["result"]["prompts"]
        self.assertEqual(len(prompts), 4)
        p_msg = self.client.request("prompts/get", {"name": "model_problem_formally", "arguments": {"problem_summary": "mutex"}})
        self.assertIn("formal_define_system", p_msg["result"]["messages"][0]["content"]["text"])

    def test_03_inspect_detects_chiral_mirror_symmetry_on_iii20(self) -> None:
        res = self.client.request(
            "tools/call",
            {"name": "soko_inspect_room", "arguments": {"room_id": "III-20"}},
        )
        self.assertFalse(res["result"]["isError"])
        data = res["result"]["structuredContent"]
        self.assertTrue(data["symmetries"]["exact_mirror_y"])
        self.assertTrue(data["symmetries"]["hero_mirror_y_chirality"])
        self.assertGreaterEqual(len(data["chiral_opportunities"]), 1)

    def test_04_triple_oracle_verify_trajectory_digest_and_audit(self) -> None:
        ver = self.client.request(
            "tools/call",
            {
                "name": "soko_verify_route",
                "arguments": {
                    "room_id": "III-20",
                    "route": "ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR",
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(ver["epistemic_status"], "VERIFIED")
        self.assertTrue(ver["valid_winning_route"])
        self.assertTrue(ver["differential_match"])
        self.assertTrue(ver["trajectory_digest_match"])
        self.assertTrue(ver["triple_oracle_checked"])
        self.assertEqual(ver["route_len"], 84)
        self.assertEqual(ver["route_sha256_12"], "eecbea96b091")

        # Verify alternate 84-key route and exact SHA-256 (`4edff1ad8c90`, fixing F-06 README typo)
        ver_alt = self.client.request(
            "tools/call",
            {
                "name": "soko_verify_route",
                "arguments": {
                    "room_id": "III-20",
                    "route": FRONTIER_ROOMS["III-20"]["alternate_route_84"],
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(ver_alt["epistemic_status"], "VERIFIED")
        self.assertEqual(ver_alt["route_sha256_12"], "4edff1ad8c90")

        # Verify both 14x7 and 15x7 III-14 benchmark variants
        for rid in ("III-14", "III-14-15x7"):
            v14 = self.client.request(
                "tools/call",
                {"name": "soko_verify_route", "arguments": {"room_id": rid, "route": FRONTIER_ROOMS[rid]["reference_route"]}},
            )["result"]["structuredContent"]
            self.assertEqual(v14["epistemic_status"], "VERIFIED")
            self.assertTrue(v14["trajectory_digest_match"])

        bad = self.client.request(
            "tools/call",
            {"name": "soko_verify_route", "arguments": {"room_id": "III-20", "route": "UUUU"}},
        )["result"]["structuredContent"]
        self.assertEqual(bad["epistemic_status"], "REJECTED")
        self.assertFalse(bad["valid_winning_route"])

        audit = self.client.request(
            "tools/call",
            {"name": "soko_run_planted_bug_audit", "arguments": {}},
        )["result"]["structuredContent"]
        self.assertEqual(audit["epistemic_status"], "VERIFIED")
        self.assertEqual(audit["planted_bugs_caught"], 10)
        self.assertEqual(audit["cross_oracle_mismatches"], 0)

    def test_05_regression_f01_f03_fail_closed_and_tcb_lock(self) -> None:
        g20 = FRONTIER_ROOMS["III-20"]["grid"]
        r84 = FRONTIER_ROOMS["III-20"]["reference_route"]

        # Without C++, Python Spec + Python FlatBitmaskOracle still give genuine 2-engine verification:
        py_dual = verify_route_dual(3, g20, r84, _skip_cpp_for_test=True)
        self.assertEqual(py_dual["epistemic_status"], "VERIFIED")
        self.assertEqual(py_dual["engines_count"], 2)
        self.assertTrue(py_dual["trajectory_digest_match"])

        # F-01 Regression: If require_cpp=True and C++ is unavailable, MUST fail closed:
        req_cpp_fail = verify_route_dual(3, g20, r84, require_cpp=True, _skip_cpp_for_test=True)
        self.assertEqual(req_cpp_fail["epistemic_status"], "REJECTED_INSUFFICIENT_ORACLES")
        self.assertFalse(req_cpp_fail["valid_winning_route"])

        # F-01 Regression: Single-oracle execution MUST NEVER emit VERIFIED:
        single_only = verify_route_dual(3, g20, r84, _skip_cpp_for_test=True, _skip_flat_for_test=True)
        self.assertEqual(single_only["epistemic_status"], "REJECTED_INSUFFICIENT_ORACLES")
        self.assertFalse(single_only["valid_winning_route"])
        self.assertFalse(single_only["differential_match"])

        # F-03 Regression: Runtime SHA256SUMS manifest and TCB pins check
        tcb = self.client.request("tools/call", {"name": "soko_verify_tcb_lock", "arguments": {}})["result"]["structuredContent"]
        self.assertEqual(tcb["epistemic_status"], "VERIFIED")
        self.assertTrue(tcb["tcb_locked"])
        self.assertIsNotNone(tcb["checker_pins"]["oracle_py_sha256"])
        self.assertIsNotNone(tcb["checker_pins"]["flat_oracle_py_sha256"])

    def test_06_solve_from_scratch_and_quotient_pdb_prove_floor_f04(self) -> None:
        custom_grid = [
            "##########",
            "#........#",
            "#F.**...G#",
            "#........#",
            "##########",
        ]
        solved = self.client.request(
            "tools/call",
            {
                "name": "soko_solve_room",
                "arguments": {"part": 1, "grid": custom_grid, "max_depth": 25, "beam_width": 4000, "budget_sec": 5},
            },
        )["result"]["structuredContent"]
        self.assertTrue(solved["solved"])
        self.assertEqual(solved["epistemic_status"], "VERIFIED")

        flr22 = self.client.request(
            "tools/call",
            {"name": "soko_prove_floor", "arguments": {"room_id": "III-22", "max_bound": 12, "budget_sec": 6}},
        )["result"]["structuredContent"]
        self.assertEqual(flr22["proven_floor"], 9)
        self.assertTrue(flr22["exact_optimum_reached"])
        self.assertTrue(flr22["exact_state_tt"])
        self.assertEqual(flr22["winning_witness"]["route_len"], 9)

        # F-04 Regression: III-14 Quotient-PDB activates automatically (raising initial bound from 9 -> >= 27 in <3s!)
        flr14 = self.client.request(
            "tools/call",
            {"name": "soko_prove_floor", "arguments": {"room_id": "III-14", "max_bound": 27, "budget_sec": 4}},
        )["result"]["structuredContent"]
        self.assertEqual(flr14["epistemic_status"], "VERIFIED")
        self.assertTrue(flr14["quotient_pdb_enabled"])
        self.assertTrue(flr14["exact_state_tt"])
        self.assertGreaterEqual(flr14["proven_floor"], 27)

    def test_07_generic_chiral_optimizer_reproduces_87_to_84_world_record(self) -> None:
        opt = self.client.request(
            "tools/call",
            {
                "name": "soko_optimize_route",
                "arguments": {
                    "room_id": "III-20",
                    "beam_width": 40000,
                    "window_len": 14,
                    "budget_sec": 35,
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(opt["epistemic_status"], "VERIFIED")
        self.assertEqual(opt["initial_len"], 87)
        self.assertLessEqual(opt["best_len"], 84)
        self.assertTrue(opt["dual_oracle_verified"])
        self.assertTrue(opt["triple_oracle_checked"])
        self.assertTrue(opt["differential_match"])

    def test_08_formal_ast_sandbox_and_alpha_skeleton_gate(self) -> None:
        # 1. Block imports inside formal specs
        bad_import = self.client.request(
            "tools/call",
            {
                "name": "formal_define_system",
                "arguments": {
                    "system_id": "bad_imp",
                    "spec_code": "import os\ndef initial_state(): return 0\ndef actions(s): return ()\ndef step(s,a): return 0\ndef is_goal(s): return False",
                    "impl_code": "def initial_state(): return 0\ndef actions(s): return (1,)\ndef step(s,a): return 0\ndef is_goal(s): return False",
                    "must_fail_controls": [{"trace": [1]}],
                },
            },
        )
        self.assertTrue(bad_import["result"]["isError"])

        # 2. Block alpha-renamed copy-pasted impl_code
        spec_src = (
            "def initial_state(): return 0\n"
            "def actions(st): return (1, 2)\n"
            "def step(st, act): return st + act if st + act <= 4 else None\n"
            "def is_goal(st): return st == 4\n"
        )
        alpha_copy = (
            "def initial_state(): return 0\n"
            "def actions(x): return (1, 2)\n"
            "def step(x, mv): return x + mv if x + mv <= 4 else None\n"
            "def is_goal(x): return x == 4\n"
        )
        dup_res = self.client.request(
            "tools/call",
            {
                "name": "formal_define_system",
                "arguments": {
                    "system_id": "dup_skel",
                    "spec_code": spec_src,
                    "impl_code": alpha_copy,
                    "must_fail_controls": [{"trace": [1]}],
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(dup_res["epistemic_status"], "REJECTED_IDENTICAL_AST_SKELETON")
        self.assertFalse(dup_res["tcb_locked"])

    def test_09_eval_domain2_team_lease_protocol_bug_hunt_and_epoch_fencing_proof(self) -> None:
        # Formalizes team `LEASE-PROTOCOL.txt` §5:
        # State tuple in SPEC: (holder, lease_epoch, s1_tok, s2_tok, store_epoch, clobbered)
        #   holder: 0=none, 1=seat1, 2=seat2
        #   lease_epoch: 0..2, s1_tok: 0..2, s2_tok: 0..2, store_epoch: 0..2, clobbered: 0/1
        unfenced_spec = """
def initial_state():
    return (0, 0, 0, 0, 0, 0)

def actions(s):
    return ("s1_acq", "s2_acq", "timeout", "s1_commit", "s2_commit")

def step(s, a):
    holder, lepoch, t1, t2, sepoch, clob = s
    if clob:
        return None
    if a == "s1_acq":
        if holder != 0 or lepoch >= 2:
            return None
        ne = lepoch + 1
        return (1, ne, ne, t2, sepoch, 0)
    if a == "s2_acq":
        if holder != 0 or lepoch >= 2:
            return None
        ne = lepoch + 1
        return (2, ne, t1, ne, sepoch, 0)
    if a == "timeout":
        if holder == 0:
            return None
        return (0, lepoch, t1, t2, sepoch, 0)
    if a == "s1_commit":
        if t1 == 0:
            return None
        # Unfenced bug: writer commits without checking t1 == sepoch / t1 >= lepoch!
        bad = 1 if t1 < sepoch else 0
        return (holder, lepoch, 0, t2, max(sepoch, t1), bad)
    if a == "s2_commit":
        if t2 == 0:
            return None
        bad = 1 if t2 < sepoch else 0
        return (holder, lepoch, t1, 0, max(sepoch, t2), bad)
    return None

def is_goal(s):
    return s[4] == 2 and s[5] == 0

def invariant(s):
    return (s[5] == 0, "stale_lease_clobbered_newer_commit" if s[5] else "ok")

def project_obs(s):
    return s
"""
        # Independent IMPL using bit-packed 18-bit integer state!
        unfenced_impl = """
def _pack(h, le, t1, t2, se, cl):
    return h | (le << 3) | (t1 << 6) | (t2 << 9) | (se << 12) | (cl << 15)

def initial_state():
    return 0

def project_obs(x):
    return (x & 7, (x >> 3) & 7, (x >> 6) & 7, (x >> 9) & 7, (x >> 12) & 7, (x >> 15) & 1)

def actions(x):
    return ("s1_acq", "s2_acq", "timeout", "s1_commit", "s2_commit")

def step(x, a):
    h, le, t1, t2, se, cl = project_obs(x)
    if cl == 1:
        return None
    if a == "s1_acq" and h == 0 and le < 2:
        return _pack(1, le + 1, le + 1, t2, se, 0)
    if a == "s2_acq" and h == 0 and le < 2:
        return _pack(2, le + 1, t1, le + 1, se, 0)
    if a == "timeout" and h != 0:
        return _pack(0, le, t1, t2, se, 0)
    if a == "s1_commit" and t1 > 0:
        ns = se if se >= t1 else t1
        return _pack(h, le, 0, t2, ns, 1 if t1 < se else 0)
    if a == "s2_commit" and t2 > 0:
        ns = se if se >= t2 else t2
        return _pack(h, le, t1, 0, ns, 1 if t2 < se else 0)
    return None

def is_goal(x):
    return ((x >> 12) & 7) == 2 and ((x >> 15) & 1) == 0

def invariant(x):
    bad = (x >> 15) & 1
    return (bad == 0, "stale_lease_clobbered_newer_commit" if bad else "ok")
"""
        reg_unfenced = self.client.request(
            "tools/call",
            {
                "name": "formal_define_system",
                "arguments": {
                    "system_id": "lease_unfenced_v1",
                    "description": "Advisory Drive lease without monotonic epoch fencing",
                    "spec_code": unfenced_spec,
                    "impl_code": unfenced_impl,
                    "positive_witnesses": [
                        {"name": "clean_handoff", "trace": ["s1_acq", "s1_commit", "timeout", "s2_acq", "s2_commit"], "expect_goal": True}
                    ],
                    "must_fail_controls": [
                        {"name": "unheld_commit", "trace": ["s1_commit"]},
                        {"name": "double_acquire", "trace": ["s1_acq", "s2_acq"]},
                    ],
                    "allow_invariant_violations_in_fuzz": True,
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(reg_unfenced["epistemic_status"], "VERIFIED")
        self.assertTrue(reg_unfenced["tcb_locked"])

        # Discover minimal split-brain counterexample automatically!
        bug = self.client.request(
            "tools/call",
            {
                "name": "formal_solve_system",
                "arguments": {"system_id": "lease_unfenced_v1", "mode": "find_invariant_violation", "strategy": "exact_dijkstra"},
            },
        )["result"]["structuredContent"]
        self.assertEqual(bug["epistemic_status"], "VERIFIED")
        self.assertTrue(bug["counterexample_found"])
        self.assertEqual(bug["steps"], 5)
        # Now patch with monotonic epoch fencing (`t >= lepoch` & `t > sepoch` required to commit!) and PROVE global safety!
        fenced_spec = unfenced_spec.replace(
            "bad = 1 if t1 < sepoch else 0\n        return (holder, lepoch, 0, t2, max(sepoch, t1), bad)",
            "if t1 != lepoch or t1 <= sepoch:\n            return None\n        return (holder, lepoch, 0, t2, t1, 0)",
        ).replace(
            "bad = 1 if t2 < sepoch else 0\n        return (holder, lepoch, t1, 0, max(sepoch, t2), bad)",
            "if t2 != lepoch or t2 <= sepoch:\n            return None\n        return (holder, lepoch, t1, 0, t2, 0)",
        )
        fenced_impl = unfenced_impl.replace(
            "if a == \"s1_commit\" and t1 > 0:\n        ns = se if se >= t1 else t1\n        return _pack(h, le, 0, t2, ns, 1 if t1 < se else 0)",
            "if a == \"s1_commit\" and t1 > 0 and t1 == le and t1 > se:\n        return _pack(h, le, 0, t2, t1, 0)",
        ).replace(
            "if a == \"s2_commit\" and t2 > 0:\n        ns = se if se >= t2 else t2\n        return _pack(h, le, t1, 0, ns, 1 if t2 < se else 0)",
            "if a == \"s2_commit\" and t2 > 0 and t2 == le and t2 > se:\n        return _pack(h, le, t1, 0, t2, 0)",
        )

        reg_fenced = self.client.request(
            "tools/call",
            {
                "name": "formal_define_system",
                "arguments": {
                    "system_id": "lease_epoch_fenced_v2",
                    "description": "Epoch-fenced lease protocol (§5 resolution)",
                    "spec_code": fenced_spec,
                    "impl_code": fenced_impl,
                    "positive_witnesses": [
                        {"name": "clean_fenced_handoff", "trace": ["s1_acq", "s1_commit", "timeout", "s2_acq", "s2_commit"], "expect_goal": True}
                    ],
                    "must_fail_controls": [
                        {"name": "stale_s1_blocked", "trace": bug["trace"]},
                    ],
                    "planted_mutations": [
                        {"bug_id": "DROP_EPOCH_FENCE", "description": "Re-introduces unfenced stale commit", "mutated_code": unfenced_spec},
                    ],
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(reg_fenced["epistemic_status"], "VERIFIED")
        self.assertEqual(reg_fenced["planted_mutations"]["killed"], 1)

        safety_proof = self.client.request(
            "tools/call",
            {
                "name": "formal_solve_system",
                "arguments": {"system_id": "lease_epoch_fenced_v2", "mode": "find_invariant_violation", "strategy": "exact_dijkstra"},
            },
        )["result"]["structuredContent"]
        self.assertEqual(safety_proof["epistemic_status"], "PROVEN")
        self.assertEqual(safety_proof["certificate_kind"], "EXHAUSTIVE_GLOBAL_SAFETY_PROOF")
        self.assertFalse(safety_proof["counterexample_found"])
        self.assertTrue(safety_proof["complete_state_space_exhausted"])

    def test_10_eval_domain3_weighted_scheduling_lns_and_quotient_optimality_closure(self) -> None:
        # 4 jobs (J0..J3) on 2 modes (Mode 0 = GPU-A, Mode 1 = GPU-B) with switchover setup cost + precedence (J0 before J2, J1 before J3):
        # Job run costs:
        #   J0: mode0=3, mode1=7
        #   J1: mode0=7, mode1=3
        #   J2: mode0=4, mode1=8  (requires J0 done)
        #   J3: mode0=8, mode1=4  (requires J1 done)
        # Switchover cost between mode 0 <-> mode 1 = 5 (initial mode = 0).
        # Optimal schedule: run J0 (3) + J2 (4) on mode 0, switch 0->1 (5), run J1 (3) + J3 (4) on mode 1 => total = 3+4+5+3+4 = 19!
        sched_spec = """
def initial_state():
    return (frozenset(), 0)

def actions(s):
    done, mode = s
    acts = [("switch", 1 - mode)]
    for j in (0, 1, 2, 3):
        if j not in done:
            acts.append(("run", j))
    return tuple(acts)

def step(s, a):
    done, mode = s
    kind, val = a
    if kind == "switch":
        if val != 1 - mode:
            return None
        return (done, val)
    if kind == "run":
        if val in done:
            return None
        if val == 2 and 0 not in done:
            return None
        if val == 3 and 1 not in done:
            return None
        return (done | frozenset((val,)), mode)
    return None

def step_cost(s, a, ns):
    _, mode = s
    kind, val = a
    if kind == "switch":
        return 5
    table = ((3, 7), (7, 3), (4, 8), (8, 4))
    return table[val][mode]

def is_goal(s):
    return len(s[0]) == 4

def project_obs(s):
    mask = 0
    for j in s[0]:
        mask |= (1 << j)
    return (mask, s[1])
"""
        sched_impl = """
COSTS_M0 = (3, 7, 4, 8)
COSTS_M1 = (7, 3, 8, 4)

def initial_state():
    return 0

def project_obs(x):
    return (x & 15, (x >> 4) & 1)

def actions(x):
    mask = x & 15
    mode = (x >> 4) & 1
    out = [("switch", 1 - mode)]
    for j in range(4):
        if not ((mask >> j) & 1):
            out.append(("run", j))
    return tuple(out)

def step(x, a):
    mask = x & 15
    mode = (x >> 4) & 1
    k, v = a
    if k == "switch":
        return mask | ((1 - mode) << 4) if v == 1 - mode else None
    if k == "run":
        if (mask >> v) & 1:
            return None
        if v == 2 and not (mask & 1):
            return None
        if v == 3 and not (mask & 2):
            return None
        return (mask | (1 << v)) | (mode << 4)
    return None

def step_cost(x, a, nx):
    mode = (x >> 4) & 1
    if a[0] == "switch":
        return 5
    j = a[1]
    return COSTS_M0[j] if mode == 0 else COSTS_M1[j]

def is_goal(x):
    return (x & 15) == 15
"""
        mut_no_prec = sched_spec.replace("if val == 2 and 0 not in done:\n            return None", "pass")
        mut_free_switch = sched_spec.replace("return 5", "return 1")

        suboptimal_seed = [
            ["run", 0],
            ["switch", 1],
            ["run", 1],
            ["switch", 0],
            ["run", 2],
            ["switch", 1],
            ["run", 3],
        ]  # cost = 3 + 5 + 3 + 5 + 4 + 5 + 4 = 29

        reg_sched = self.client.request(
            "tools/call",
            {
                "name": "formal_define_system",
                "arguments": {
                    "system_id": "weighted_job_routing_v1",
                    "description": "4-job 2-cluster setup-cost scheduling with precedence",
                    "spec_code": sched_spec,
                    "impl_code": sched_impl,
                    "positive_witnesses": [{"name": "ping_pong_29", "trace": suboptimal_seed, "expect_goal": True}],
                    "must_fail_controls": [
                        {"name": "precedence_violation_j2", "trace": [["run", 2]]},
                        {"name": "incomplete_schedule", "trace": [["run", 0], ["run", 2]]},
                    ],
                    "planted_mutations": [
                        {"bug_id": "DROP_J0_J2_PRECEDENCE", "mutated_code": mut_no_prec},
                        {"bug_id": "UNDERPRICE_SWITCHOVER", "mutated_code": mut_free_switch},
                    ],
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(reg_sched["epistemic_status"], "VERIFIED")
        self.assertEqual(reg_sched["planted_mutations"]["killed"], 2)

        # 1. Compress suboptimal 29-cost seed down to optimal 19 via Window LNS!
        opt_lns = self.client.request(
            "tools/call",
            {
                "name": "formal_solve_system",
                "arguments": {
                    "system_id": "weighted_job_routing_v1",
                    "mode": "optimize_trace",
                    "seed_trace": suboptimal_seed,
                    "window_len": 8,
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(opt_lns["epistemic_status"], "VERIFIED")
        self.assertEqual(opt_lns["initial_cost"], 29)
        self.assertEqual(opt_lns["best_cost"], 19)

        # 2. Certify LB >= 19 via Quotient Homomorphism -> closes LB == UB == 19 (`PROVEN`)!
        quotient_cert = """
def project(s):
    done, mode = s
    # Quotient forgets order and collapses {0,2} count + {1,3} count + mode (3 x 3 x 2 = 18 states vs 32 concrete)
    a_cnt = (1 if 0 in done else 0) + (1 if 2 in done else 0)
    b_cnt = (1 if 1 in done else 0) + (1 if 3 in done else 0)
    return (a_cnt, b_cnt, mode)
"""
        lb_q = self.client.request(
            "tools/call",
            {
                "name": "formal_certify_lower_bound",
                "arguments": {
                    "system_id": "weighted_job_routing_v1",
                    "proof_mode": "quotient_homomorphism",
                    "certificate_code": quotient_cert,
                    "claimed_lower_bound": 19,
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(lb_q["epistemic_status"], "PROVEN")
        self.assertEqual(lb_q["certified_lower_bound"], 19)

        # 3. Verify that an exaggerated/inadmissible inductive potential fails closed!
        bad_pot = """
def potential(s):
    done, _ = s
    return (4 - len(done)) * 10
"""
        lb_bad = self.client.request(
            "tools/call",
            {
                "name": "formal_certify_lower_bound",
                "arguments": {
                    "system_id": "weighted_job_routing_v1",
                    "proof_mode": "inductive_potential",
                    "certificate_code": bad_pot,
                    "claimed_lower_bound": 25,
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(lb_bad["epistemic_status"], "REJECTED_STEP_CONSISTENCY_VIOLATION")

        # 4. Triage portfolio & export cryptographic ledger
        triage = self.client.request(
            "tools/call",
            {
                "name": "formal_triage_portfolio",
                "arguments": {
                    "items": [
                        {"id": "III-21", "proven_floor": 268, "shortest_known": 316, "live_record": 379, "active_cells": 200, "has_chiral_symmetry": False},
                        {"id": "I-1", "proven_floor": 8, "shortest_known": 8, "live_record": 8, "active_cells": 10},
                    ]
                },
            },
        )["result"]["structuredContent"]
        self.assertEqual(triage["closed_optimal_count"], 1)
        self.assertEqual(triage["ranked_portfolio"][0]["id"], "III-21")

        ledger = self.client.request(
            "tools/call",
            {"name": "formal_export_ledger", "arguments": {}},
        )["result"]["structuredContent"]
        self.assertGreaterEqual(ledger["registered_systems_count"], 3)


if __name__ == "__main__":
    unittest.main()
