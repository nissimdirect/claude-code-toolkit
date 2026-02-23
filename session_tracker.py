#!/usr/bin/env python3
"""
Session Tracker — Central Stop Hook (v2)
Runs after every Claude response (debounced per-session).
Zero Claude tokens consumed — pure Python on disk.

Responsibilities:
1. Track session heartbeats
2. Detect multi-session file conflicts
3. Trigger log rotation when needed
4. Lightweight profiling check (flag, don't process)
5. Update shared buffer with session status

Red Team Fixes (v2):
- Atomic writes via temp file + rename
- File locking for shared buffer (fcntl.flock)
- Per-session debounce (not global)
- PID liveness check before deleting lock files
- Error logging to file
- Preserves editing list across heartbeats
- Catches all exceptions in should_run()
"""

import os
import sys
import time
import json
import fcntl
import signal
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

# --- Dynamic Path Resolution ---
# Derives all paths from HOME and username. No hardcoded usernames.

HOME = Path.home()
USERNAME = HOME.name
CLAUDE_DIR = HOME / ".claude"

# Claude Code stores project memory under a path-encoded directory
# e.g., ~/.claude/projects/-Users-nissimagent/memory/
# We derive this from the actual home directory.
PROJECT_KEY = f"-{str(HOME).replace('/', '-').lstrip('-')}"
MEMORY_DIR = CLAUDE_DIR / "projects" / PROJECT_KEY / "memory"

SHARED_BUFFER = CLAUDE_DIR / "shared-buffer.md"
LOG_PATH = MEMORY_DIR / "user-input-log.md"
LEARNINGS_PATH = MEMORY_DIR / "learnings.md"
LOCK_DIR = CLAUDE_DIR / ".locks"
ERROR_LOG = LOCK_DIR / ".session-tracker-errors.log"
RESOURCE_LOG = LOCK_DIR / ".resource-tracker.json"

# Config
DEBOUNCE_SECONDS = 300  # 5 minutes between full checks
MAX_LOG_LINES = 200
SESSION_TIMEOUT = 3600  # 1 hour — session considered dead
MAX_ERROR_LOG_LINES = 100


# --- Atomic File Operations ---


def atomic_write(filepath, content, permissions=0o600):
    """Write to temp file, then atomic rename. Crash-safe."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent), prefix=f".{filepath.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, permissions)
        os.rename(tmp_path, str(filepath))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def log_error(message):
    """Append error to log file. Last resort — append-only is safe."""
    try:
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat()
        entry = f"[{timestamp}] {message}\n"
        with open(str(ERROR_LOG), "a") as f:
            f.write(entry)
        # Trim if too long
        if ERROR_LOG.exists() and ERROR_LOG.stat().st_size > 50000:
            lines = ERROR_LOG.read_text().splitlines()
            atomic_write(ERROR_LOG, "\n".join(lines[-MAX_ERROR_LOG_LINES:]) + "\n")
    except Exception:
        pass  # Error logging itself failed — nothing we can do


# --- Session Identity ---


def get_session_id():
    """Generate a stable session ID from parent PID."""
    pid = os.getppid()
    return f"session-{pid}"


def is_pid_alive(pid):
    """Check if a process is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


# --- Debounce (Per-Session) ---


def should_run(session_id):
    """Check if enough time has passed since THIS session's last full run."""
    tracker_file = LOCK_DIR / f".debounce-{session_id}"
    if not tracker_file.exists():
        return True
    try:
        data = json.loads(tracker_file.read_text())
        if not isinstance(data, dict):
            return True
        last_run = data.get("last_run", 0)
        return (time.time() - last_run) > DEBOUNCE_SECONDS
    except Exception:
        return True


def update_debounce(session_id):
    """Record when this session last did a full check."""
    tracker_file = LOCK_DIR / f".debounce-{session_id}"
    data = {
        "last_run": time.time(),
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    }
    atomic_write(tracker_file, json.dumps(data))


# --- Multi-Session Lock Files ---


