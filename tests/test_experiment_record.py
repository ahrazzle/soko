import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
import venv
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "experiments/record_run.py"
spec = importlib.util.spec_from_file_location("record_run", SCRIPT)
record = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record)


class ExperimentRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "source.txt").write_text("fixed input")
        self.plan = {"schema_version": 1, "id": "control", "purpose": "calibration",
                     "question": "Does the control reject an invalid route?",
                     "hypothesis": "It rejects an extra key after winning.",
                     "intervention": "Append one key", "control": "Original winning route",
                     "prediction": "Control passes, intervention fails", "decision_rule": "Stop search if checker accepts both",
                     "instance": {"source_url": "https://example.test/pinned", "source_sha256": "a" * 64},
                     "baseline": {"as_of": "2026-11-12", "keys": 84},
                     "wall_seconds": 5, "tracked_files": ["source.txt"]}
        self.path = self.root / "plan.json"

    def run_command(self, program):
        self.path.write_text(json.dumps(self.plan))
        return record.run(self.path, self.root / "run", [sys.executable, "-c", program], self.root)

    def test_success_is_not_a_verified_gain(self):
        result = self.run_command("print('claimed world record')")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["acceptance"], "not_evaluated")
        self.assertIsNone(result["verified_gain"])
        self.assertTrue(result["sources_unchanged"])
        self.assertIn("claimed world record", (self.root / "run/stdout.log").read_text())

    def test_nonzero_exit_preserved(self):
        result = self.run_command("import sys; sys.exit(7)")
        self.assertEqual(result["status"], "COMMAND_FAILED")
        self.assertEqual(result["returncode"], 7)

    def test_executable_identity_uses_child_cwd_for_relative_path_entries(self):
        launcher = self.root / "launcher"
        launcher.mkdir()
        self.path.write_text(json.dumps(self.plan))
        previous_cwd = Path.cwd()
        for index, entry in enumerate(("bin", "")):
            with self.subTest(path_entry=entry):
                for root, output in ((launcher, "wrong"), (self.root, "actual")):
                    directory = root / entry
                    directory.mkdir(exist_ok=True)
                    tool = directory / "probe"
                    tool.write_text(f"#!/bin/sh\nprintf '{output}\\n'\n")
                    tool.chmod(0o755)
                try:
                    os.chdir(launcher)
                    with mock.patch.dict(os.environ, {"PATH": entry}):
                        result = record.run(self.path, self.root / f"path-run-{index}",
                                            ["probe"], self.root)
                finally:
                    os.chdir(previous_cwd)
                actual = self.root / entry / "probe"
                self.assertEqual(result["status"], "COMPLETED")
                self.assertEqual(result["command"], ["probe"])
                self.assertEqual(result["executable"], str(actual))
                self.assertEqual(result["executable_sha256"], record.sha256(actual))
                self.assertEqual((self.root / f"path-run-{index}/stdout.log").read_text(), "actual\n")

    def test_interpreter_symlink_preserves_virtual_environment(self):
        environment = self.root / "venv"
        venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
        self.path.write_text(json.dumps(self.plan))
        result = record.run(self.path, self.root / "run",
                            [str(environment / "bin/python"), "-c", "import sys; print(sys.prefix)"],
                            self.root)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual((self.root / "run/stdout.log").read_text().strip(), str(environment))

    def test_timeout_is_not_negative_search_result(self):
        self.plan["wall_seconds"] = 0.1
        result = self.run_command("import time; time.sleep(30)")
        self.assertEqual(result["status"], "TIMED_OUT")
        self.assertLess(result["elapsed_seconds"], 4)
        self.assertIsNone(result["verified_gain"])

    @unittest.skipUnless(Path("/proc/self/stat").exists(), "uses Linux process state to distinguish zombies")
    def test_timeout_kills_worker_when_parent_exits_on_term(self):
        self.plan["wall_seconds"] = 1
        worker = ("import os, signal, time; from pathlib import Path; "
                  "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                  "Path('worker.pid').write_text(str(os.getpid())); time.sleep(30)")
        result = self.run_command("import subprocess, sys, time; "
                                  f"subprocess.Popen([sys.executable, '-c', {worker!r}]); time.sleep(30)")
        self.assertEqual(result["status"], "TIMED_OUT")
        pid = int((self.root / "worker.pid").read_text())
        # SIGKILL delivery can precede the final state update. An orphaned zombie
        # is already dead even if the container's init has not reaped it yet.
        def running():
            try:
                state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                return False
            return state not in ("Z", "X")
        try:
            deadline = time.monotonic() + 0.5
            while running() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(running(), "worker survived the parent's timeout")
        finally:
            if running():
                os.kill(pid, signal.SIGKILL)

    def test_changed_source_invalidates_comparability(self):
        result = self.run_command("from pathlib import Path; Path('source.txt').write_text('changed')")
        self.assertEqual(result["status"], "SOURCE_CHANGED")
        self.assertEqual(result["process_status"], "COMPLETED")

    def test_previous_observation_is_not_overwritten(self):
        self.run_command("print('first')")
        with self.assertRaises(FileExistsError):
            self.run_command("print('second')")
        self.assertEqual((self.root / "run/stdout.log").read_text(), "first\n")

    def test_declared_evidence_is_retained_and_hashed(self):
        self.plan["artifacts"] = ["replay.json"]
        result = self.run_command("from pathlib import Path; Path('run/replay.json').write_text('{}')")
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["artifacts"]["replay.json"]["sha256"], record.sha256(self.root / "run/replay.json"))
        self.assertEqual(result["missing_artifacts"], [])

    def test_success_without_declared_evidence_fails(self):
        self.plan["artifacts"] = ["replay.json"]
        result = self.run_command("print('success')")
        self.assertEqual(result["status"], "ARTIFACT_MISSING")
        self.assertEqual(result["process_status"], "COMPLETED")
        self.assertEqual(result["missing_artifacts"], ["replay.json"])

    def test_artifact_cannot_escape_the_run_directory(self):
        for name in ("../outside.json", "/tmp/outside.json", "result.json", "./result.json", "."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                record.validate_plan(dict(self.plan, artifacts=[name]))
        self.plan["artifacts"] = ["replay.json"]
        result = self.run_command("from pathlib import Path; Path('run/replay.json').symlink_to('../source.txt')")
        self.assertEqual(result["status"], "ARTIFACT_MISSING")

    def test_nonregular_artifact_is_missing_without_reading(self):
        self.plan["artifacts"] = ["replay.json"]
        # Reading a FIFO would block. The mocked reader makes the regression
        # fail promptly instead of hanging the test process if the guard breaks.
        original_read = Path.read_bytes
        def guarded_read(path):
            if path.name == "replay.json":
                self.fail("attempted to read a nonregular artifact")
            return original_read(path)
        with mock.patch.object(Path, "read_bytes", guarded_read):
            result = self.run_command("import os; os.mkfifo('run/replay.json')")
        self.assertEqual(result["status"], "ARTIFACT_MISSING")
        self.assertEqual(result["missing_artifacts"], ["replay.json"])

    def test_no_unbounded_or_unplanned_execution(self):
        for field in ("hypothesis", "control", "prediction", "decision_rule"):
            plan = dict(self.plan, **{field: ""})
            with self.subTest(field=field), self.assertRaises(ValueError):
                record.validate_plan(plan)
        for limit in (True, 0, -1, float("inf"), float("nan")):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                record.validate_plan(dict(self.plan, wall_seconds=limit))
