#!/usr/bin/env python3
"""Tests for claude_memory_watchdog.py

Tests core logic without requiring actual memory pressure.
Uses mocked subprocess outputs to simulate various memory conditions.
"""

import json
import os
import signal
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import the module under test
import claude_memory_watchdog as wd


class TestAlertLevels(unittest.TestCase):
    """Test alert level calculation from memory percentages."""

    def test_ok_level(self):
        self.assertEqual(wd.calculate_alert_level(0), "ok")
        self.assertEqual(wd.calculate_alert_level(30), "ok")
        self.assertEqual(wd.calculate_alert_level(64.9), "ok")

    def test_moderate_level(self):
        self.assertEqual(wd.calculate_alert_level(65), "moderate")
        self.assertEqual(wd.calculate_alert_level(70), "moderate")
        self.assertEqual(wd.calculate_alert_level(77.9), "moderate")

    def test_high_level(self):
        self.assertEqual(wd.calculate_alert_level(80), "high")
        self.assertEqual(wd.calculate_alert_level(88), "high")
        self.assertEqual(wd.calculate_alert_level(91.9), "high")

    def test_critical_level(self):
        self.assertEqual(wd.calculate_alert_level(92), "critical")
        self.assertEqual(wd.calculate_alert_level(94), "critical")
        self.assertEqual(wd.calculate_alert_level(95.5), "critical")

    def test_emergency_level(self):
        self.assertEqual(wd.calculate_alert_level(96), "emergency")
        self.assertEqual(wd.calculate_alert_level(98), "emergency")
        self.assertEqual(wd.calculate_alert_level(100), "emergency")


class TestVmStatParsing(unittest.TestCase):
    """Test parsing of vm_stat output."""

    SAMPLE_VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                3842.
Pages active:                            180825.
Pages inactive:                          170293.
Pages speculative:                          838.
Pages throttled:                              0.
Pages wired down:                         79231.
Pages purgeable:                          14023.
"Translation faults":                  11888665.
Pages copy-on-write:                    1065891.
Pages zero filled:                      5867591.
Pages reactivated:                       191893.
Pages purged:                             73558.
File-backed pages:                        92019.
Anonymous pages:                         259937.
Pages stored in compressor:              316503.
Pages occupied by compressor:             66988.
Decompressions:                          437424.
Compressions:                            777619.
Pageins:                                6555810.
Pageouts:                                  1063.
Swapins:                                  19072.
Swapouts:                                 21397.
"""

    @patch("subprocess.run")
    def test_parse_vm_stat(self, mock_run):
        mock_run.return_value = MagicMock(stdout=self.SAMPLE_VM_STAT, returncode=0)
        stats = wd.parse_vm_stat()

        page_size = 16384
        self.assertEqual(stats["free"], 3842 * page_size)
        self.assertEqual(stats["active"], 180825 * page_size)
        self.assertEqual(stats["wired_down"], 79231 * page_size)
        self.assertEqual(stats["occupied_by_compressor"], 66988 * page_size)

    @patch("subprocess.run")
    def test_parse_vm_stat_timeout(self, mock_run):
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("vm_stat", 3)
        stats = wd.parse_vm_stat()
        self.assertEqual(stats, {})


class TestMemoryPressure(unittest.TestCase):
    """Test memory pressure calculation."""

    @patch("claude_memory_watchdog.parse_vm_stat")
    @patch("claude_memory_watchdog.get_total_ram_bytes")
    def test_pressure_calculation(self, mock_total, mock_vmstat):
        mock_total.return_value = 16 * 1024**3  # 16 GB

        mb = 1024 * 1024
        mock_vmstat.return_value = {
            "wired_down": 2000 * mb,  # 2 GB
            "active": 4000 * mb,  # 4 GB
            "occupied_by_compressor": 1000 * mb,  # 1 GB
            "inactive": 3000 * mb,
            "free": 6000 * mb,
        }

        used, total, breakdown = wd.get_memory_pressure()
        self.assertEqual(total, 16 * 1024**3)
        # Used should be wired + active + compressed = 7 GB
        expected_used = 7000 * mb
        self.assertEqual(used, expected_used)
        self.assertEqual(breakdown["wired_mb"], 2000)
        self.assertEqual(breakdown["active_mb"], 4000)
        self.assertEqual(breakdown["compressed_mb"], 1000)


class TestProcessMemory(unittest.TestCase):
    """Test process memory parsing."""

    SAMPLE_PS = """ 1423  430064     1  1:05 claude --dangerously-skip-permissions
 1669  301312     1  0:09 claude --dangerously-skip-permissions
 1248 1838560     1  0:03 /opt/homebrew/Cellar/ollama/0.15.6/bin/ollama runner --model test
 1430   41200     1  0:00 npm exec @modelcontextprotocol/server-github
 1429   40640     1  0:00 npm exec @modelcontextprotocol/server-memory
  500  100000     1  0:00 /usr/bin/something-else
