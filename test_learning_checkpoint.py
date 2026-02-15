#!/usr/bin/env python3
"""Tests for learning_checkpoint.py — buffer, flush, health check."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the module under test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import learning_checkpoint as lc


class TestBufferOperations(unittest.TestCase):
    """Test add/list/count/flush with isolated buffer."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self.tmp.close()
        self.orig_path = lc.BUFFER_PATH
        lc.BUFFER_PATH = Path(self.tmp.name)

    def tearDown(self):
        lc.BUFFER_PATH = self.orig_path
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    def test_empty_buffer(self):
        """Fresh buffer has no learnings."""
        os.unlink(self.tmp.name)  # Start with no file
        buf = lc._load_buffer()
        self.assertEqual(buf['learnings'], [])
        self.assertIsNone(buf['session_id'])

    def test_add_learning(self):
        """add_learning writes to disk immediately."""
        os.unlink(self.tmp.name)
        lc.add_learning("Test learning one")
        buf = lc._load_buffer()
        self.assertEqual(len(buf['learnings']), 1)
        self.assertEqual(buf['learnings'][0]['text'], "Test learning one")
        self.assertEqual(buf['learnings'][0]['category'], 'general')
        self.assertIsNotNone(buf['started'])

    def test_add_multiple(self):
        """Multiple adds accumulate in buffer."""
        os.unlink(self.tmp.name)
        lc.add_learning("First")
        lc.add_learning("Second", category='system')
        lc.add_learning("Third", category='health')
        buf = lc._load_buffer()
        self.assertEqual(len(buf['learnings']), 3)
        self.assertEqual(buf['learnings'][1]['category'], 'system')

    def test_count(self, ):
        """count_learnings returns JSON with correct count."""
        os.unlink(self.tmp.name)
        lc.add_learning("A")
        lc.add_learning("B")
        # Capture stdout
        import io
        captured = io.StringIO()
        sys.stdout = captured
        lc.count_learnings()
        sys.stdout = sys.__stdout__
        data = json.loads(captured.getvalue())
        self.assertEqual(data['count'], 2)

    def test_flush_clears_buffer(self):
        """flush_learnings outputs learnings and clears buffer."""
        os.unlink(self.tmp.name)
        lc.add_learning("Flush me")
        lc.add_learning("Flush me too", category='system')

        # Capture flush output
        import io
        captured = io.StringIO()
        sys.stdout = captured
        lc.flush_learnings()
        sys.stdout = sys.__stdout__
        output = captured.getvalue()

        self.assertIn("Flush me", output)
        self.assertIn("[system]", output)
        self.assertIn("Buffer cleared", output)

        # Buffer should be empty after flush
        buf = lc._load_buffer()
        self.assertEqual(len(buf['learnings']), 0)

    def test_flush_empty_buffer(self):
        """Flushing empty buffer reports nothing to flush."""
        os.unlink(self.tmp.name)
        import io
        captured = io.StringIO()
        sys.stdout = captured
        lc.flush_learnings()
        sys.stdout = sys.__stdout__
        self.assertIn("No learnings to flush", captured.getvalue())

    def test_corrupt_json_recovery(self):
        """Corrupt buffer file returns empty buffer."""
        Path(self.tmp.name).write_text("NOT JSON {{{")
        buf = lc._load_buffer()
        self.assertEqual(buf['learnings'], [])

    def test_atomic_write(self):
        """Buffer write is atomic (uses os.replace)."""
        os.unlink(self.tmp.name)
        lc.add_learning("Atomic test")
        # File should exist and be valid JSON
        self.assertTrue(Path(self.tmp.name).exists())
        data = json.loads(Path(self.tmp.name).read_text())
        self.assertEqual(len(data['learnings']), 1)


class TestHealthCheck(unittest.TestCase):
    """Test health_check with mocked subprocess calls."""

    def setUp(self):
        # Use temp buffer to avoid polluting real buffer
        self.tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self.tmp.close()
        self.orig_path = lc.BUFFER_PATH
        lc.BUFFER_PATH = Path(self.tmp.name)
        os.unlink(self.tmp.name)

    def tearDown(self):
        lc.BUFFER_PATH = self.orig_path
        try:
            os.unlink(self.tmp.name)
        except OSError:
            pass

    @patch('subprocess.Popen')
    @patch('subprocess.run')
    def test_health_check_returns_results(self, mock_run, mock_popen):
        """health_check returns a list of results."""
        # Mock all subprocess calls to fail (systems not running)
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='')
        mock_popen.return_value = MagicMock()
        mock_popen.return_value.stdout = MagicMock()
        mock_popen.return_value.wait = MagicMock()

        results = lc.health_check()
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)
        for r in results:
            self.assertIn('name', r)
            self.assertIn('status', r)
            self.assertIn('severity', r)

    @patch('subprocess.Popen')
    @patch('subprocess.run')
    def test_health_check_buffers_high_failures(self, mock_run, mock_popen):
        """HIGH severity failures get auto-buffered as learnings."""
        mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='')
        mock_popen.return_value = MagicMock()
        mock_popen.return_value.stdout = MagicMock()
        mock_popen.return_value.wait = MagicMock()

        lc.health_check()
        buf = lc._load_buffer()
        # Should have auto-buffered at least one HIGH failure
        health_learnings = [l for l in buf['learnings'] if l['category'] == 'health']
        self.assertTrue(len(health_learnings) > 0)

    def test_budget_freshness_check(self):
        """_check_budget_freshness returns tuple(bool, str)."""
        ok, detail = lc._check_budget_freshness()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(detail, str)

    def test_experiments_check(self):
        """_check_experiments returns tuple(bool, str)."""
        ok, detail = lc._check_experiments()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(detail, str)


class TestCLI(unittest.TestCase):
    """Test CLI entry point."""

    def test_add_via_cli(self):
        """CLI 'add' command works."""
        tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        tmp.close()
        os.unlink(tmp.name)

        with patch.object(lc, 'BUFFER_PATH', Path(tmp.name)):
            with patch('sys.argv', ['lc', 'add', 'CLI test learning']):
                lc.main()

        data = json.loads(Path(tmp.name).read_text())
        self.assertEqual(data['learnings'][0]['text'], 'CLI test learning')
        os.unlink(tmp.name)

    def test_add_with_category(self):
        """CLI 'add' with --category flag."""
        tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        tmp.close()
        os.unlink(tmp.name)

        with patch.object(lc, 'BUFFER_PATH', Path(tmp.name)):
            with patch('sys.argv', ['lc', 'add', 'Categorized', '--category', 'system']):
                lc.main()

        data = json.loads(Path(tmp.name).read_text())
        self.assertEqual(data['learnings'][0]['category'], 'system')
        os.unlink(tmp.name)

    def test_unknown_command_exits(self):
        """Unknown command exits with code 1."""
        with patch('sys.argv', ['lc', 'bogus']):
            with self.assertRaises(SystemExit) as ctx:
                lc.main()
            self.assertEqual(ctx.exception.code, 1)

    def test_no_args_exits(self):
        """No arguments exits with code 1."""
        with patch('sys.argv', ['lc']):
            with self.assertRaises(SystemExit) as ctx:
                lc.main()
            self.assertEqual(ctx.exception.code, 1)


if __name__ == '__main__':
    unittest.main()
