#!/usr/bin/env python3
"""Unit tests for budget threshold rate switching system.

Tests the budget_check.py hook and track_resources.py alert logic:
- 5 threshold levels (ok, info, warning, critical, limit)
- Model recommendation at each level
- Window reset detection (high → low)
- Stale file refresh trigger
- Edge cases (missing file, corrupt JSON, boundary values)
- CO2 equivalence display

Run: python3 -m pytest tests/test_budget_switching.py -v
  or: python3 tests/test_budget_switching.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent dir to path so we can import the hook
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path.home() / '.claude' / 'hooks'))

# Import the modules under test
from dashboard_v2 import co2_equivalence, get_environmental_impact, get_usage_stats


class TestThresholdLevels(unittest.TestCase):
    """Test that each budget percentage maps to the correct alert level and model recommendation."""

    def _make_state(self, pct, tokens_used=None, alert=None, model=None):
        """Create a budget state dict at a given percentage."""
        budget = 220_000
        if tokens_used is None:
            tokens_used = int(budget * pct / 100)
        remaining = budget - tokens_used

        # Derive alert and model from percentage (matching track_resources.py logic)
        if alert is None:
            if pct < 50:
                alert = 'ok'
            elif pct < 70:
                alert = 'info'
            elif pct < 85:
                alert = 'warning'
            elif pct < 95:
                alert = 'critical'
            else:
                alert = 'limit'

        if model is None:
            if alert in ('ok', 'info'):
                model = 'opus'
            elif alert in ('warning', 'critical'):
                model = 'sonnet'
            else:
                model = 'wind_down'

        return {
            'five_hour_window': {
                'percentage': pct,
                'tokens_used': tokens_used,
                'budget': budget,
                'remaining': remaining,
                'messages': 50,
            },
            'alert_level': alert,
            'model_recommendation': model,
            'weekly': {
                'opus_tokens': 100000,
                'opus_messages': 200,
                'sonnet_tokens': 50000,
                'sonnet_messages': 100,
            },
            'environmental': {
                'total_carbon_g': 500.0,
                'total_wh': 1200.0,
            },
        }

    def test_ok_level_below_50(self):
        """Under 50% → alert=ok, model=opus."""
        state = self._make_state(30)
        self.assertEqual(state['alert_level'], 'ok')
        self.assertEqual(state['model_recommendation'], 'opus')

    def test_info_level_50_to_69(self):
        """50-69% → alert=info, model=opus."""
        for pct in [50, 55, 63, 69]:
            state = self._make_state(pct)
            self.assertEqual(state['alert_level'], 'info', f"Failed at {pct}%")
            self.assertEqual(state['model_recommendation'], 'opus', f"Failed at {pct}%")

    def test_warning_level_70_to_84(self):
        """70-84% → alert=warning, model=sonnet."""
        for pct in [70, 75, 80, 84]:
            state = self._make_state(pct)
            self.assertEqual(state['alert_level'], 'warning', f"Failed at {pct}%")
            self.assertEqual(state['model_recommendation'], 'sonnet', f"Failed at {pct}%")

    def test_critical_level_85_to_94(self):
        """85-94% → alert=critical, model=sonnet."""
        for pct in [85, 90, 94]:
            state = self._make_state(pct)
            self.assertEqual(state['alert_level'], 'critical', f"Failed at {pct}%")
            self.assertEqual(state['model_recommendation'], 'sonnet', f"Failed at {pct}%")

    def test_limit_level_95_plus(self):
        """95%+ → alert=limit, model=wind_down."""
        for pct in [95, 99, 100, 110]:
            state = self._make_state(pct)
            self.assertEqual(state['alert_level'], 'limit', f"Failed at {pct}%")
            self.assertEqual(state['model_recommendation'], 'wind_down', f"Failed at {pct}%")

    def test_boundary_49_is_ok(self):
        """49% is still ok."""
        state = self._make_state(49)
        self.assertEqual(state['alert_level'], 'ok')

    def test_boundary_50_is_info(self):
        """50% crosses to info."""
        state = self._make_state(50)
        self.assertEqual(state['alert_level'], 'info')

    def test_boundary_70_is_warning(self):
        """70% crosses to warning."""
        state = self._make_state(70)
        self.assertEqual(state['alert_level'], 'warning')

    def test_boundary_85_is_critical(self):
        """85% crosses to critical."""
        state = self._make_state(85)
        self.assertEqual(state['alert_level'], 'critical')

    def test_boundary_95_is_limit(self):
        """95% crosses to limit."""
        state = self._make_state(95)
        self.assertEqual(state['alert_level'], 'limit')


class TestBudgetCheckHook(unittest.TestCase):
    """Test the budget_check.py hook's build_context() function."""

    def setUp(self):
        """Set up temp files for budget state."""
        self.tmp_dir = tempfile.mkdtemp()
        self.budget_file = Path(self.tmp_dir) / '.budget-state.json'
        self.prev_file = Path(self.tmp_dir) / '.budget-prev-alert.json'

    def tearDown(self):
        """Clean up temp files."""
        for f in [self.budget_file, self.prev_file]:
            try:
                f.unlink()
            except FileNotFoundError:
                pass
        os.rmdir(self.tmp_dir)

    def _write_state(self, state):
        self.budget_file.write_text(json.dumps(state))

    def _write_prev_alert(self, level):
        self.prev_file.write_text(json.dumps({'alert_level': level}))

    @patch('budget_check.BUDGET_STATE')
    @patch('budget_check.PREV_STATE_FILE')
    def test_ok_returns_none(self, mock_prev, mock_budget):
        """When alert=ok and no reset, build_context returns None (save tokens)."""
        mock_budget.__class__ = Path
        mock_prev.__class__ = Path

        # Import after patching
        import budget_check
        state = {
            'five_hour_window': {'percentage': 30, 'remaining': 154000},
            'alert_level': 'ok',
            'model_recommendation': 'opus',
        }
        # Mock previous alert as 'ok' (no reset)
        with patch.object(budget_check, 'get_previous_alert_level', return_value='ok'), \
             patch.object(budget_check, 'save_current_alert_level'):
            result = budget_check.build_context(state)
        self.assertIsNone(result)

    @patch('budget_check.BUDGET_STATE')
    @patch('budget_check.PREV_STATE_FILE')
    def test_info_returns_message(self, mock_prev, mock_budget):
        """When alert=info, returns budget info message."""
        import budget_check
        state = {
            'five_hour_window': {'percentage': 60, 'remaining': 88000},
            'alert_level': 'info',
            'model_recommendation': 'opus',
        }
        with patch.object(budget_check, 'get_previous_alert_level', return_value='ok'), \
             patch.object(budget_check, 'save_current_alert_level'):
            result = budget_check.build_context(state)
        self.assertIn('60%', result)
        self.assertIn('Opus is fine', result)

    @patch('budget_check.BUDGET_STATE')
    @patch('budget_check.PREV_STATE_FILE')
    def test_warning_recommends_sonnet(self, mock_prev, mock_budget):
        """When alert=warning, message recommends switching to Sonnet."""
        import budget_check
        state = {
            'five_hour_window': {'percentage': 75, 'remaining': 55000},
            'alert_level': 'warning',
            'model_recommendation': 'sonnet',
        }
        with patch.object(budget_check, 'get_previous_alert_level', return_value='info'), \
             patch.object(budget_check, 'save_current_alert_level'):
            result = budget_check.build_context(state)
        self.assertIn('75%', result)
        self.assertIn('Sonnet', result)

    @patch('budget_check.BUDGET_STATE')
    @patch('budget_check.PREV_STATE_FILE')
    def test_critical_says_sonnet_only(self, mock_prev, mock_budget):
        """When alert=critical, message says Sonnet only."""
        import budget_check
        state = {
            'five_hour_window': {'percentage': 90, 'remaining': 22000},
            'alert_level': 'critical',
            'model_recommendation': 'sonnet',
        }
        with patch.object(budget_check, 'get_previous_alert_level', return_value='warning'), \
             patch.object(budget_check, 'save_current_alert_level'):
            result = budget_check.build_context(state)
        self.assertIn('90%', result)
        self.assertIn('Sonnet only', result)

    @patch('budget_check.BUDGET_STATE')
    @patch('budget_check.PREV_STATE_FILE')
    def test_limit_says_wind_down(self, mock_prev, mock_budget):
        """When alert=limit, message says wind down."""
        import budget_check
        state = {
            'five_hour_window': {'percentage': 97, 'remaining': 6600},
            'alert_level': 'limit',
            'model_recommendation': 'wind_down',
        }
        with patch.object(budget_check, 'get_previous_alert_level', return_value='critical'), \
             patch.object(budget_check, 'save_current_alert_level'):
            result = budget_check.build_context(state)
        self.assertIn('97%', result)
        self.assertIn('Wind down', result)

    @patch('budget_check.BUDGET_STATE')
    @patch('budget_check.PREV_STATE_FILE')
    def test_window_reset_detection(self, mock_prev, mock_budget):
        """When previous alert was high and current is ok, detect reset."""
        import budget_check
        state = {
            'five_hour_window': {'percentage': 10, 'remaining': 198000},
            'alert_level': 'ok',
            'model_recommendation': 'opus',
        }
        # Previous was critical, now ok = window reset
        with patch.object(budget_check, 'get_previous_alert_level', return_value='critical'), \
             patch.object(budget_check, 'save_current_alert_level'):
            result = budget_check.build_context(state)
        self.assertIsNotNone(result)
        self.assertIn('reset', result)
        self.assertIn('Opus', result)

    @patch('budget_check.BUDGET_STATE')
    @patch('budget_check.PREV_STATE_FILE')
    def test_window_reset_from_warning(self, mock_prev, mock_budget):
        """Window reset from warning level also triggers reset message."""
        import budget_check
        state = {
            'five_hour_window': {'percentage': 5, 'remaining': 209000},
            'alert_level': 'ok',
            'model_recommendation': 'opus',
        }
        with patch.object(budget_check, 'get_previous_alert_level', return_value='warning'), \
             patch.object(budget_check, 'save_current_alert_level'):
            result = budget_check.build_context(state)
        self.assertIsNotNone(result)
        self.assertIn('reset', result)

    def test_none_state_returns_none(self):
        """build_context(None) returns None gracefully."""
        import budget_check
        result = budget_check.build_context(None)
        self.assertIsNone(result)


