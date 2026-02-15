#!/usr/bin/env python3
"""Web Dashboard — Flask server for Claude Code dashboard.

Replaces terminal dashboard (dashboard_v2.py) with a browser-based version.
Reads ALL KB sources dynamically from data-sources.json.

Usage: python3 app.py
Opens: http://localhost:5050
"""

import json
import os
import sys
import time
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, render_template

# Add parent dir so we can import data_loader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_loader import (
    get_all_dashboard_data,
    get_knowledge_base_stats,
    refresh_budget_data,
)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

PORT = 5050
LOCKFILE = Path.home() / ".claude/.locks/dashboard_web.pid"

# Server-side response cache
_response_cache = {}
_response_cache_time = {}
RESPONSE_CACHE_TTL = {
    "all_data": 0.5,   # 500ms
    "kb_data": 60,      # 60s
}


def _cached_response(key, loader, ttl=None):
    """Cache JSON responses server-side."""
    if ttl is None:
        ttl = RESPONSE_CACHE_TTL.get(key, 1)
    now = time.time()
    if key in _response_cache and (now - _response_cache_time.get(key, 0)) < ttl:
        return _response_cache[key]
    result = loader()
    _response_cache[key] = result
    _response_cache_time[key] = now
    return result


# === ROUTES ===

@app.route("/")
def index():
    """Serve the dashboard HTML."""
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    """Return all dashboard data as JSON (cached 500ms)."""
    data = _cached_response("all_data", get_all_dashboard_data, ttl=0.5)
    return jsonify(data)


@app.route("/api/kb")
def api_kb():
    """Return KB stats only (cached 60s)."""
    def _load_kb():
        stats, total, by_skill = get_knowledge_base_stats()
        return {
            "stats": stats,
            "total": total,
            "by_skill": by_skill,
            "source_count": len(stats),
        }
    data = _cached_response("kb_data", _load_kb, ttl=60)
    return jsonify(data)


@app.route("/api/refresh")
def api_refresh():
    """Trigger track_resources.py run, return status."""
    success = refresh_budget_data()
    # Clear cache so next poll gets fresh data
    _response_cache.pop("all_data", None)
    return jsonify({"refreshed": success})


# === LIFECYCLE ===

def _acquire_lock():
    """Acquire PID lockfile. Returns True if acquired.

    Uses lsof to check if port is already bound (reliable regardless of
    how the process was started — fixes pgrep pattern mismatch bug).
    """
    import subprocess
    LOCKFILE.parent.mkdir(parents=True, exist_ok=True)

    # Check 1: Is port already in use?
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{PORT}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [int(p) for p in result.stdout.strip().split("\n") if p.strip()]
        other_pids = [p for p in pids if p != os.getpid()]
        if other_pids:
            LOCKFILE.write_text(str(other_pids[0]))
            return False
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass

    # Check 2: Lockfile PID still alive?
    if LOCKFILE.exists():
        try:
            old_pid = int(LOCKFILE.read_text().strip())
            os.kill(old_pid, 0)
            return False
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass  # Stale lockfile

    LOCKFILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    """Release PID lockfile."""
    try:
        if LOCKFILE.exists() and LOCKFILE.read_text().strip() == str(os.getpid()):
            LOCKFILE.unlink()
    except OSError:
        pass


def open_browser():
    """Open browser after Flask starts."""
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    if not _acquire_lock():
        print(f"Web dashboard already running. Open http://localhost:{PORT}")
        print(f"Lock file: {LOCKFILE}")
        webbrowser.open(f"http://localhost:{PORT}")
        sys.exit(0)

    try:
        # Refresh budget data on launch
        refresh_budget_data()

        # Open browser after 1.5s delay (let Flask start)
        Timer(1.5, open_browser).start()

        print(f"Dashboard starting at http://localhost:{PORT}")
        app.run(host="127.0.0.1", port=PORT, debug=False)
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        _release_lock()
