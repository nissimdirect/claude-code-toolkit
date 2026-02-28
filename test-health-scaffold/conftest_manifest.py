"""
conftest_manifest.py — Reusable pytest manifest plugin for test health tracking.

USAGE:
    1. Copy this file into your project root (next to conftest.py) or merge
       its contents into your existing conftest.py.
    2. Run pytest as usual. After each session, the plugin will:
       - Write .test-manifest.json (current test state snapshot)
       - Append session summary to .test-results/history.jsonl
       - Append per-test durations to .test-results/per_test.jsonl
    3. Use check_tests.sh to skip re-runs when tests are green.
    4. Use test_health.py for dashboards, flaky detection, and slow test reports.

FILES PRODUCED:
    .test-manifest.json          — Single-run snapshot (commit, branch, pass/fail, duration)
    .test-results/history.jsonl  — Append-only session history (auto-rotated at 500 lines)
    .test-results/per_test.jsonl — Append-only per-test durations (auto-rotated at 50000 lines)

REQUIREMENTS:
    - Python 3.8+
    - pytest
    - git (for commit SHA and branch detection)
"""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ──────────────────────────────────────────────────────────────────────
# State accumulated across the session
# ──────────────────────────────────────────────────────────────────────

_session_state = {
    "start_time": None,
    "passed": 0,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "per_test": [],  # list of {"name": str, "duration": float, "outcome": str}
}

HISTORY_MAX_LINES = 500
PER_TEST_MAX_LINES = 50000
MAX_AGE_HOURS = 24
RESULTS_DIR = ".test-results"
MANIFEST_FILE = ".test-manifest.json"


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _git_value(*args: str) -> str:
    """Run a git command and return stripped stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def _rotate_jsonl(path: Path, max_lines: int) -> None:
    """If *path* exceeds *max_lines*, trim to the last *max_lines* entries."""
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > max_lines:
        path.write_text(
            "\n".join(lines[-max_lines:]) + "\n",
            encoding="utf-8",
        )


# ──────────────────────────────────────────────────────────────────────
# Pytest hooks
# ──────────────────────────────────────────────────────────────────────


def pytest_sessionstart(session):
    """Record the wall-clock start time."""
    _session_state["start_time"] = time.monotonic()
    _session_state["passed"] = 0
    _session_state["failed"] = 0
    _session_state["errors"] = 0
    _session_state["skipped"] = 0
    _session_state["per_test"] = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Count outcomes and record per-test durations."""
    outcome = yield
    report = outcome.get_result()

    # We only care about the "call" phase for pass/fail,
    # "setup"/"teardown" for errors, and "setup" for skips.
    if report.when == "call":
        if report.passed:
            _session_state["passed"] += 1
            test_outcome = "passed"
        elif report.failed:
            _session_state["failed"] += 1
            test_outcome = "failed"
        else:
            # xfail / xpass etc. — count as passed
            _session_state["passed"] += 1
            test_outcome = "passed"

        _session_state["per_test"].append(
            {
                "name": item.nodeid,
                "duration": report.duration,
                "outcome": test_outcome,
            }
        )
    elif report.when == "setup" and report.skipped:
        _session_state["skipped"] += 1
        _session_state["per_test"].append(
            {
                "name": item.nodeid,
                "duration": report.duration,
                "outcome": "skipped",
            }
        )
    elif report.when in ("setup", "teardown") and report.failed:
        _session_state["errors"] += 1
        _session_state["per_test"].append(
            {
                "name": item.nodeid,
                "duration": report.duration,
                "outcome": "error",
            }
        )


def pytest_sessionfinish(session, exitstatus):
    """Write manifest, append JSONL history, and auto-rotate."""
    if _session_state["start_time"] is None:
        return  # safety: sessionstart never fired

    duration_seconds = round(time.monotonic() - _session_state["start_time"], 3)
    commit_sha = _git_value("rev-parse", "HEAD")
    branch = _git_value("rev-parse", "--abbrev-ref", "HEAD")
    timestamp = datetime.now(timezone.utc).isoformat()
    green = _session_state["failed"] == 0 and _session_state["errors"] == 0

    manifest = {
        "commit_sha": commit_sha,
        "branch": branch,
        "timestamp": timestamp,
        "max_age_hours": MAX_AGE_HOURS,
        "passed": _session_state["passed"],
        "failed": _session_state["failed"],
        "errors": _session_state["errors"],
        "skipped": _session_state["skipped"],
        "duration_seconds": duration_seconds,
        "green": green,
        "framework": "pytest",
    }

    root = Path.cwd()
    results_dir = root / RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)

    # ── Write .test-manifest.json ──
    manifest_path = root / MANIFEST_FILE
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    # ── Append to history.jsonl ──
    history_path = results_dir / "history.jsonl"
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(manifest) + "\n")

    # ── Append per-test durations to per_test.jsonl ──
    per_test_path = results_dir / "per_test.jsonl"
    with per_test_path.open("a", encoding="utf-8") as f:
        for entry in _session_state["per_test"]:
            record = {
                "timestamp": timestamp,
                "commit_sha": commit_sha,
                "name": entry["name"],
                "duration": entry["duration"],
                "outcome": entry["outcome"],
            }
            f.write(json.dumps(record) + "\n")

    # ── Auto-rotate ──
    _rotate_jsonl(history_path, HISTORY_MAX_LINES)
    _rotate_jsonl(per_test_path, PER_TEST_MAX_LINES)
