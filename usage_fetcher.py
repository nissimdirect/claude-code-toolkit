#!/usr/bin/env python3
"""Shared usage fetcher library for Claude Code statusline.

All OAuth token retrieval, API fetching, caching, backoff, and atomic write
logic lives here. Imported by both the daemon and the PostToolUse hook.

Cache file: ~/.claude/.locks/usage-state.json
"""

import fcntl
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

CACHE_PATH = Path.home() / ".claude" / ".locks" / "usage-state.json"
USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"

# Backoff constants
BACKOFF_BASE_SECONDS = 60
BACKOFF_MAX_SECONDS = 600


def get_oauth_token():
    """Read Claude Code OAuth token from macOS Keychain. Returns str or None."""
    try:
        result = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                "Claude Code-credentials",
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            creds = json.loads(result.stdout.strip())
            return creds.get("claudeAiOauth", {}).get("accessToken")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


def read_cache():
    """Read and parse usage-state.json. Returns dict or None."""
    try:
        if not CACHE_PATH.exists():
            return None
        with open(CACHE_PATH) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def cache_age_seconds():
    """Return age of cache file in seconds via mtime. Returns float('inf') if missing."""
    try:
        return time.time() - CACHE_PATH.stat().st_mtime
    except OSError:
        return float("inf")


def is_backoff_active(cache):
    """Check if backoff_until is set and in the future."""
    if not cache:
        return False
    backoff_until = cache.get("backoff_until")
    if not backoff_until:
        return False
    try:
        until = datetime.fromisoformat(backoff_until)
        return datetime.now(timezone.utc) < until
    except (ValueError, TypeError):
        return False


def calculate_next_backoff(cache):
    """Calculate next backoff duration: 60s * 2^(errors-1), max 600s."""
    if not cache:
        return BACKOFF_BASE_SECONDS
    errors = cache.get("consecutive_errors", 0)
    if errors <= 0:
        return BACKOFF_BASE_SECONDS
    seconds = BACKOFF_BASE_SECONDS * (2 ** (errors - 1))
    return min(seconds, BACKOFF_MAX_SECONDS)


def fetch_usage(token):
    """Call Anthropic usage API. Returns (data_dict, status_code).

    On timeout or connection error, returns (None, None).
    On HTTP error, returns (None, status_code).
    On malformed JSON 200, returns (None, 200).
    """
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            USAGE_API_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "anthropic-beta": "oauth-2025-04-20",
                "User-Agent": "claude-code/2.0.31",
            },
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw = resp.read().decode()
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return (data, 200)
                return (None, 200)
            except json.JSONDecodeError:
                return (None, 200)
    except urllib.error.HTTPError as e:
        return (None, e.code)
    except Exception:
        return (None, None)


def write_cache(data, source, duration_ms=0):
    """Atomically write usage data to cache file.

    Args:
        data: API response dict (must have five_hour, seven_day, etc.)
        source: "daemon" or "hook"
        duration_ms: how long the fetch took
    """
    cache = {
        "five_hour": data.get("five_hour", {}),
        "seven_day": data.get("seven_day", {}),
        "extra_usage": data.get("extra_usage", {}),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "fetch_duration_ms": duration_ms,
        "last_error": None,
        "last_error_at": None,
        "consecutive_errors": 0,
        "backoff_until": None,
    }
    _atomic_write(cache)


def write_error_to_cache(msg, status=None):
    """Record error in cache while preserving existing usage data.

    Uses flock to protect the read-modify-write cycle against concurrent
    daemon + hook writes (Learning #192: shared .locks/ files need flock).
    """
    from datetime import timedelta

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = CACHE_PATH.parent / "usage-state.flock"
    try:
        with open(lock_path, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                existing = read_cache() or {}
                now = datetime.now(timezone.utc)
                errors = existing.get("consecutive_errors", 0) + 1

                # Calculate backoff for 429s
                backoff_until = None
                if status == 429:
                    backoff_secs = BACKOFF_BASE_SECONDS * (2 ** (errors - 1))
                    backoff_secs = min(backoff_secs, BACKOFF_MAX_SECONDS)
                    backoff_until = (now + timedelta(seconds=backoff_secs)).isoformat()

                cache = {
                    # Preserve existing usage data
                    "five_hour": existing.get("five_hour", {}),
                    "seven_day": existing.get("seven_day", {}),
                    "extra_usage": existing.get("extra_usage", {}),
                    "fetched_at": existing.get("fetched_at"),
                    "source": existing.get("source"),
                    "fetch_duration_ms": existing.get("fetch_duration_ms", 0),
                    # Update error fields
                    "last_error": msg,
                    "last_error_at": now.isoformat(),
                    "consecutive_errors": errors,
                    "backoff_until": backoff_until,
                }
                _atomic_write(cache)
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
    except OSError:
        pass


def _atomic_write(cache):
    """Write cache dict atomically using tempfile + os.replace."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(CACHE_PATH.parent), suffix=".tmp", prefix="usage-state-"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(cache, f)
            os.replace(tmp_path, str(CACHE_PATH))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError:
        pass


def maybe_refresh(source, min_age):
    """Main entry point. Refresh cache if stale enough.

    Args:
        source: "daemon" or "hook"
        min_age: minimum cache age in seconds before refreshing

    Returns:
        True if refresh happened, False if skipped.
    """
    # Dedup: skip if cache is fresh enough
    age = cache_age_seconds()
    if age < min_age:
        return False

    # Check backoff
    cache = read_cache()
    if is_backoff_active(cache):
        return False

    # Get token
    token = get_oauth_token()
    if not token:
        return False

    # Fetch
    start = time.time()
    data, status = fetch_usage(token)
    duration_ms = int((time.time() - start) * 1000)

    if data and status == 200:
        write_cache(data, source, duration_ms)
        return True
    else:
        error_msg = f"HTTP {status}" if status else "timeout/connection error"
        write_error_to_cache(error_msg, status)
        return False