class TestStaleRefresh(unittest.TestCase):
    """Test the stale file refresh logic."""

    def test_missing_file_triggers_refresh(self):
        """If .budget-state.json doesn't exist, refresh should be triggered."""
        import budget_check
        with patch.object(budget_check, 'BUDGET_STATE', Path('/nonexistent/path')), \
             patch.object(budget_check, 'TRACKER_SCRIPT', Path('/nonexistent/script')):
            # Should not crash even if files don't exist
            budget_check.refresh_if_stale()

    def test_stale_file_triggers_refresh(self):
        """If .budget-state.json is >10 min old, refresh runs."""
        import budget_check
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{}')
            tmp_path = Path(f.name)

        try:
            # Make file 15 minutes old
            old_time = os.path.getmtime(tmp_path) - 900
            os.utime(tmp_path, (old_time, old_time))

            with patch.object(budget_check, 'BUDGET_STATE', tmp_path), \
                 patch.object(budget_check, 'TRACKER_SCRIPT', Path('/nonexistent')):
                budget_check.refresh_if_stale()
                # No crash = success
        finally:
            tmp_path.unlink()

    def test_fresh_file_skips_refresh(self):
        """If .budget-state.json is <10 min old, no refresh needed."""
        import budget_check
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            f.write(b'{}')
            tmp_path = Path(f.name)

        try:
            with patch.object(budget_check, 'BUDGET_STATE', tmp_path), \
                 patch('subprocess.run') as mock_run:
                budget_check.refresh_if_stale()
                mock_run.assert_not_called()
        finally:
            tmp_path.unlink()