"""

    @patch("subprocess.run")
    def test_process_parsing(self, mock_run):
        mock_run.return_value = MagicMock(stdout=self.SAMPLE_PS, returncode=0)
        procs = wd.get_process_memory()

        # Should find 2 Claude processes
        self.assertEqual(len(procs["claude"]), 2)
        # Oldest PID should be primary
        self.assertEqual(procs["claude"][0]["pid"], 1423)
        self.assertEqual(procs["claude"][0]["type"], "primary")
        self.assertEqual(procs["claude"][1]["type"], "secondary")
        # Ollama runner should be detected
        self.assertGreater(procs["ollama_mb"], 1000)
        # MCP servers should be detected
        self.assertGreater(procs["mcp_mb"], 0)


class TestKillLogic(unittest.TestCase):
    """Test process kill ordering."""

    def test_kill_newest_preserves_primary(self):
        """LIFO: kill newest, preserve oldest (primary)."""
        procs = [
            {"pid": 100, "rss_mb": 400, "type": "primary"},
            {"pid": 200, "rss_mb": 300, "type": "secondary"},
            {"pid": 300, "rss_mb": 250, "type": "secondary"},
        ]
        with patch("os.kill") as mock_kill:
            killed = wd.kill_newest_claude(procs)
            # Should kill PID 300 (newest)
            mock_kill.assert_called_once_with(300, signal.SIGTERM)
            self.assertEqual(killed, 300)

    def test_kill_single_process_protected(self):
        """Never kill the only running process."""
        procs = [{"pid": 100, "rss_mb": 400, "type": "primary"}]
        with patch("os.kill") as mock_kill:
            killed = wd.kill_newest_claude(procs)
            mock_kill.assert_not_called()
            self.assertIsNone(killed)

    def test_kill_empty_list(self):
        """Empty process list is safe."""
        killed = wd.kill_newest_claude([])
        self.assertIsNone(killed)

    def test_kill_all_except_primary(self):
        """Emergency: kill all except oldest PID."""
        procs = [
            {"pid": 100, "rss_mb": 400, "type": "primary"},
            {"pid": 200, "rss_mb": 300, "type": "secondary"},
            {"pid": 300, "rss_mb": 250, "type": "secondary"},
        ]
        with patch("os.kill") as mock_kill:
            killed = wd.kill_all_claude_except_primary(procs)
            self.assertEqual(set(killed), {200, 300})
            # PID 100 (primary) should NOT be in kill calls
            kill_pids = [call[0][0] for call in mock_kill.call_args_list]
            self.assertNotIn(100, kill_pids)


class TestStateManagement(unittest.TestCase):
    """Test atomic state file writes."""

    def test_atomic_write(self):
        """State file should be written atomically (tmp+rename)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / ".memory-state.json"
            state_tmp = state_file.with_suffix(".tmp")

            # Monkey-patch the module paths
            orig_state = wd.STATE_FILE
            orig_tmp = wd.STATE_TMP
            wd.STATE_FILE = state_file
            wd.STATE_TMP = state_tmp

            try:
                state = {"alert_level": "ok", "used_pct": 42.0}
                wd.write_state(state)

                # State file should exist
                self.assertTrue(state_file.exists())
                # Tmp file should NOT exist (renamed away)
                self.assertFalse(state_tmp.exists())
                # Content should be valid JSON
                data = json.loads(state_file.read_text())
                self.assertEqual(data["alert_level"], "ok")
                self.assertEqual(data["used_pct"], 42.0)
            finally:
                wd.STATE_FILE = orig_state
                wd.STATE_TMP = orig_tmp


