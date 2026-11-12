import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("replay_instance", ROOT / "experiments/frontier_mac/replay_instance.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstanceEvidenceTests(unittest.TestCase):
    def instance(self):
        return {"part": 1, "grid": ["#####", "#F.G#", "#####"], "route": "RR", "record_keys": 3}

    def test_binds_problem_and_route_and_labels_scope(self):
        cert = module.replay(self.instance())
        self.assertTrue(cert["valid_winning_route"])
        self.assertTrue(cert["beats_observed_record"])
        self.assertEqual(cert["evidence_level"], "differential_replay")
        self.assertFalse(cert["formal_proof_checked"])
        self.assertFalse(cert["external_spec_pinned"])
        self.assertEqual(len(cert["certificate_sha256"]), 64)
        for key in ("replay_adapter_sha256", "engine_bridge_sha256"):
            self.assertEqual(len(cert["acceptance_checker_pins"][key]), 64)

    def test_instance_hash_changes_with_grid(self):
        first = module.replay(self.instance())
        second = self.instance()
        second["grid"] = ["######", "#F..G#", "######"]
        second["route"] = "RRR"
        cert = module.replay(second)
        self.assertNotEqual(first["instance_sha256"], cert["instance_sha256"])
        self.assertNotEqual(first["route_sha256"], cert["route_sha256"])

    def test_attribution_does_not_change_problem_identity(self):
        first = module.replay(self.instance())
        second = self.instance()
        second["source_url"] = "https://example.invalid/attribution"
        cert = module.replay(second)
        self.assertEqual(first["instance_sha256"], cert["instance_sha256"])
        self.assertNotEqual(first["certificate_sha256"], cert["certificate_sha256"])

    def test_route_at_record_is_not_a_new_record(self):
        instance = self.instance()
        instance["record_keys"] = 2
        self.assertFalse(module.replay(instance)["beats_observed_record"])

    def test_incomplete_route_is_not_a_win(self):
        instance = self.instance()
        instance["route"] = "R"
        result = module.replay(instance)
        self.assertFalse(result["valid_winning_route"])
        self.assertFalse(result["beats_observed_record"])

    def test_rejects_noncanonical_starting_rooms(self):
        for grid in (["..."], ["G.."], ["F.."], ["FFGG"], ["F1GG"], ["F2G"], ["12GG"]):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                module.replay({"part": 1, "grid": grid, "route": ""})

    def test_rejects_malformed_inputs(self):
        for change in ({"part": True}, {"grid": ["?F.G"]}, {"grid": ["##", "#"]}, {"route": "R R"}, {"route": "rr"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.replay(self.instance() | change)


if __name__ == "__main__":
    unittest.main()


class SearchFailureEvidenceTests(unittest.TestCase):
    def test_compiler_failure_writes_failed_evidence(self):
        sys.path.insert(0, str(ROOT / "experiments/frontier_mac"))
        try:
            import run_search
        finally:
            sys.path.pop(0)
        with tempfile.TemporaryDirectory() as tmp:
            instance = Path(tmp) / "instance.json"
            output = Path(tmp) / "result.json"
            instance.write_text(json.dumps({"part": 1, "grid": ["#####", "#F.G#", "#####"], "route": "RR"}))
            args = ["run_search", str(instance), "--output", str(output)]
            with patch.object(sys, "argv", args), patch.object(run_search.shutil, "which", return_value="clang++"), patch.object(run_search.subprocess, "check_output", return_value="test compiler\n"), patch.object(run_search.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "compiler")):
                self.assertEqual(run_search.main(), 1)
            result = json.loads(output.read_text())
            self.assertEqual(result["status"], "BACKEND_FAILED")
            self.assertEqual(result["error_type"], "CalledProcessError")
            self.assertEqual(result["return_code"], 1)
            self.assertEqual(result["error_stage"], "compile")
            self.assertNotIn(str(Path(tmp)), json.dumps(result))
