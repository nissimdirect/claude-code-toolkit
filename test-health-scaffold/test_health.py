#!/usr/bin/env python3
"""
test_health.py — Framework-agnostic test health dashboard.

USAGE:
    Copy this script into your project root (next to .test-manifest.json).

    python test_health.py           # Last 20 runs: pass rate, duration trend
    python test_health.py --slow    # Top 10 slowest tests (by avg duration)
    python test_health.py --flaky   # Tests with mixed outcomes across runs
    python test_health.py --rotate  # Trim JSONL files to retention limits

READS:
    .test-manifest.json          — Current test state snapshot
    .test-results/history.jsonl  — Session-level history
    .test-results/per_test.jsonl — Per-test durations and outcomes

REQUIREMENTS:
    Python 3.8+ (stdlib only — no third-party deps)
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(".test-results")
MANIFEST_FILE = Path(".test-manifest.json")
HISTORY_FILE = RESULTS_DIR / "history.jsonl"
PER_TEST_FILE = RESULTS_DIR / "per_test.jsonl"

HISTORY_MAX_LINES = 500
PER_TEST_MAX_LINES = 50000


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file and return a list of dicts. Skip malformed lines."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _rotate_jsonl(path: Path, max_lines: int) -> int:
    """Trim *path* to the last *max_lines* entries. Return lines removed."""
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= max_lines:
        return 0
    removed = len(lines) - max_lines
    path.write_text(
        "\n".join(lines[-max_lines:]) + "\n",
        encoding="utf-8",
    )
    return removed


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable string."""
    if seconds < 1.0:
        return f"{seconds * 1000:.0f}ms"
    if seconds < 60.0:
        return f"{seconds:.2f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def _trend_arrow(values: list[float]) -> str:
    """Return an ASCII arrow showing trend direction for the last few values."""
    if len(values) < 2:
        return "  "
    recent = values[-3:] if len(values) >= 3 else values
    delta = recent[-1] - recent[0]
    if abs(delta) < 0.01:
        return "--"
    return "/\\" if delta > 0 else "\\/"


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse an ISO 8601 timestamp string."""
    try:
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, AttributeError):
        return None


# ──────────────────────────────────────────────────────────────────────
# Modes
# ──────────────────────────────────────────────────────────────────────


def mode_default():
    """Show last 20 runs from history.jsonl with pass rate, duration, and trend."""
    entries = _read_jsonl(HISTORY_FILE)
    if not entries:
        print("No test history found. Run your tests first to generate data.")
        return

    last_20 = entries[-20:]

    # Header
    print()
    print("TEST HEALTH — Last {} runs".format(len(last_20)))
    print("=" * 72)
    print(
        f"{'#':>3}  {'Timestamp':<20}  {'Pass':>5}  {'Fail':>5}  {'Err':>4}  "
        f"{'Skip':>5}  {'Duration':>10}  {'Status':>6}"
    )
    print("-" * 72)

    durations = []
    pass_rates = []

    for i, entry in enumerate(last_20, 1):
        passed = entry.get("passed", 0)
        failed = entry.get("failed", 0)
        errors = entry.get("errors", 0)
        skipped = entry.get("skipped", 0)
        duration = entry.get("duration_seconds", 0)
        green = entry.get("green", False)
        ts = entry.get("timestamp", "")

        total = passed + failed + errors
        rate = (passed / total * 100) if total > 0 else 0.0
        pass_rates.append(rate)
        durations.append(duration)

        # Format timestamp to something readable
        dt = _parse_timestamp(ts)
        ts_display = dt.strftime("%Y-%m-%d %H:%M") if dt else ts[:19]

        status = "GREEN" if green else "RED"

        print(
            f"{i:>3}  {ts_display:<20}  {passed:>5}  {failed:>5}  {errors:>4}  "
            f"{skipped:>5}  {_format_duration(duration):>10}  {status:>6}"
        )

    # Summary
    print("-" * 72)
    avg_duration = sum(durations) / len(durations) if durations else 0
    avg_pass_rate = sum(pass_rates) / len(pass_rates) if pass_rates else 0
    duration_trend = _trend_arrow(durations)
    pass_trend = _trend_arrow(pass_rates)

    print(f"  Avg pass rate: {avg_pass_rate:.1f}%  {pass_trend}")
    print(f"  Avg duration:  {_format_duration(avg_duration)}  {duration_trend}")

    # Current manifest status
    if MANIFEST_FILE.exists():
        manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        sha = manifest.get("commit_sha", "")[:8]
        branch = manifest.get("branch", "?")
        green = manifest.get("green", False)
        print(f"\n  Current: {'GREEN' if green else 'RED'} @ {sha} on {branch}")
    print()


def mode_slow():
    """Show top 10 slowest tests by average duration."""
    entries = _read_jsonl(PER_TEST_FILE)
    if not entries:
        print("No per-test data found. Run your tests first to generate data.")
        return

    # Group by test name, collect durations (exclude skipped)
    durations_by_test: dict[str, list[float]] = defaultdict(list)
    for entry in entries:
        outcome = entry.get("outcome", "")
        if outcome == "skipped":
            continue
        name = entry.get("name", "")
        dur = entry.get("duration", 0)
        if name:
            durations_by_test[name].append(dur)

    if not durations_by_test:
        print("No test duration data found.")
        return

    # Sort by average duration, descending
    ranked = sorted(
        durations_by_test.items(),
        key=lambda kv: sum(kv[1]) / len(kv[1]),
        reverse=True,
    )[:10]

    print()
    print("SLOWEST TESTS — Top 10 by avg duration")
    print("=" * 80)
    print(f"{'#':>3}  {'Avg':>10}  {'Max':>10}  {'Runs':>5}  {'Test'}")
    print("-" * 80)

    for i, (name, durs) in enumerate(ranked, 1):
        avg_d = sum(durs) / len(durs)
        max_d = max(durs)
        print(
            f"{i:>3}  {_format_duration(avg_d):>10}  {_format_duration(max_d):>10}  "
            f"{len(durs):>5}  {name}"
        )

    print()


def mode_flaky():
    """Find tests that have both passed and failed across runs."""
    entries = _read_jsonl(PER_TEST_FILE)
    if not entries:
        print("No per-test data found. Run your tests first to generate data.")
        return

    # Group outcomes by test name
    outcomes_by_test: dict[str, set[str]] = defaultdict(set)
    counts_by_test: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for entry in entries:
        name = entry.get("name", "")
        outcome = entry.get("outcome", "")
        if name and outcome:
            outcomes_by_test[name].add(outcome)
            counts_by_test[name][outcome] += 1

    # Find tests with mixed pass/fail outcomes
    flaky_tests = []
    for name, outcomes in outcomes_by_test.items():
        has_pass = "passed" in outcomes
        has_fail = "failed" in outcomes or "error" in outcomes
        if has_pass and has_fail:
            total = sum(counts_by_test[name].values())
            fail_count = counts_by_test[name].get("failed", 0) + counts_by_test[
                name
            ].get("error", 0)
            pass_count = counts_by_test[name].get("passed", 0)
            flaky_rate = fail_count / total * 100 if total > 0 else 0
            flaky_tests.append((name, pass_count, fail_count, total, flaky_rate))

    if not flaky_tests:
        print("No flaky tests detected. All tests have consistent outcomes.")
        return

    # Sort by flaky rate descending
    flaky_tests.sort(key=lambda x: x[4], reverse=True)

    print()
    print(f"FLAKY TESTS — {len(flaky_tests)} tests with mixed outcomes")
    print("=" * 80)
    print(f"{'#':>3}  {'Pass':>6}  {'Fail':>6}  {'Total':>6}  {'Flaky%':>7}  {'Test'}")
    print("-" * 80)

    for i, (name, pass_c, fail_c, total, rate) in enumerate(flaky_tests, 1):
        print(f"{i:>3}  {pass_c:>6}  {fail_c:>6}  {total:>6}  {rate:>6.1f}%  {name}")

    print()


def mode_rotate():
    """Trim JSONL files to retention limits."""
    h_removed = _rotate_jsonl(HISTORY_FILE, HISTORY_MAX_LINES)
    p_removed = _rotate_jsonl(PER_TEST_FILE, PER_TEST_MAX_LINES)

    print(f"history.jsonl:  trimmed {h_removed} lines (limit: {HISTORY_MAX_LINES})")
    print(f"per_test.jsonl: trimmed {p_removed} lines (limit: {PER_TEST_MAX_LINES})")

    if h_removed == 0 and p_removed == 0:
        print("Both files are within limits. Nothing to trim.")


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Test health dashboard. Reads .test-manifest.json and .test-results/ JSONL files.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--slow",
        action="store_true",
        help="Top 10 slowest tests by average duration",
    )
    group.add_argument(
        "--flaky",
        action="store_true",
        help="Tests with mixed pass/fail outcomes across runs",
    )
    group.add_argument(
        "--rotate",
        action="store_true",
        help="Trim JSONL files to retention limits",
    )

    args = parser.parse_args()

    if args.slow:
        mode_slow()
    elif args.flaky:
        mode_flaky()
    elif args.rotate:
        mode_rotate()
    else:
        mode_default()


if __name__ == "__main__":
    main()