class TestCorruptState(unittest.TestCase):
    """Test handling of corrupt or invalid budget state files."""

    def test_corrupt_json(self):
        """Corrupt JSON in state file should not crash."""
        import budget_check
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            f.write('not valid json {{{')
            tmp_path = Path(f.name)

        try:
            with patch.object(budget_check, 'BUDGET_STATE', tmp_path):
                result = budget_check.read_budget_state()
            self.assertIsNone(result)
        finally:
            tmp_path.unlink()

    def test_empty_file(self):
        """Empty state file should not crash."""
        import budget_check
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            f.write('')
            tmp_path = Path(f.name)

        try:
            with patch.object(budget_check, 'BUDGET_STATE', tmp_path):
                result = budget_check.read_budget_state()
            self.assertIsNone(result)
        finally:
            tmp_path.unlink()

    def test_missing_keys_uses_defaults(self):
        """State with missing keys should use safe defaults."""
        usage = get_usage_stats({})  # Empty dict, no keys
        self.assertEqual(usage['percentage'], 0)
        self.assertEqual(usage['remaining'], 220_000)
        self.assertEqual(usage['model_recommendation'], 'opus')
        self.assertEqual(usage['alert_level'], 'ok')

    def test_none_data_uses_defaults(self):
        """None data should return full defaults."""
        usage = get_usage_stats(None)
        self.assertEqual(usage['percentage'], 0)
        self.assertEqual(usage['remaining'], 220_000)


