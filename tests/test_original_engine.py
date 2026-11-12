"""Offline boundaries plus opt-in original-browser integration tests.

Set SOKO_ORIGINAL_HTML to a pinned cached HTML file to run browser cases.
"""
import hashlib
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from experiments.original_engine import check as original
from soko_mcp import original as runtime


class OriginalEngineBoundaryTests(unittest.TestCase):
    def test_input_rejection_before_download_or_browser(self):
        with patch.object(original, "get_html") as download:
            for room, route in ((True, "R"), (0, "R"), (23, "R"), (20, None),
                                (20, "r"), (20, "R R"), (20, "X"), (20, "R" * 10001)):
                with self.subTest(room=room, route=route), self.assertRaises(ValueError):
                    original.check(room, route)
            download.assert_not_called()

    def test_supplied_and_cached_html_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            supplied = root / "input.html"
            supplied.write_bytes(b"changed source")
            cached = root / (original.HTML_SHA256 + ".html")
            cached.write_bytes(b"changed source")
            with patch.object(original.subprocess, "run") as fetch:
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    original.get_html(supplied)
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    original.get_html(cache_dir=root)
                fetch.assert_not_called()
            self.assertEqual(cached.read_bytes(), b"changed source")

    def test_bad_download_is_not_installed_or_trusted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def fetch(command, **kwargs):
                Path(command[command.index("--output") + 1]).write_bytes(b"bad response")

            with patch.object(original.subprocess, "run", side_effect=fetch):
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    original.get_html(cache_dir=root)
            self.assertEqual(list(root.iterdir()), [])

    def test_valid_download_is_pinned_and_cached(self):
        content = b"known test fixture"
        pin = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(runtime.SOURCES, {3: (runtime.SOURCE_URL, pin, runtime.SCRIPT_SHA256)}):
            root = Path(tmp)

            def fetch(command, **kwargs):
                self.assertNotIn("--insecure", command)
                self.assertNotIn("-k", command)
                self.assertEqual(command[-1], original.SOURCE_URL)
                Path(command[command.index("--output") + 1]).write_bytes(content)

            with patch.object(original.subprocess, "run", side_effect=fetch) as download:
                self.assertEqual(original.get_html(cache_dir=root), content)
                self.assertEqual(original.get_html(cache_dir=root), content)
                self.assertEqual(download.call_count, 1)

    def test_only_exact_final_win_without_death_restart_or_again_cutoff_passes(self):
        valid = {"first_win": 84, "first_death": None, "restarts": 0, "again_limit_hit": False}
        self.assertTrue(original.accepted(valid, 84))
        for change in ({"first_win": 83}, {"first_win": None}, {"first_win": True},
                       {"first_death": 20}, {"restarts": 1}, {"again_limit_hit": True}):
            self.assertFalse(original.accepted(dict(valid, **change), 84))
        self.assertFalse(original.accepted(valid, 85))
        self.assertFalse(original.accepted({}, 0))

    def test_local_server_exposes_only_the_validated_page(self):
        with original.local_page(b"pinned page") as url:
            self.assertEqual(urllib.request.urlopen(url).read(), b"pinned page")
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(url.replace("part3.html", "another-file"))
            self.assertEqual(error.exception.code, 404)

    def test_runtime_failure_replaces_a_stale_success_certificate(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "result.json"
            output.write_text('{"valid_winning_route":true}')
            with patch("sys.argv", ["check", "--room", "20", "--route", "RR", "--output", str(output)]), \
                 patch.object(original, "check", side_effect=RuntimeError("browser unavailable")), \
                 redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(original.main(), 2)
            result = json.loads(output.read_text())
            self.assertFalse(result["valid_winning_route"])
            self.assertEqual(result["status"], "CHECK_FAILED")


@unittest.skipUnless(os.environ.get("SOKO_ORIGINAL_HTML"), "set SOKO_ORIGINAL_HTML for original-browser checks")
class OriginalEngineBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path(os.environ["SOKO_ORIGINAL_HTML"])
        cls.root = Path(__file__).resolve().parents[1]

    def test_recorded_baselines_and_bound_evidence(self):
        from soko_mcp.oracle import FRONTIER_ROOMS
        cases = [(14, FRONTIER_ROOMS["III-14-15x7"]["reference_route"])]
        for room in (20, 21):
            data = json.loads((self.root / f"evidence/2026-11-12-frontier/iii{room}-live-instance.json").read_text())
            cases.append((room, data["route"]))
        for room, route in cases:
            with self.subTest(room=room):
                result = original.check(room, route, html=self.html)
                self.assertTrue(result["valid_winning_route"])
                self.assertEqual(result["first_win"], len(route))
                self.assertNotIn("frames", result)
                self.assertFalse(result["public_submission"])
                self.assertFalse(result["formal_proof_checked"])
                certificate = result.pop("certificate_sha256")
                self.assertEqual(certificate, original.digest(result))
                if room == 14:
                    self.assertEqual((result["width"], result["height"]), (15, 7))

    def test_original_engine_rejects_truncation_premature_win_and_death(self):
        data = json.loads((self.root / "evidence/2026-11-12-frontier/iii20-live-instance.json").read_text())
        route = data["route"]
        for candidate in (route[:-1], route + "R", "AAU"):
            with self.subTest(length=len(candidate)):
                result = original.check(20, candidate, html=self.html, include_frames=True)
                self.assertFalse(result["valid_winning_route"])
                self.assertIn("frames", result)
                self.assertEqual(result["trajectory_sha256"], original.digest(result["frames"]))
                if candidate == "AAU":
                    self.assertEqual(result["first_death"], 3)
                    self.assertIsNone(result["first_win"])

class TrilogyReplayTests(unittest.TestCase):
    def test_input_and_timeout_validation_before_worker(self):
        from soko_mcp import original as runtime
        with patch.object(runtime.subprocess, "Popen") as worker:
            for args in ((0, 1, ""), (True, 1, ""), (1, 23, ""), (2, 1, "x")):
                with self.subTest(args=args), self.assertRaises(ValueError):
                    runtime.replay(*args)
            for timeout in (0, -1, float("inf"), True):
                with self.assertRaises(ValueError):
                    runtime.replay(1, 1, "", timeout_sec=timeout)
            worker.assert_not_called()

    def test_catalog_source_pins_match_runtime(self):
        from soko_mcp.original import SOURCES
        catalog = json.loads((Path(__file__).resolve().parents[1] / "soko_mcp/data/catalog.json").read_text())
        for source in catalog["sources"]:
            self.assertEqual(SOURCES[source["part"]],
                             (source["url"], source["html_sha256"], source["source_sha256"]))

    def test_whole_worker_timeout(self):
        from soko_mcp.original import replay
        with self.assertRaises(TimeoutError):
            replay(1, 1, "", timeout_sec=0.001)

    def test_cancel_kills_worker_process_group_and_reaps(self):
        from soko_mcp import original as runtime
        with patch.object(runtime.subprocess, "Popen") as start, \
             patch.object(runtime.os, "killpg", side_effect=ProcessLookupError) as kill:
            process = start.return_value
            process.pid = 12345
            process.communicate.side_effect = [KeyboardInterrupt(), ("", "")]
            with self.assertRaises(KeyboardInterrupt):
                runtime.replay(1, 1, "")
            kill.assert_called_once_with(12345, runtime.signal.SIGKILL)
            self.assertEqual(process.communicate.call_count, 2)

    def test_all_three_html_pins_reject_altered_source(self):
        from soko_mcp import original as runtime
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "altered.html"
            path.write_bytes(b"altered")
            for part in (1, 2, 3):
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    runtime.checked_html(path, part)


@unittest.skipUnless(all(os.environ.get(f"SOKO_ORIGINAL_HTML_{n}") for n in (1, 2, 3)),
                     "set SOKO_ORIGINAL_HTML_1, _2, _3 for trilogy browser checks")
class TrilogyBrowserTests(unittest.TestCase):
    def test_prefix_state_and_three_active_heroes(self):
        from soko_mcp.original import replay, digest
        for part in (1, 2, 3):
            html = os.environ[f"SOKO_ORIGINAL_HTML_{part}"]
            route = "R" * 10 if part == 1 else ""
            result = replay(part, 22, route, html=html, include_frames=True)
            self.assertEqual(result["part"], part)
            self.assertEqual(result["valid_winning_route"], part == 1)
            self.assertEqual(result["steps_executed"], len(route))
            self.assertEqual(result["trajectory_sha256"], digest(result["frames"]))
            self.assertEqual(len(result["final_layers"]), result["height"])
            self.assertEqual([len(line) for line in result["final_ascii"].splitlines()],
                             [result["width"]] * result["height"])
            self.assertTrue(any("goal" in cell for row in result["final_layers"] for cell in row))
            self.assertEqual(result["final_objects"], result["frames"][-1]["objects"] if route else result["initial_objects"])
            certificate = result.pop("certificate_sha256")
            self.assertEqual(certificate, digest(result))
