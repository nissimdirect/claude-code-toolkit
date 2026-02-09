#!/usr/bin/env python3
"""Budget check hook for Claude Code — UserPromptSubmit

Reads .budget-state.json (written by track_resources.py) and injects
budget context into every conversation via additionalContext.

If the JSON is stale (>10 min), refreshes it by running track_resources.py.
Must complete in <5 seconds (hook timeout).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

BUDGET_STATE = Path.home() / '.claude' / '.locks' / '.budget-state.json'
TRACKER_SCRIPT = Path.home() / 'Development' / 'tools' / 'track_resources.py'
PREV_STATE_FILE = Path.home() / '.claude' / '.locks' / '.budget-prev-alert.json'
STALE_THRESHOLD_SEC = 600  # 10 minutes


def read_budget_state():
    """Read the budget state JSON. Returns dict or None."""
    if not BUDGET_STATE.exists():
        return None
    try:
        return json.loads(BUDGET_STATE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def refresh_if_stale():
    """If budget state is stale or missing, run track_resources.py to refresh.

    Runs with a 4-second timeout to stay within hook limits.
    """
    needs_refresh = False

    if not BUDGET_STATE.exists():
        needs_refresh = True
    else:
        try:
            age = time.time() - BUDGET_STATE.stat().st_mtime
            if age > STALE_THRESHOLD_SEC:
                needs_refresh = True
        except OSError:
            needs_refresh = True

    if needs_refresh and TRACKER_SCRIPT.exists():
        try:
            subprocess.run(
                [sys.executable, str(TRACKER_SCRIPT)],
                timeout=4,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass


def get_previous_alert_level():
    """Read the previous alert level for window-reset detection."""
    if not PREV_STATE_FILE.exists():
        return 'ok'
    try:
        data = json.loads(PREV_STATE_FILE.read_text())
        return data.get('alert_level', 'ok')
    except (json.JSONDecodeError, OSError):
        return 'ok'


def save_current_alert_level(alert_level):
    """Save current alert level for next invocation comparison."""
    try:
        PREV_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        PREV_STATE_FILE.write_text(json.dumps({'alert_level': alert_level}))
    except OSError:
        pass


def build_context(state):
    """Build the additionalContext string based on budget thresholds."""
    if state is None:
        return None

    window = state.get('five_hour_window', {})
    pct = window.get('percentage', 0)
    remaining = window.get('remaining', 0)
    alert_level = state.get('alert_level', 'ok')
    model_rec = state.get('model_recommendation', 'opus')

    # Check for window reset (was high, now low)
    prev_level = get_previous_alert_level()
    save_current_alert_level(alert_level)

    prev_was_high = prev_level in ('warning', 'critical', 'limit')
    current_is_low = alert_level == 'ok'

    if prev_was_high and current_is_low:
        return (
            f"[Budget] 5-hour window has reset ({pct:.0f}% used). "
            "Safe to use Opus again."
        )

    # Threshold-based messages
    if alert_level == 'ok':
        # Don't waste context when budget is fine
        return None
    elif alert_level == 'info':
        return (
            f"[Budget] 5-hour window at {pct:.0f}% "
            f"({remaining:,} tokens remaining). Opus is fine for now."
        )
    elif alert_level == 'warning':
        return (
            f"[Budget] 5-hour window at {pct:.0f}% "
            f"({remaining:,} tokens remaining). "
            "Consider switching to Sonnet (/model sonnet) for routine tasks."
        )
    elif alert_level == 'critical':
        return (
            f"[Budget] 5-hour window at {pct:.0f}%! "
            f"Only {remaining:,} tokens remaining. "
            "Use Sonnet only. Save Opus for critical work."
        )
    elif alert_level == 'limit':
        return (
            f"[Budget] 5-hour window at {pct:.0f}%! "
            "Wind down immediately. Close background agents. "
            "New prompts may be blocked until window resets."
        )

    return None


def main():
    """Hook entry point. Reads stdin (hook event), writes JSON to stdout."""
    # Read hook event from stdin (required by Claude Code hook protocol)
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        event = {}

    # Refresh budget state if stale
    refresh_if_stale()

    # Read current state
    state = read_budget_state()

    # Build context message
    context = build_context(state)

    # Output hook response
    response = {}
    if context:
        response['additionalContext'] = context

    print(json.dumps(response))


if __name__ == '__main__':
    main()
