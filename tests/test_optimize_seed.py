"""soko_optimize_route seeds the III-20 generator control from the prior 87-key record."""
import unittest
from unittest.mock import patch

from soko_mcp import server
from soko_mcp.oracle import FRONTIER_ROOMS


class OptimizeSeedTests(unittest.TestCase):
    def seed_for(self, arguments):
        captured = {}

        def fake_optimize(**kwargs):
            captured.update(kwargs)
            return {"epistemic_status": "VERIFIED"}

        with patch.object(server, "optimize_route_verified", side_effect=fake_optimize):
            response = server.handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                                      "params": {"name": "soko_optimize_route", "arguments": arguments}})
        self.assertFalse(response["result"].get("isError"), response)
        return captured["seed_route"]

    def test_room_id_and_explicit_board_both_seed_from_87(self):
        meta = FRONTIER_ROOMS["III-20"]
        prior = meta["prior_record_route_87"]
        self.assertEqual(len(prior), 87)
        self.assertEqual(self.seed_for({"room_id": "III-20"}), prior)
        self.assertEqual(self.seed_for({"part": meta["part"], "grid": meta["grid"]}), prior)

    def test_explicit_seed_wins(self):
        self.assertEqual(self.seed_for({"room_id": "III-20", "seed_route": "RRRR"}), "RRRR")



class OptimizeSeedRejectionTests(unittest.TestCase):
    def test_rejected_seed_error_names_the_verifier_status(self):
        from soko_mcp import engine_bridge as eb
        meta = FRONTIER_ROOMS["III-20"]
        unlocked = {"tcb_locked": False}
        with patch.object(eb, "_runtime_tcb_locked", return_value=(False, unlocked)):
            with self.assertRaises(ValueError) as ctx:
                eb.optimize_route_verified(meta["part"], meta["grid"], meta["reference_route"], budget_sec=0)
        message = str(ctx.exception)
        self.assertIn("epistemic_status=REJECTED_TCB_UNLOCKED", message)
        self.assertIn("exact_win=True", message)


if __name__ == "__main__":
    unittest.main()
