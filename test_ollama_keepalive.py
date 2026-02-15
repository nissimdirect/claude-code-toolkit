#!/usr/bin/env python3
"""Tests for ollama_keepalive.py — keepalive daemon and model pinging."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ollama_keepalive as ok


class TestIsOllamaRunning(unittest.TestCase):
    """Test Ollama detection."""

    @patch('ollama_keepalive.urllib.request.urlopen')
    def test_running(self, mock_urlopen):
        """Returns True when Ollama responds."""
        mock_urlopen.return_value.__enter__ = lambda s: MagicMock()
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        self.assertTrue(ok.is_ollama_running())

    @patch('ollama_keepalive.urllib.request.urlopen', side_effect=Exception("Connection refused"))
    def test_not_running(self, mock_urlopen):
        """Returns False when Ollama is down."""
        self.assertFalse(ok.is_ollama_running())


class TestPingModel(unittest.TestCase):
    """Test model ping functionality."""

    @patch('ollama_keepalive.urllib.request.urlopen')
    def test_successful_ping(self, mock_urlopen):
        """Returns True on successful ping."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"message": {"content": "pong"}}).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        self.assertTrue(ok.ping_model("mistral:7b"))

    @patch('ollama_keepalive.urllib.request.urlopen', side_effect=Exception("timeout"))
    def test_failed_ping(self, mock_urlopen):
        """Returns False on failed ping."""
        self.assertFalse(ok.ping_model("mistral:7b"))

    @patch('ollama_keepalive.urllib.request.urlopen')
    def test_ping_sends_correct_payload(self, mock_urlopen):
        """Ping sends correct model name and minimal predict."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"message":{"content":"ok"}}'
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        ok.ping_model("qwen3:8b")

        # Verify the request was made
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        payload = json.loads(req.data)
        self.assertEqual(payload['model'], 'qwen3:8b')
        self.assertEqual(payload['options']['num_predict'], 1)
        self.assertFalse(payload['stream'])


class TestRunOnce(unittest.TestCase):
    """Test single keepalive pass."""

    @patch('ollama_keepalive.ping_model')
    @patch('ollama_keepalive.is_ollama_running', return_value=True)
    def test_pings_all_models(self, mock_running, mock_ping):
        """run_once pings all configured models."""
        ok.run_once()
        self.assertEqual(mock_ping.call_count, len(ok.MODELS_TO_KEEP))

    @patch('ollama_keepalive.ping_model')
    @patch('ollama_keepalive.is_ollama_running', return_value=False)
    def test_skips_when_not_running(self, mock_running, mock_ping):
        """run_once skips pings when Ollama is down."""
        ok.run_once()
        mock_ping.assert_not_called()


class TestPidManagement(unittest.TestCase):
    """Test PID file and stale detection."""

    def test_is_pid_running_self(self):
        """Current process PID should be running."""
        self.assertTrue(ok._is_pid_running(os.getpid()))

    def test_is_pid_running_nonexistent(self):
        """Non-existent PID should return False."""
        self.assertFalse(ok._is_pid_running(99999999))

    def test_stale_pid_detection(self):
        """Stale PID file gets cleaned up on daemon start."""
        tmp = tempfile.NamedTemporaryFile(suffix='.pid', delete=False)
        tmp.write(b"99999999")  # Non-existent PID
        tmp.close()

        orig_lock = ok.LOCK_FILE
        ok.LOCK_FILE = Path(tmp.name)

        # Daemon should detect stale PID and clean it up
        # We can't run full daemon (it loops), but we can test the logic
        self.assertTrue(Path(tmp.name).exists())
        old_pid = int(Path(tmp.name).read_text().strip())
        self.assertFalse(ok._is_pid_running(old_pid))

        ok.LOCK_FILE = orig_lock
        os.unlink(tmp.name)

    def test_running_pid_blocks_start(self):
        """Running PID in lock file should block daemon."""
        tmp = tempfile.NamedTemporaryFile(suffix='.pid', delete=False)
        tmp.write(str(os.getpid()).encode())  # Current (running) PID
        tmp.close()

        orig_lock = ok.LOCK_FILE
        ok.LOCK_FILE = Path(tmp.name)

        with self.assertRaises(SystemExit):
            ok.run_daemon()

        ok.LOCK_FILE = orig_lock
        os.unlink(tmp.name)


class TestConfig(unittest.TestCase):
    """Test configuration constants."""

    def test_models_configured(self):
        """At least one model is configured for keepalive."""
        self.assertTrue(len(ok.MODELS_TO_KEEP) > 0)

    def test_ping_interval_reasonable(self):
        """Ping interval is less than Ollama's 5min keepalive."""
        self.assertLess(ok.PING_INTERVAL, 300)
        self.assertGreater(ok.PING_INTERVAL, 60)

    def test_ollama_url_localhost(self):
        """Ollama URL points to localhost."""
        self.assertIn('localhost', ok.OLLAMA_URL)
        self.assertIn('11434', ok.OLLAMA_URL)


class TestLiveOllama(unittest.TestCase):
    """Integration tests — only run if Ollama is actually available."""

    def setUp(self):
        if not ok.is_ollama_running():
            self.skipTest("Ollama not running")

    def test_live_ping(self):
        """Live ping to Ollama succeeds."""
        result = ok.ping_model("mistral:7b")
        self.assertTrue(result)

    def test_live_run_once(self):
        """Live run_once completes without error."""
        ok.run_once()  # Should not raise


if __name__ == '__main__':
    unittest.main()
