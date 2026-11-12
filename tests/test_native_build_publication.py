"""A compiler must not corrupt the executable another agent is using."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from soko_mcp import engine_bridge as bridge


class NativeBuildPublicationTests(unittest.TestCase):
    def exercise(self, compiler_returncode):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, binary = root / 'engine.cpp', root / 'soko_engine'
            source.write_text('source')
            binary.write_bytes(b'working executable')
            os.utime(binary, (1, 1))

            def compile_candidate(command, **kwargs):
                candidate = Path(command[command.index('-o') + 1])
                candidate.write_bytes(b'partial link output')
                self.assertEqual(binary.read_bytes(), b'working executable')
                if compiler_returncode == 0:
                    candidate.write_bytes(b'finished executable')
                return subprocess.CompletedProcess(command, compiler_returncode)

            with patch.object(bridge, 'CPP_SRC', source), patch.object(bridge, 'CPP_BIN', binary), \
                    patch.object(bridge, 'CPP_BIN_DIR', root), \
                    patch.object(bridge.shutil, 'which', return_value='compiler'), \
                    patch.object(bridge.subprocess, 'run', side_effect=compile_candidate):
                result = bridge.ensure_cpp_engine()
            self.assertEqual(list(root.glob('compile-*')), [])
            if compiler_returncode:
                self.assertIsNone(result)
                self.assertEqual(binary.read_bytes(), b'working executable')
            else:
                self.assertEqual(result, binary)
                self.assertEqual(binary.read_bytes(), b'finished executable')

    def test_success_only_publishes_complete_executable(self):
        self.exercise(0)

    def test_failed_compile_retains_existing_executable(self):
        self.exercise(1)
