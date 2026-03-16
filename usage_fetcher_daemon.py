#!/usr/bin/env python3
"""Usage fetcher daemon for Claude Code statusline.

Polls the Anthropic usage API every 5 minutes and writes to
~/.claude/.locks/usage-state.json. Skips if cache is <270s old.

Single-instance via fcntl lock. Log rotation at 1MB.
Follows the pattern of claude_memory_watchdog.py.

Managed by: ~/Library/LaunchAgents/com.popchaos.claude-usage-fetcher.plist
"""

import fcntl
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add tools dir to path for import
sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage_fetcher

POLL_INTERVAL = 300  # 5 minutes
MIN_CACHE_AGE = 270  # skip if cache < 4.5min old
LOCK_PATH = Path.home() / ".claude" / ".locks" / "usage-fetcher.lock"
LOG_DIR = Path.home() / ".claude" / "logs"


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_DIR / "usage-fetcher.log",
        maxBytes=1_000_000,
        backupCount=2,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("usage-fetcher")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def acquire_lock():
    """Acquire exclusive lock file. Returns file descriptor or exits."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        fd.flush()
        return fd
    except OSError:
        print("Another instance is already running. Exiting.", file=sys.stderr)
        sys.exit(0)


def main():
    lock_fd = acquire_lock()
    logger = setup_logging()
    logger.info("Usage fetcher daemon started (PID %d)", os.getpid())

    try:
        while True:
            try:
                refreshed = usage_fetcher.maybe_refresh("daemon", MIN_CACHE_AGE)
                if refreshed:
                    cache = usage_fetcher.read_cache()
                    dur = cache.get("fetch_duration_ms", 0) if cache else 0
                    logger.info("Refreshed usage data (%dms)", dur)
                else:
                    logger.debug("Skipped (cache fresh or backoff active)")
            except Exception as e:
                logger.error("Unexpected error: %s", e)

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Daemon stopped by signal")
    finally:
        try:
            lock_fd.close()
            LOCK_PATH.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    main()
