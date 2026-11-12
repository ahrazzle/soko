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
        with tempfile.TemporaryDirectory() as tmp, patch.object(original, "HTML_SHA256", pin):
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
