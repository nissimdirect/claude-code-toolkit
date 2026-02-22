"""Regression tests for flywheel_tracker.py.

Validates measurements against known ground truth to catch the class of bug
where a measurement silently returns 0 due to wrong patterns, paths, or keys.

Run with: python3 -m pytest tests/test_flywheel_tracker.py -v
From:      ~/Development/tools/
"""

import sys
from pathlib import Path

# Add parent to path so we can import flywheel_tracker
sys.path.insert(0, str(Path(__file__).parent.parent))
import flywheel_tracker


class TestMeasurementGroundTruth:
    """Verify measurements against known minimums.

    These minimums are conservative — well below actual values.
    If any drops below, it's almost certainly a measurement bug.
    """

    def test_learnings_above_minimum(self):
        """We have 150+ learnings. If this returns < 100, measurement is broken."""
        count = flywheel_tracker._count_learnings()
        assert count >= 100, (
            f"_count_learnings() returned {count}, expected >= 100. "
            "Check regex pattern against actual learnings.md format."
        )

    def test_kb_articles_above_minimum(self):
        """We have 87K+ articles. If this returns < 50K, measurement is broken."""
        count = flywheel_tracker._kb_article_count()
        assert count >= 50000, (
            f"_kb_article_count() returned {count}, expected >= 50000. "
            "Check directory scanning logic and skip list."
        )

    def test_graduated_learnings_above_minimum(self):
        """We have 19+ graduated. If this returns 0, measurement is broken."""
        count = flywheel_tracker._count_graduated()
        assert count >= 5, (
            f"_count_graduated() returned {count}, expected >= 5. "
            "Check counting logic against learnings.md format."
        )


class TestMeasureAllLoops:
    """Integration tests for the full measurement pipeline."""

    def setup_method(self):
        self.loops = flywheel_tracker.measure_all_loops()

    def test_all_10_loops_present(self):
        """All 10 loops must be measured."""
        assert len(self.loops) == 10
        for i in range(1, 11):
            assert str(i) in self.loops, f"Loop {i} missing from measurement"

    def test_required_fields_present(self):
        """Each loop must have the required schema fields."""
        required = {
            "name",
            "spinning",
            "instrumented",
            "metric_name",
            "metric_value",
            "trend",
            "detail",
        }
        for num, loop in self.loops.items():
            missing = required - set(loop.keys())
            assert not missing, f"Loop {num} missing fields: {missing}"

    def test_no_spinning_loop_has_zero_metric(self):
        """If a loop is 'spinning', its metric_value should not be 0.

        Catches the case where 'spinning' is hardcoded True but measurement failed.
        Exception: Loop 4 (budget) can legitimately be 0% at start of billing cycle.
        """
        for num, loop in self.loops.items():
            if loop["spinning"] and num != "4":
                assert loop["metric_value"] != 0, (
                    f"Loop {num} ({loop['name']}) is marked spinning but "
                    f"metric_value is 0. Likely a measurement bug."
                )

    def test_all_loops_instrumented(self):
        """All 10 loops should be instrumented (we achieved 10/10)."""
        instrumented = sum(1 for l in self.loops.values() if l["instrumented"])
        assert instrumented == 10, (
            f"Only {instrumented}/10 loops instrumented. "
            "Check Loop 9 (Sentry) and Loop 10 (Playwright) detection."
        )


class TestVerify:
    """Test the self-verification function."""

    def test_verify_returns_no_warnings_on_real_data(self):
        """verify() should find no warnings when run against real data."""
        loops = flywheel_tracker.measure_all_loops()
        warnings = flywheel_tracker.verify(loops)
        assert warnings == [], "verify() found warnings on real data:\n" + "\n".join(
            warnings
        )

    def test_verify_catches_silent_zero(self):
        """verify() should warn when a data source exists but measurement is 0."""
        loops = flywheel_tracker.measure_all_loops()
        # Simulate a broken measurement by setting metric_value to 0
        loops["1"]["metric_value"] = 0
        warnings = flywheel_tracker.verify(loops)
        assert any("Loop 1" in w for w in warnings), (
            "verify() should warn when Loop 1 source exists but metric is 0"
        )


class TestTrend:
    """Unit tests for trend calculation."""

    def test_trend_up(self):
        assert flywheel_tracker._trend(100, 50) == "up"

    def test_trend_down(self):
        assert flywheel_tracker._trend(50, 100) == "down"

    def test_trend_flat(self):
        assert flywheel_tracker._trend(100, 99) == "flat"

    def test_trend_new(self):
        assert flywheel_tracker._trend(100, 0) == "new"


class TestDataSourceReading:
    """Verify individual data source readers don't crash and return sane types."""

    def test_count_learnings_returns_int(self):
        result = flywheel_tracker._count_learnings()
        assert isinstance(result, int)

    def test_kb_article_count_returns_int(self):
        result = flywheel_tracker._kb_article_count()
        assert isinstance(result, int)

    def test_delegation_stats_returns_dict(self):
        result = flywheel_tracker._delegation_stats()
        assert isinstance(result, dict)

    def test_budget_state_returns_dict(self):
        result = flywheel_tracker._budget_state()
        assert isinstance(result, dict)

    def test_handoff_count_returns_int(self):
        result = flywheel_tracker._handoff_count()
        assert isinstance(result, int)

    def test_compound_doc_count_returns_int(self):
        result = flywheel_tracker._compound_doc_count()
        assert isinstance(result, int)

    def test_active_tasks_returns_tuple(self):
        shipped, total = flywheel_tracker._active_tasks_shipped_ratio()
        assert isinstance(shipped, int)
        assert isinstance(total, int)
        assert shipped <= total
