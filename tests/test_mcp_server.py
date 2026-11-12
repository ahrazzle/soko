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
        self._id = 1

    def request(self, method: str, params: dict | None = None) -> dict:
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        self._id += 1
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
        self.proc.stdin.flush()
        return json.loads(self.proc.stdout.readline().decode("utf-8"))

    def close(self) -> None:
        self.proc.stdin.close()
        self.proc.wait(timeout=10)
        self.proc.stdout.close()
        self.proc.stderr.close()


class SokoVerifiedMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = McpStdioClient()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def test_01_initialize_and_primitives(self) -> None:
        init = self.client.request("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}})
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
        tools = {t["name"] for t in self.client.request("tools/list")["result"]["tools"]}
        self.assertIn("soko_optimize_route", tools)
        self.assertEqual(len(tools), 7)
        res = self.client.request("resources/read", {"uri": "soko://benchmarks/frontier"})
        self.assertIn("III-20", json.loads(res["result"]["contents"][0]["text"]))

    def test_02_inspect_verify_and_planted_bug_audit(self) -> None:
        ins = self.client.request("tools/call", {"name": "soko_inspect_room", "arguments": {"room_id": "III-20"}})
        self.assertTrue(ins["result"]["structuredContent"]["symmetries"]["exact_mirror_y"])
        ver = self.client.request("tools/call", {"name": "soko_verify_route", "arguments": {
            "room_id": "III-20",
            "route": "ADDDRRADAAADRULARADAAADDLLALAAAARRRRUULAAUALLRADRRRRADRULRURRRRRARRUURURAURRRDDRAUUR",
        }})["result"]["structuredContent"]
        self.assertEqual(ver["epistemic_status"], "VERIFIED")
        self.assertEqual(ver["route_len"], 84)
        aud = self.client.request("tools/call", {"name": "soko_run_planted_bug_audit", "arguments": {}})["result"]["structuredContent"]
        self.assertEqual(aud["planted_bugs_caught"], 10)


if __name__ == "__main__":
    unittest.main()