def claim_session(session_id):
    """Register this session. Preserves existing editing list."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_DIR / f"{session_id}.lock"

    # Preserve existing editing list if lock file exists
    existing_editing = []
    if lock_file.exists():
        try:
            existing = json.loads(lock_file.read_text())
            if isinstance(existing, dict):
                existing_editing = existing.get("editing", [])
        except Exception:
            pass

    data = {
        "session_id": session_id,
        "pid": os.getppid(),
        "started": datetime.now().isoformat(),
        "last_heartbeat": time.time(),
        "editing": existing_editing,
    }
    atomic_write(lock_file, json.dumps(data))


def update_heartbeat(session_id):
    """Update heartbeat timestamp. Preserves all other fields."""
    lock_file = LOCK_DIR / f"{session_id}.lock"
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text())
            if isinstance(data, dict):
                data["last_heartbeat"] = time.time()
                atomic_write(lock_file, json.dumps(data))
                return
        except Exception:
            pass
    # Lock file missing or corrupt — recreate
    claim_session(session_id)


def cleanup_dead_sessions():
    """Remove lock files for sessions confirmed dead (PID check + timeout)."""
    if not LOCK_DIR.exists():
        return
    now = time.time()
    for lock_file in LOCK_DIR.glob("*.lock"):
        try:
            data = json.loads(lock_file.read_text())
            if not isinstance(data, dict):
                lock_file.unlink()
                continue
            pid = data.get("pid", 0)
            heartbeat = data.get("last_heartbeat", 0)
            # Only delete if BOTH heartbeat is stale AND process is dead
            if (now - heartbeat) > SESSION_TIMEOUT and not is_pid_alive(pid):
                lock_file.unlink()
        except (json.JSONDecodeError, OSError):
            # Corrupt lock file — check if it's old before deleting
            try:
                age = now - lock_file.stat().st_mtime
                if age > SESSION_TIMEOUT:
                    lock_file.unlink()
            except OSError:
                pass


def get_active_sessions():
    """List all active sessions."""
    if not LOCK_DIR.exists():
        return []
    sessions = []
    for lock_file in LOCK_DIR.glob("*.lock"):
        try:
            data = json.loads(lock_file.read_text())
            if isinstance(data, dict):
                sessions.append(data)
        except Exception:
            continue
    return sessions


def check_conflicts(session_id):
    """Check if other sessions are active and report."""
    sessions = get_active_sessions()
    other_sessions = [s for s in sessions if s.get("session_id") != session_id]
    if other_sessions:
        other_ids = [s.get("session_id", "?") for s in other_sessions]
        append_to_shared_buffer(
            session_id, f"Active sessions: {len(sessions)} (others: {other_ids})"
        )


# --- Shared Buffer (Append-Only for Safety) ---


def ensure_shared_buffer():
    """Create shared buffer if it doesn't exist. Uses atomic write."""
    if not SHARED_BUFFER.exists():
        content = """# Shared Buffer — Multi-Session Communication

> Inter-session message bus. All Claude sessions read/write here.
> Newest messages at top. Auto-pruned to last 50 entries.

<!-- BUFFER_START -->

"""
        SHARED_BUFFER.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(SHARED_BUFFER, content)


def append_to_shared_buffer(session_id, message):
    """Post a message to the shared buffer with file locking."""
    ensure_shared_buffer()
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"**[{timestamp}] {session_id}:** {message}\n"

    lock_path = str(SHARED_BUFFER) + ".lock"

    try:
        # Acquire exclusive lock
        lock_fd = open(lock_path, "w")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        # Can't acquire lock — another session is writing. Skip this update.
        try:
            lock_fd.close()
        except Exception:
            pass
        return

    try:
        content = SHARED_BUFFER.read_text()

        # Use robust delimiter
        marker = "<!-- BUFFER_START -->"
        if marker in content:
            parts = content.split(marker, 1)
            header = parts[0] + marker + "\n"
            body = parts[1]
        else:
            # Fallback for old format with ---
            parts = content.split("---\n", 1)
            if len(parts) == 2:
                header = parts[0] + "---\n"
                body = parts[1]
            else:
                header = content
                body = ""

        # Add new entry at top of body
        body = "\n" + entry + body

        # Prune to 50 entries
        lines = body.strip().split("\n")
        entry_lines = [l for l in lines if l.startswith("**[")]
        if len(entry_lines) > 50:
            body_lines = []
            count = 0
            for line in lines:
                if line.startswith("**["):
                    count += 1
                    if count > 50:
                        break
                body_lines.append(line)
            body = "\n".join(body_lines)

        atomic_write(SHARED_BUFFER, header + body + "\n")
    finally:
        # Release lock
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()
            os.unlink(lock_path)
        except Exception:
            pass


