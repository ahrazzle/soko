"""Corpus parity and minimized original-rule regressions.

The synthetic cases were replayed in the original compiled rules with only
LEVELS replaced; they exercise ordering beyond the isolated I-22 corridors.
"""
import os
from pathlib import Path
import unittest

from soko_mcp.catalog import get_room, load_catalog
from soko_mcp.evidence import validate_room
from soko_mcp.flat_oracle import FlatBitmaskOracle, replay_flat_oracle
from soko_mcp.oracle import PuzzleScriptOracle, replay_oracle


class TrilogyMechanicsTests(unittest.TestCase):
    def assert_engines(self, part, grid, route, expected):
        readable = PuzzleScriptOracle(part, grid)
        flat = FlatBitmaskOracle(part, grid)
        for key in route:
            self.assertEqual(readable.step(key), flat.step(key))
        self.assertEqual(readable.render_ascii(), "\n".join(expected))
        self.assertEqual(flat.render_ascii(), readable.render_ascii())
        self.assertEqual(flat.fold_digest(0), readable.fold_canonical_digest(0))
        # Import lazily so Python-only installations retain independent checks.
        from soko_mcp.engine_bridge import _invoke_cpp, ensure_cpp_engine
        if ensure_cpp_engine() is not None:
            native = _invoke_cpp("verify", part, grid, 0, 0, 0, route)
            self.assertEqual(native["final_ascii"], readable.render_ascii())
            self.assertEqual(native["traj_fnv64"], replay_oracle(part, grid, route)["traj_fnv64"])

    def test_all_original_baselines_win_and_agree(self):
        from soko_mcp.engine_bridge import _invoke_cpp, ensure_cpp_engine
        native_available = ensure_cpp_engine() is not None
        for room_id, room in load_catalog().items():
            with self.subTest(room=room_id):
                args = room["part"], room["grid"], room["reference_route"]
                readable = replay_oracle(*args)
                flat = replay_flat_oracle(*args)
                self.assertTrue(readable["exact_win"])
                self.assertTrue(flat["exact_win"])
                self.assertEqual(readable["traj_fnv64"], flat["traj_fnv64"])
                if native_available:
                    native = _invoke_cpp("verify", args[0], args[1], 0, 0, 0, args[2])
                    self.assertTrue(native["exact_win"])
                    self.assertEqual(readable["traj_fnv64"], native["traj_fnv64"])

    def test_multi_active_original_room_and_identity_boundary(self):
        room = get_room("I-22")
        validate_room(1, room["grid"])
        self.assertTrue(replay_oracle(1, room["grid"], "R" * 10)["exact_win"])
        for grid in (["FFTGGG"], ["F1GG"], ["12GG"]):
            with self.assertRaises(ValueError):
                validate_room(1, grid)

    def test_active_followers_move_simultaneously(self):
        grid = ["#########", "#FTW...G#", "#GG.....#", "#########"]
        self.assert_engines(1, grid, "R", ["#########", "#.FTW..G#", "#GG.....#", "#########"])
        self.assert_engines(1, grid, "RL", grid)

    def test_action_uses_original_rule_order_for_each_initial_player(self):
        grid = ["#########", "#F2W...G#", "#GG.....#", "#########"]
        self.assert_engines(1, grid, "A", ["#########", "#FT3...G#", "#GG.....#", "#########"])
        self.assert_engines(1, grid, "AA", grid)

    def test_door_crush_opens_monster_gate_in_same_late_phase(self):
        grid = ["#########", "#F{O[MG.#", "#P.....G#", "#########"]
        self.assert_engines(2, grid, "RR", ["#########", "#.{F[.G.#", "#..P...G#", "#########"])

    def test_bard_overwrites_active_hero_before_that_cells_movement(self):
        grid = ["#######", "#.FB.G#", "#....G#", "#######"]
        self.assert_engines(3, grid, "L", ["#######", "#B...G#", "#....G#", "#######"])

    def test_petrified_active_bard_keeps_movement_but_stops_playing(self):
        grid = ["#######", "#D.*.G#", "#BG...#", "#.....#", "#######"]
        self.assert_engines(3, grid, "D", ["#######", "#D.*.G#", "#.G...#", "##....#", "#######"])

    def test_bard_note_moves_into_active_hero_before_regular_movement(self):
        grid = ["########", "#*PB..G#", "#.....G#", "########"]
        self.assert_engines(3, grid, "R", ["########", "#..*B.G#", "#.....G#", "########"])

    def test_part_two_action_reactivation_on_an_initial_player_cell_cancels(self):
        grid = ["#########", "#F2W...G#", "#GG.....#", "#########"]
        self.assert_engines(2, grid, "A", grid)

    def test_part_two_wizard_leaves_inactive_hero_without_canceling(self):
        grid = ["#########", "#F.....G#", "#W.2...G#", "#......G#", "#########"]
        self.assert_engines(2, grid, "R", ["#########", "#.F....G#", "#2.W...G#", "#......G#", "#########"])

    def test_part_two_one_blocked_player_cancels_every_player(self):
        grid = ["#########", "#F#....G#", "#P.....G#", "#########"]
        self.assert_engines(2, grid, "R", grid)


@unittest.skipUnless(os.environ.get("SOKO_ORIGINAL_HTML_PART1"), "set SOKO_ORIGINAL_HTML_PART1 for original-browser checks")
class MultiActiveOriginalTests(unittest.TestCase):
    def test_original_corridor_movement_and_action_frames(self):
        from soko_mcp.original import replay
        room = get_room("I-22")
        for route in ("R" * 10, "ARRAALLRR", "ULRRA"):
            with self.subTest(route=route):
                original = replay(1, 22, route, html=Path(os.environ["SOKO_ORIGINAL_HTML_PART1"]), include_frames=True)
                readable = PuzzleScriptOracle(1, room["grid"])
                flat = FlatBitmaskOracle(1, room["grid"])
                ids, stride, height, width = original["object_ids"], original["stride"], original["height"], original["width"]
                names = {"fighter": "F", "thief": "T", "wizard": "W", "sfighter": "1", "sthief": "2", "swizard": "3", "wall": "#"}
                for frame in original["frames"]:
                    readable.step(frame["key"])
                    flat.step(frame["key"])
                    rows = []
                    for y in range(height):
                        row = ""
                        for x in range(width):
                            words = frame["objects"][(x * height + y) * stride: (x * height + y + 1) * stride]
                            hero = next((symbol for name, symbol in names.items() if words[ids[name] >> 5] & (1 << (ids[name] & 31))), None)
                            row += hero or ("G" if room["grid"][y][x] == "G" else ".")
                        rows.append(row)
                    self.assertEqual(readable.render_ascii(), "\n".join(rows), frame["step"])
                    self.assertEqual(flat.render_ascii(), readable.render_ascii(), frame["step"])
