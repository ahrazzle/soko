import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from soko_mcp import engine_bridge as bridge
from soko_mcp.server import dispatch_tool_call, handle_jsonrpc_message


class CapabilityTests(unittest.TestCase):
    def test_tcb_tool_is_registered_and_missing_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bridge, "SHA256SUMS_PATH", Path(tmp) / "missing"), patch.object(bridge, "ensure_cpp_engine", return_value=None):
            response = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "soko_verify_tcb_lock", "arguments": {}}})
        self.assertFalse(response["result"]["isError"])
        result = response["result"]["structuredContent"]
        self.assertEqual(result["epistemic_status"], "TAMPERED_OR_UNLOCKED")
        self.assertFalse(result["tcb_locked"])

    def test_missing_cpp_source_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(bridge, "CPP_SRC", Path(tmp) / "missing.cpp"):
            result = dispatch_tool_call("soko_capabilities", {})
            solve = dispatch_tool_call("soko_solve_room", {"room_id": "I-1"})
        self.assertFalse(result["solve_from_scratch"]["available"])
        self.assertFalse(result["lower_bound_proving"]["available"])
        self.assertEqual(result["cpp_unavailable_reason"], "missing_cpp_source")
        self.assertEqual(result["route_optimization"]["backend"], "python_fallback_window_bfs")
        self.assertEqual(solve["epistemic_status"], "UNAVAILABLE_BACKEND")
        self.assertFalse(solve["search_performed"])
        self.assertEqual(solve["states_explored"], 0)

    def test_available_cpp_and_no_solution_is_budget_result(self):
        with patch.object(bridge, "ensure_cpp_engine", return_value=Path("engine")), patch.object(bridge, "_invoke_cpp", return_value={"solved": False, "explored": 5}):
            capabilities = bridge.get_capabilities()
            result = bridge.solve_room_verified(1, ["F.G"])
        self.assertTrue(capabilities["solve_from_scratch"]["available"])
        self.assertEqual(result["epistemic_status"], "UNSOLVED_WITHIN_BUDGET")
        self.assertTrue(result["search_performed"])
        self.assertEqual(result["states_explored"], 5)

    def test_backend_failure_is_not_budget_exhaustion(self):
        with patch.object(bridge, "ensure_cpp_engine", return_value=Path("engine")), patch.object(bridge, "_invoke_cpp", return_value=None):
            result = bridge.solve_room_verified(1, ["F.G"])
        self.assertEqual(result["epistemic_status"], "BACKEND_FAILED")
        self.assertFalse(result["search_performed"])

    def test_cli_tcb_lock_and_capabilities(self):
        for command in ("tcb-lock", "capabilities"):
            result = subprocess.run([sys.executable, "-m", "soko_mcp", command], capture_output=True, text=True, check=True)
            self.assertIsInstance(json.loads(result.stdout), dict)

    def test_existing_python_route_verification(self):
        result = dispatch_tool_call("soko_verify_route", {"room_id": "I-1", "route": "RRRRRRRRR"})
        self.assertTrue(result["valid_winning_route"])
        self.assertGreaterEqual(result["engines_count"], 2)


if __name__ == "__main__":
    unittest.main()
