import unittest
from unittest.mock import patch

from soko_mcp import engine_bridge as bridge
from soko_mcp.evidence import digest, problem_identity
from soko_mcp.server import handle_jsonrpc_message


class EvidenceBoundaryTests(unittest.TestCase):
    def test_invalid_starts_rejected_before_native_execution(self):
        cases = [(1, ["###"]), (1, ["FGG"]), (1, ["FFGG"]),
                 (1, ["F1GG"]), (1, ["F.G", "##"]), (1, ["F?G"]),
                 (True, ["F.G"]), (4, ["F.G"]), (1, ["F" + "." * 511 + "G"])]
        with patch.object(bridge, "_invoke_cpp") as native:
            for part, grid in cases:
                with self.subTest(part=part, grid=grid), self.assertRaises(ValueError):
                    bridge.verify_route_dual(part, grid, "")
            native.assert_not_called()

    def test_mcp_rejects_vacuous_and_nonstring_route(self):
        for args in ({"part": 1, "grid": ["###"], "route": ""},
                     {"part": 1, "grid": ["F.G"], "route": None}):
            response = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                               "params": {"name": "soko_verify_route", "arguments": args}})
            self.assertTrue(response["result"]["isError"])

    def test_certificate_binds_instance_route_and_checkers(self):
        result = bridge.verify_route_dual(1, ["F.G"], "rr")
        self.assertTrue(result["valid_winning_route"])
        self.assertEqual(result["route"], "RR")
        self.assertEqual(result["evidence_level"], "differential_replay")
        self.assertFalse(result["formal_proof_checked"])
        self.assertFalse(result["source_lock_asserted"])
        self.assertEqual(result["instance_sha256"], problem_identity(1, ["F.G"])["instance_sha256"])
        self.assertNotEqual(result["instance_sha256"], problem_identity(1, ["F..G"])["instance_sha256"])
        certificate_hash = result.pop("certificate_sha256")
        self.assertEqual(certificate_hash, digest(result))
        result["checker_pins"]["evidence_py_sha256"] = "changed"
        self.assertNotEqual(certificate_hash, digest(result))

    def test_python_only_replay_does_not_require_absent_cpp_artifact(self):
        pins = bridge.get_soko_checker_pins()
        pins["cpp_soko_engine_src_sha256"] = None
        pins["cpp_soko_engine_bin_sha256"] = None
        with patch.object(bridge, "_invoke_cpp", return_value=None), patch.object(bridge, "get_soko_checker_pins", return_value=pins):
            result = bridge.verify_route_dual(1, ["F.G"], "RR")
            self.assertTrue(result["valid_winning_route"])
            self.assertEqual(result["engines_count"], 2)
            self.assertFalse(bridge.verify_route_dual(1, ["F.G"], "RR", require_cpp=True)["valid_winning_route"])

    def test_mcp_certificate_includes_room_metadata(self):
        response = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                           "params": {"name": "soko_verify_route", "arguments": {
                                               "room_id": "I-1", "route": "RRRRRRRR"}}})
        result = response["result"]["structuredContent"]
        certificate_hash = result.pop("certificate_sha256")
        self.assertEqual(result["room_id"], "I-1")
        self.assertEqual(certificate_hash, digest(result))

    def test_rejected_bound_has_no_guarantee(self):
        for output in ({"proven_floor": 900},
                       {"epistemic_status": "CONJECTURE", "proven_floor": 900},
                       {"epistemic_status": "EXHAUSTIVE_LOWER_BOUND", "proven_floor": 900,
                        "exact_state_tt": True, "search_algorithm": "exact_bfs", "completed_depth": 0}):
            with self.subTest(output=output), patch.object(bridge, "_invoke_cpp", return_value=output):
                result = bridge.prove_floor_verified(1, ["F.G"], 2, 1)
                self.assertIsNone(result["guarantee"])
                self.assertEqual(result["proven_floor"], 0)  # trivial floor only
                self.assertFalse(result["exact_optimum_reached"])
