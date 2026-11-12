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
