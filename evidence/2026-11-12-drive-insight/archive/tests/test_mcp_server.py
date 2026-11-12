import json
from pathlib import Path
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


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


class SokoVerifiedMcpTests(unittest.TestCase):
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
                "clientInfo": {"name": "unittest-client", "version": "1.0"},
            },
        )
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
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
            },
        )
        resources = self.client.request("resources/list")["result"]["resources"]
        self.assertEqual(len(resources), 3)
        r_bench = self.client.request("resources/read", {"uri": "soko://benchmarks/frontier"})
        bench_data = json.loads(r_bench["result"]["contents"][0]["text"])
        self.assertIn("III-20", bench_data)

        prompts = self.client.request("prompts/list")["result"]["prompts"]
        self.assertEqual(len(prompts), 2)
        p_msg = self.client.request("prompts/get", {"name": "break_room_record", "arguments": {"room_id": "III-20"}})
        self.assertIn("soko_optimize_route", p_msg["result"]["messages"][0]["content"]["text"])

    def test_03_inspect_detects_chiral_mirror_symmetry_on_iii20(self) -> None:
        res = self.client.request(
            "tools/call",
            {"name": "soko_inspect_room", "arguments": {"room_id": "III-20"}},
        )
        self.assertFalse(res["result"]["isError"])
        data = res["result"]["structuredContent"]
        self.assertTrue(data["symmetries"]["exact_mirror_y"])
        self.assertTrue(data["symmetries"]["hero_mirror_y_chirality"])
        self.assertTrue(len(data["chiral_opportunities"]) >= 1)

    def test_04_dual_oracle_verify_and_planted_bug_audit(self) -> None:
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
        self.assertEqual(ver["route_len"], 84)

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

    def test_05_solve_from_scratch_and_prove_floor(self) -> None:
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

        flr = self.client.request(
            "tools/call",
            {"name": "soko_prove_floor", "arguments": {"room_id": "III-22", "max_bound": 12, "budget_sec": 6}},
        )["result"]["structuredContent"]
        self.assertEqual(flr["proven_floor"], 9)
        self.assertTrue(flr["exact_optimum_reached"])
        self.assertGreater(flr["edge_consistency_checks"], 0)

    def test_06_generic_chiral_optimizer_reproduces_87_to_84_world_record(self) -> None:
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
        self.assertTrue(opt["differential_match"])


if __name__ == "__main__":
    unittest.main()