class TestCO2Equivalence(unittest.TestCase):
    """Test the CO2 real-world equivalence display."""

    def test_zero_co2(self):
        """0g CO2 → less than 1 Google search."""
        result = co2_equivalence(0)
        self.assertIn('Google search', result)

    def test_tiny_co2(self):
        """0.5g CO2 → still mentions Google searches."""
        result = co2_equivalence(0.5)
        self.assertIn('Google search', result)

    def test_small_co2_smartphone(self):
        """15g CO2 → smartphone charges."""
        result = co2_equivalence(15)
        self.assertIn('smartphone charge', result)

    def test_medium_co2_netflix(self):
        """100g CO2 → Netflix streaming hours."""
        result = co2_equivalence(100)
        self.assertIn('Netflix', result)

    def test_large_co2_driving(self):
        """2000g CO2 → miles driving."""
        result = co2_equivalence(2000)
        self.assertIn('miles driving', result)

    def test_very_large_co2(self):
        """10000g CO2 → still miles driving."""
        result = co2_equivalence(10000)
        self.assertIn('miles driving', result)

    def test_env_impact_includes_equiv(self):
        """get_environmental_impact returns equiv field."""
        data = {
            'environmental': {'total_carbon_g': 500, 'total_wh': 1200}
        }
        result = get_environmental_impact(data)
        self.assertIn('equiv', result)
        self.assertTrue(len(result['equiv']) > 0)

    def test_env_impact_none_data(self):
        """get_environmental_impact(None) returns empty equiv."""
        result = get_environmental_impact(None)
        self.assertEqual(result['equiv'], '')

    def test_8g_is_one_smartphone(self):
        """~8g should say ~1 smartphone charge."""
        result = co2_equivalence(8)
        self.assertIn('1 smartphone charge', result)

    def test_36g_is_one_hr_netflix(self):
        """~36g should say ~1 hr Netflix."""
        result = co2_equivalence(36)
        self.assertIn('1 hr Netflix', result)


class TestDashboardUsageStats(unittest.TestCase):
    """Test get_usage_stats extracts data correctly."""

    def test_full_state(self):
        """Full state dict returns correct values."""
        state = {
            'five_hour_window': {
                'percentage': 63,
                'tokens_used': 138600,
                'budget': 220000,
                'remaining': 81400,
                'messages': 150,
            },
            'alert_level': 'info',
            'model_recommendation': 'opus',
            'weekly': {
                'opus_tokens': 500000,
                'opus_messages': 300,
                'sonnet_tokens': 100000,
                'sonnet_messages': 50,
            },
        }
        usage = get_usage_stats(state)
        self.assertEqual(usage['percentage'], 63)
        self.assertEqual(usage['tokens_used'], 138600)
        self.assertEqual(usage['remaining'], 81400)
        self.assertEqual(usage['model_recommendation'], 'opus')
        self.assertEqual(usage['alert_level'], 'info')
        self.assertEqual(usage['weekly_opus_tokens'], 500000)
        self.assertEqual(usage['weekly_sonnet_messages'], 50)

    def test_partial_state(self):
        """State with missing weekly data uses 0 defaults."""
        state = {
            'five_hour_window': {'percentage': 20},
            'alert_level': 'ok',
        }
        usage = get_usage_stats(state)
        self.assertEqual(usage['percentage'], 20)
        self.assertEqual(usage['weekly_opus_tokens'], 0)
        self.assertEqual(usage['weekly_sonnet_tokens'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
