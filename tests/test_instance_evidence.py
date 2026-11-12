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


class SearchFailureEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "experiments/frontier_mac"))
        try:
            import run_search
            cls.runner = run_search
        finally:
            sys.path.pop(0)

    def run_experiment(self, *, replay_effect=None, process_effect=None, compiler="clang++", instance_data=None):
        seed = {"valid_winning_route": True, "certificate_sha256": "seed-certificate"}
        candidate = {"valid_winning_route": True, "certificate_sha256": "candidate-certificate"}
        if replay_effect is None:
            replay_effect = [seed, candidate]
        if process_effect is None:
            process_effect = [subprocess.CompletedProcess("compiler", 0),
                              subprocess.CompletedProcess("search", 0, '{"best_route": "RR"}')]
        with tempfile.TemporaryDirectory() as tmp:
            instance = Path(tmp) / "instance.json"
            output = Path(tmp) / "result.json"
            instance.write_text(instance_data if instance_data is not None else json.dumps(
                {"part": 1, "grid": ["#####", "#F.G#", "#####"], "route": "RR"}))
            args = ["run_search", str(instance), "--output", str(output)]
            with patch.object(sys, "argv", args), \
                 patch.object(self.runner, "replay", side_effect=replay_effect), \
                 patch.object(self.runner.shutil, "which", return_value=compiler), \
                 patch.object(self.runner.subprocess, "check_output", return_value="test compiler\n"), \
                 patch.object(self.runner.subprocess, "run", side_effect=process_effect) as processes:
                code = self.runner.main()
            result = json.loads(output.read_text())
            self.assertNotIn(str(Path(tmp)), json.dumps(result))
            return code, result, processes.call_count

    def test_compiler_failure_writes_failed_evidence(self):
        code, result, calls = self.run_experiment(process_effect=subprocess.CalledProcessError(1, "compiler"))
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "BACKEND_FAILED")
        self.assertEqual(result["error_type"], "CalledProcessError")
        self.assertEqual(result["return_code"], 1)
        self.assertEqual(result["error_stage"], "compile")
        self.assertEqual(calls, 1)

    def test_seed_backend_failure_writes_evidence_before_search(self):
        code, result, calls = self.run_experiment(replay_effect=subprocess.CalledProcessError(2, "seed-engine"))
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "BACKEND_FAILED")
        self.assertEqual(result["error_stage"], "seed_replay")
        self.assertEqual(result["return_code"], 2)
        self.assertEqual(calls, 0)
        self.assertNotIn("candidate_certificate", result)

    def test_rejected_seed_prevents_search(self):
        code, result, calls = self.run_experiment(replay_effect=[{"valid_winning_route": False}])
        self.assertEqual((code, result["status"], calls), (1, "SEED_REJECTED", 0))

    def test_missing_compiler_writes_unavailable_evidence(self):
        code, result, calls = self.run_experiment(compiler=None)
        self.assertEqual((code, result["status"], calls), (1, "UNAVAILABLE_BACKEND", 0))
        self.assertEqual(result["error_stage"], "compiler_discovery")

    def test_invalid_json_writes_failed_evidence(self):
        code, result, calls = self.run_experiment(instance_data="not JSON")
        self.assertEqual((code, result["status"], calls), (1, "BACKEND_FAILED", 0))
        self.assertEqual(result["error_stage"], "instance_read")

    def test_search_timeout_does_not_claim_a_candidate(self):
        code, result, calls = self.run_experiment(process_effect=[
            subprocess.CompletedProcess("compiler", 0), subprocess.TimeoutExpired("search", 105)])
        self.assertEqual((code, result["status"], calls), (1, "TIMEOUT_NO_CANDIDATE_RETURNED", 2))
        self.assertNotIn("candidate_certificate", result)
        self.assertIn("elapsed_seconds", result)

    def test_candidate_replay_timeout_is_not_a_search_timeout(self):
        code, result, calls = self.run_experiment(replay_effect=[
            {"valid_winning_route": True, "certificate_sha256": "seed-certificate"},
            subprocess.TimeoutExpired("candidate-engine", 5)])
        self.assertEqual((code, result["status"], calls), (1, "BACKEND_FAILED", 2))
        self.assertEqual(result["error_stage"], "candidate_replay")
        self.assertIn("search", result)
        self.assertNotIn("candidate_certificate", result)
        self.assertIn("elapsed_seconds", result)

    def test_malformed_candidate_output_is_recorded(self):
        code, result, calls = self.run_experiment(process_effect=[
            subprocess.CompletedProcess("compiler", 0), subprocess.CompletedProcess("search", 0, "[]")])
        self.assertEqual((code, result["status"], calls), (1, "BACKEND_FAILED", 2))
        self.assertEqual(result["error_stage"], "search_output")
        self.assertNotIn("candidate_certificate", result)

    def test_success_requires_accepted_candidate_replay(self):
        code, result, calls = self.run_experiment()
        self.assertEqual((code, result["status"], calls), (0, "CANDIDATE_ACCEPTED", 2))
        self.assertEqual(result["candidate_certificate"]["certificate_sha256"], "candidate-certificate")
        code, result, calls = self.run_experiment(replay_effect=[
            {"valid_winning_route": True, "certificate_sha256": "seed-certificate"},
            {"valid_winning_route": False}])
        self.assertEqual((code, result["status"], calls), (1, "CANDIDATE_REJECTED", 2))


if __name__ == "__main__":
    unittest.main()