# --- Log Rotation Check ---


def check_log_rotation():
    """Check if input log needs rotation."""
    if not LOG_PATH.exists():
        return False
    try:
        lines = len(LOG_PATH.read_text(encoding="utf-8").splitlines())
        if lines > MAX_LOG_LINES:
            append_to_shared_buffer(
                get_session_id(), f"INPUT LOG AT {lines} LINES — needs rotation"
            )
            return True
    except Exception:
        pass
    return False


# --- Profiling Flag ---


def check_profiling_needed():
    """Check if profiling analysis is overdue. Flag, don't process."""
    index_file = Path.home() / ".claude/.locks/learning-index.json"
    if not index_file.exists():
        return
    try:
        import json

        index = json.loads(index_file.read_text(encoding="utf-8"))
        correction_count = len(index.get("correction_history", []))
        if correction_count >= 5:
            append_to_shared_buffer(
                get_session_id(), "PROFILING DUE — 5+ sessions since last /self-improve"
            )
    except Exception:
        pass


# --- Resource Tracking ---


def track_response():
    """Increment response counter and track session duration.
    Runs on EVERY hook call (not debounced) for accurate counting.
    Flags when session is burning too many responses."""
    try:
        data = {}
        if RESOURCE_LOG.exists():
            try:
                data = json.loads(RESOURCE_LOG.read_text())
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}

        session_id = get_session_id()
        now = time.time()

        # Per-session tracking
        sessions = data.get("sessions", {})
        session = sessions.get(
            session_id,
            {
                "first_response": now,
                "response_count": 0,
                "last_response": now,
            },
        )
        session["response_count"] = session.get("response_count", 0) + 1
        session["last_response"] = now

        # Calculate session duration in minutes
        duration_min = (now - session.get("first_response", now)) / 60
        response_count = session["response_count"]

        sessions[session_id] = session
        data["sessions"] = sessions

        # Daily aggregate
        today = datetime.now().strftime("%Y-%m-%d")
        daily = data.get("daily", {})
        today_data = daily.get(today, {"responses": 0, "sessions": []})
        today_data["responses"] = today_data.get("responses", 0) + 1
        if session_id not in today_data.get("sessions", []):
            today_data.setdefault("sessions", []).append(session_id)
        daily[today] = today_data
        data["daily"] = daily

        # Prune daily data older than 7 days
        cutoff = (datetime.now().replace(hour=0, minute=0, second=0)).__format__(
            "%Y-%m-%d"
        )
        for key in list(daily.keys()):
            if key < cutoff and len(daily) > 7:
                del daily[key]

        # Prune stale sessions (older than 7 days)
        week_ago = now - (7 * 86400)
        for sid in list(sessions.keys()):
            s = sessions[sid]
            if isinstance(s, dict) and s.get("last_response", 0) < week_ago:
                del sessions[sid]

        atomic_write(RESOURCE_LOG, json.dumps(data, indent=2))

        # Alert thresholds (post to shared buffer on full check cycles)
        if response_count > 0 and response_count % 50 == 0:
            append_to_shared_buffer(
                session_id,
                f"RESOURCE: {response_count} responses in {duration_min:.0f}min. "
                f"Consider /clear if context is bloated.",
            )

        if today_data.get("responses", 0) > 200:
            append_to_shared_buffer(
                session_id,
                f"RESOURCE WARNING: {today_data['responses']} responses today. "
                f"High burn rate — review if tasks need model downgrade to Haiku.",
            )

    except Exception:
        pass  # Resource tracking is non-critical


# --- Main ---


def main():
    session_id = get_session_id()

    # Always track responses (lightweight, not debounced)
    track_response()

    if not should_run(session_id):
        # Still update heartbeat even if debounced
        update_heartbeat(session_id)
        return

    # Full check cycle
    update_debounce(session_id)
    claim_session(session_id)
    cleanup_dead_sessions()
    check_conflicts(session_id)
    check_log_rotation()
    check_profiling_needed()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error(f"CRASH: {e}\n{traceback.format_exc()}")
        sys.exit(1)
