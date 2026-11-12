"""Source-lock acceptance requires complete coverage, not just valid hash syntax."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from soko_mcp import engine_bridge
from soko_mcp.integrity import REQUIRED_SOURCES, render_source_manifest, verify_source_manifest


class SourceManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for relative in REQUIRED_SOURCES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture for {relative}\n")
        self.manifest = self.root / "SHA256SUMS"
        self.manifest.write_text(render_source_manifest(self.root))

    def check(self):
        return verify_source_manifest(self.root, self.manifest)

    def test_complete_source_lock_needs_no_compiler_or_binary(self):
        with mock.patch.object(engine_bridge, "REPO_ROOT", self.root), \
             mock.patch.object(engine_bridge, "SHA256SUMS_PATH", self.manifest), \
             mock.patch.object(engine_bridge, "CPP_BIN", self.root / "absent-binary"), \
             mock.patch.object(engine_bridge, "ensure_cpp_engine", side_effect=AssertionError("must not build")):
            result = engine_bridge.verify_tcb_lock()
        self.assertTrue(result["source_integrity_verified"])
        self.assertEqual(result["files_verified"], len(REQUIRED_SOURCES))
        self.assertFalse(result["compiled_binary"]["verified_by_manifest"])
        self.assertFalse(result["cpp_engine_compiled"])

    def test_one_valid_hash_is_not_complete_coverage(self):
        self.manifest.write_text(self.manifest.read_text().splitlines()[0] + "\n")
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertEqual(len(result["missing_entries"]), len(REQUIRED_SOURCES) - 1)

    def test_malformed_lines_fail_even_alongside_valid_manifest(self):
        valid = self.manifest.read_text()
        for suffix in ("ignored garbage", "z" * 64 + "  bogus.py", "# comment"):
            with self.subTest(line=suffix):
                self.manifest.write_text(valid + suffix + "\n")
                result = self.check()
                self.assertFalse(result["source_integrity_verified"])
                self.assertTrue(result["malformed_lines"])

    def test_duplicate_entry_fails(self):
        text = self.manifest.read_text()
        self.manifest.write_text(text + text.splitlines()[0] + "\n")
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertEqual(result["duplicate_entries"], [REQUIRED_SOURCES[0]])

    def test_binary_is_observed_separately_not_a_portable_manifest_entry(self):
        self.manifest.write_text(self.manifest.read_text() + "0" * 64 + "  cpp/build/soko_engine\n")
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertEqual(result["unexpected_entries"], ["cpp/build/soko_engine"])

    def test_paths_cannot_escape_or_alias_a_covered_entry(self):
        text = self.manifest.read_text()
        for relative in ("../outside", "/tmp/outside", "./soko_mcp/oracle.py", "soko_mcp//oracle.py", "soko_mcp\\oracle.py"):
            with self.subTest(path=relative):
                self.manifest.write_text(text + "0" * 64 + "  " + relative + "\n")
                result = self.check()
                self.assertFalse(result["source_integrity_verified"])
                self.assertTrue(result["unconfined_paths"])

    def test_symlink_cannot_escape_root(self):
        path = self.root / REQUIRED_SOURCES[0]
        path.unlink()
        path.symlink_to(self.root.parent / "outside")
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertTrue(result["unconfined_paths"])

    def test_changed_source_fails(self):
        (self.root / REQUIRED_SOURCES[0]).write_text("changed\n")
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertEqual(result["mismatched_files"][0]["file"], REQUIRED_SOURCES[0])

    def test_missing_source_fails(self):
        (self.root / REQUIRED_SOURCES[0]).unlink()
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertEqual(result["missing_files"], [REQUIRED_SOURCES[0]])

    def test_missing_or_empty_manifest_fails(self):
        self.manifest.write_text("")
        self.assertFalse(self.check()["source_integrity_verified"])
        self.manifest.unlink()
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertFalse(result["manifest_present"])

    def test_unreadable_source_is_reported_as_failure(self):
        (self.root / REQUIRED_SOURCES[0]).unlink()
        (self.root / REQUIRED_SOURCES[0]).mkdir()
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertTrue(result["read_errors"])

    def test_invalid_utf8_manifest_fails_closed(self):
        self.manifest.write_bytes(b"\xff")
        result = self.check()
        self.assertFalse(result["source_integrity_verified"])
        self.assertTrue(result["read_errors"])


if __name__ == "__main__":
    unittest.main()
