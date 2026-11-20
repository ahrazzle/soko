"""Every floor the README states must be reproduced here or backed by an in-repo ledger.

Review 5907250524 found README floors (76 on III-20, 44 on III-14) that this
repository's prover cannot reproduce. This test lists each floor claim the README
makes, by its exact text, and either reruns it or checks its ledger:

- reproduce: rerun prove_floor_verified with a state-capped search. The cap makes
  the result independent of machine speed; the budget is only a safety net.
- ledger: a slow standalone run recorded in an evidence ledger. The ledger must
  exist, give its reproduction command, and be linked from the README.

Any other floor-like phrase in the README fails the scan, so a new claim cannot be
added without registering it here.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from soko_mcp.engine_bridge import ensure_cpp_engine, prove_floor_verified, resolve_room_input

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
LEDGER_38 = "evidence/2026-11-13-iii14-15x7-floor38-ledger/README.md"

# (room, max_bound, budget_sec) -> the floor that run must reach; "exact" also requires VERIFIED.
RUNS = {
    "iii20": ("III-20", 75, 240),
    "iii14_fixture": ("fixture:III-14", 43, 300),
    "i1_fixture": ("fixture:I-1", 12, 60),
    "iii22": ("III-22", 12, 60),
    "i1": ("I-1", 10, 60),
}

CLAIMS = [
    {"text": "raising the generic MCP lower bound on `III-20` from `25` (`v0.3.0`) to **`>= 48`**",
     "run": "iii20", "floor": 48},
    {"text": "giving a sound lower bound **`>= 34`** on the 14x7 `III-14` fixture",
     "run": "iii14_fixture", "floor": 34},
    {"text": "The 14x7 fixture still has the standalone-prover lower bound `>= 34`",
     "run": "iii14_fixture", "floor": 34},
    {"text": "to **`>= 33` in ~6.6s**", "run": "iii14_fixture", "floor": 33},
    {"text": "15x7 catalog board `III-14`, floor of 38 or more", "ledger": LEDGER_38},
    {"text": "A floor of 38 or more was reproduced by grk-proof", "ledger": LEDGER_38},
    {"text": "On the 15x7 catalog board, a floor of 38 or more was reproduced by grk-proof", "ledger": LEDGER_38},
    {"text": "Proven optimal on the legacy `fixture:I-1` board", "run": "i1_fixture", "floor": 9, "exact": True},
    {"text": "and on III-22: `RRRRRRRRR`", "run": "iii22", "floor": 9, "exact": True},
    {"text": "with record and floor 8", "run": "i1", "floor": 8, "exact": True},
]

# Phrases that state a floor. Only lines that talk about floors or bounds are scanned.
FLOOR_PHRASES = re.compile(
    r">=\s*\**`?\s*\d+|floor of \d+|floor \d+|proven (?:minimum|optimal|floor)|closed optimal",
    re.IGNORECASE,
)
CONTEXT = re.compile(r"floor|lower bound|proven|minimum|optimal", re.IGNORECASE)


class ReadmeFloorClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = README.read_text(encoding="utf-8")

    def test_every_registered_claim_is_in_the_readme(self) -> None:
        for claim in CLAIMS:
            with self.subTest(claim=claim["text"]):
                self.assertIn(claim["text"], self.text)

    def test_readme_states_no_unregistered_floor(self) -> None:
        covered = []
        for claim in CLAIMS:
            start = self.text.find(claim["text"])
            while start >= 0:
                covered.append((start, start + len(claim["text"])))
                start = self.text.find(claim["text"], start + 1)
        offset = 0
        for lineno, line in enumerate(self.text.splitlines(keepends=True), 1):
            if CONTEXT.search(line):
                for m in FLOOR_PHRASES.finditer(line):
                    a, b = offset + m.start(), offset + m.end()
                    with self.subTest(line=lineno, phrase=m.group(0)):
                        self.assertTrue(
                            any(lo <= a and b <= hi for lo, hi in covered),
                            f"README line {lineno} states a floor ({m.group(0)!r}) that tests/test_readme_floors.py "
                            "does not reproduce or tie to a ledger",
                        )
            offset += len(line)

    def test_ledger_claims_cite_an_existing_ledger_with_a_command(self) -> None:
        for claim in CLAIMS:
            if "ledger" not in claim:
                continue
            with self.subTest(claim=claim["text"]):
                ledger = ROOT / claim["ledger"]
                self.assertTrue(ledger.is_file())
                self.assertIn(claim["ledger"], self.text)
                self.assertIn("Reproduction Commands", ledger.read_text(encoding="utf-8"))

    def test_reproducible_claims_are_reproduced(self) -> None:
        if ensure_cpp_engine() is None:
            raise unittest.SkipTest("C++20 compiler unavailable")
        results = {}
        for key, (room, max_bound, budget) in RUNS.items():
            _, part, grid, _ = resolve_room_input(room_id=room)
            results[key] = prove_floor_verified(part, grid, max_bound=max_bound, budget_sec=budget)
        for claim in CLAIMS:
            if "run" not in claim:
                continue
            out = results[claim["run"]]
            with self.subTest(claim=claim["text"]):
                self.assertFalse(out.get("timed_out"), "the safety budget ran out; the state cap did not decide")
                if claim.get("exact"):
                    self.assertEqual(out["epistemic_status"], "VERIFIED")
                    self.assertEqual(out["proven_floor"], claim["floor"])
                else:
                    self.assertIn(out["epistemic_status"], ("VERIFIED", "LOWER_BOUND_UNWITNESSED"))
                    self.assertGreaterEqual(out["proven_floor"], claim["floor"])


if __name__ == "__main__":
    unittest.main()