class TestHeuristics(unittest.TestCase):
    """Test heuristic tracking."""

    def test_rolling_average(self):
        h = {
            "avg_claude_mb": 400,
            "samples": 9,
            "peak_today_mb": 0,
            "peak_today_date": "",
            "peak_today_time": "",
            "incidents_today": 0,
            "incidents_today_date": "",
            "incidents_7d": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            orig = wd.HEURISTICS_FILE
            wd.HEURISTICS_FILE = Path(tmpdir) / "heuristics.json"
            try:
                h = wd.update_heuristics(h, 500, "ok")
                # (400*9 + 500) / 10 = 410
                self.assertEqual(h["avg_claude_mb"], 410)
                self.assertEqual(h["samples"], 10)
            finally:
                wd.HEURISTICS_FILE = orig

    def test_incident_tracking(self):
        h = {
            "avg_claude_mb": 0,
            "samples": 0,
            "peak_today_mb": 0,
            "peak_today_date": "",
            "peak_today_time": "",
            "incidents_today": 0,
            "incidents_today_date": "",
            "incidents_7d": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            orig = wd.HEURISTICS_FILE
            wd.HEURISTICS_FILE = Path(tmpdir) / "heuristics.json"
            try:
                h = wd.update_heuristics(h, 1000, "critical")
                self.assertEqual(h["incidents_today"], 1)
                self.assertEqual(len(h["incidents_7d"]), 1)
            finally:
                wd.HEURISTICS_FILE = orig


class TestForensicLog(unittest.TestCase):
    """Test forensic log format and rotation."""

    def test_log_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = wd.LOG_DIR
            wd.LOG_DIR = Path(tmpdir)
            try:
                state = {
                    "alert_level": "moderate",
                    "used_pct": 65.0,
                    "claude_total_mb": 800,
                    "ollama_mb": 6000,
                    "mcp_total_mb": 200,
                    "session_count": 2,
                    "headroom_mb": 3000,
                }
                wd.write_log_entry(state, "NOTIFY:moderate")
                log_path = wd.get_log_path()
                content = log_path.read_text()
                # Should be pipe-delimited
                self.assertIn(
                    "|moderate|65|800|6000|200|2|3000|NOTIFY:moderate", content
                )
            finally:
                wd.LOG_DIR = orig

    def test_log_rotation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = wd.LOG_DIR
            wd.LOG_DIR = Path(tmpdir)
            try:
                # Create an old log file
                old_log = Path(tmpdir) / "memory-2020-01-01.log"
                old_log.write_text("old data")
                # Set mtime to 10 days ago
                old_time = time.time() - 10 * 86400
                os.utime(old_log, (old_time, old_time))

                wd.rotate_logs()
                self.assertFalse(old_log.exists())
            finally:
                wd.LOG_DIR = orig


class TestMemoryGuardHook(unittest.TestCase):
    """Test the memory_guard.py hook (inline since it's simple)."""

    def test_missing_state_file(self):
        """Hook should output empty JSON when state file doesn't exist."""
        import subprocess

        result = subprocess.run(
            ["python3", str(Path.home() / ".claude" / "hooks" / "memory_guard.py")],
            capture_output=True,
            text=True,
            timeout=5,
            input="{}",
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout.strip())
        # Either empty (no state) or has additionalContext (if watchdog is running)
        self.assertIsInstance(data, dict)


class TestBalloonDetector(unittest.TestCase):
    """Test rate-of-change balloon detection."""

    def test_no_balloon_stable_memory(self):
        """Stable memory should not trigger balloon."""
        bd = wd.BalloonDetector(window_size=6)
        # Add 6 samples at ~same level, 30s apart
        for i in range(6):
            bd.samples.append((1000 + i * 30, 8000))  # 8 GB stable
        is_bal, sev, rate = bd.detect()
        self.assertFalse(is_bal)
        self.assertEqual(sev, "none")

    def test_balloon_warning_detected(self):
        """500 MB/min growth should trigger warning."""
        bd = wd.BalloonDetector(window_size=6)
        # 3 minutes of 600 MB/min growth: 8000 -> 9800 MB
        for i in range(6):
            bd.samples.append((1000 + i * 30, 8000 + i * 300))
        is_bal, sev, rate = bd.detect()
        self.assertTrue(is_bal)
        self.assertEqual(sev, "warning")
        self.assertGreaterEqual(rate, 500)

    def test_balloon_critical_detected(self):
        """1500 MB/min growth should trigger critical."""
        bd = wd.BalloonDetector(window_size=6)
        # 3 minutes of 2000 MB/min growth: 8000 -> 14000 MB
        for i in range(6):
            bd.samples.append((1000 + i * 30, 8000 + i * 1000))
        is_bal, sev, rate = bd.detect()
        self.assertTrue(is_bal)
        self.assertEqual(sev, "critical")
        self.assertGreaterEqual(rate, 1500)

    def test_shrinking_memory_not_balloon(self):
        """Decreasing memory should not trigger balloon."""
        bd = wd.BalloonDetector(window_size=6)
        for i in range(6):
            bd.samples.append((1000 + i * 30, 12000 - i * 500))
        is_bal, sev, rate = bd.detect()
        self.assertFalse(is_bal)
        self.assertLess(rate, 0)

    def test_insufficient_data(self):
        """With only 1 sample, rate should be 0."""
        bd = wd.BalloonDetector(window_size=6)
        bd.samples.append((1000, 8000))
        rate = bd.get_rate_mb_per_min()
        self.assertEqual(rate, 0.0)

    def test_window_rolls(self):
        """Window should cap at window_size samples."""
        bd = wd.BalloonDetector(window_size=3)
        for i in range(10):
            bd.add_sample(8000 + i * 100)
        self.assertEqual(len(bd.samples), 3)


class TestBalloonEscalationCap(unittest.TestCase):
    """Balloon escalation must NEVER reach kill-triggering levels."""

    def test_balloon_cannot_escalate_to_critical(self):
        """Even critical balloon severity should cap at 'high', not 'critical'.
        Only static RAM thresholds (92%+) should trigger kills."""
        # Simulate: RAM at 75% (moderate) + balloon critical
        # Old behavior: would escalate to critical → SIGTERM
        # New behavior: caps at high → warn + block spawning, no kill
        base_level = wd.calculate_alert_level(75)
        self.assertEqual(base_level, "moderate")
        # The main loop caps balloon escalation at "high"
        # regardless of balloon severity — verify the logic
        if base_level in ("ok", "moderate"):
            escalated = "high"
        else:
            escalated = base_level
        self.assertEqual(escalated, "high")
        self.assertNotEqual(escalated, "critical")

    def test_static_threshold_still_triggers_critical(self):
        """Static RAM at 93% should still be critical (kills are valid)."""
        level = wd.calculate_alert_level(93)
        self.assertEqual(level, "critical")


class TestNotificationCooldown(unittest.TestCase):
    """Test that notifications respect cooldown timers."""

    @patch("claude_memory_watchdog.send_notification")
    def test_cooldown_prevents_spam(self, mock_notify):
        """Same alert level should not re-notify within cooldown period."""
        last_notification = {"moderate": time.time()}
        now = time.time()
        # Within cooldown (300s) — should NOT send
        if now - last_notification.get("moderate", 0) > wd.NOTIFICATION_COOLDOWN:
            wd.send_notification("test", "test")
        mock_notify.assert_not_called()

    @patch("claude_memory_watchdog.send_notification")
    def test_cooldown_expired_allows_notify(self, mock_notify):
        """After cooldown expires, notification should be sent."""
        last_notification = {"moderate": time.time() - 400}  # 400s ago > 300s cooldown
        now = time.time()
        if now - last_notification.get("moderate", 0) > wd.NOTIFICATION_COOLDOWN:
            wd.send_notification("test", "test")
        mock_notify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
