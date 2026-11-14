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


if __name__ == "__main__":
    unittest.main()
