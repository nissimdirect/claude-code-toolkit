#!/usr/bin/env python3
"""Claude Memory Watchdog — System Memory Observatory.

Single writer for .memory-state.json. Monitors memory, alerts, logs, kills.
Runs as a launchd daemon. Self-restarts via launchd if memory exceeds 50MB.

No external dependencies — uses only macOS native commands (vm_stat, sysctl, ps).

Alert levels (percentage of wired+active+compressed RAM):
  ok       (<60%)   — log only
  moderate (60-75%) — macOS notification (5-min cooldown)
  high     (75-85%) — urgent notification, deny delegation
  critical (85-92%) — SIGTERM newest Claude subprocess (LIFO)
  emergency (>92%)  — SIGKILL all Claude except primary, stop Ollama

RT-1: Uses wired+active+compressed (not naive used/total) for accurate pressure.
RT-2: Kills by PID age (LIFO) — oldest PID = primary session, preserved.
RT-3: Self-memory-limited at 50MB via resource.getrusage().
RT-4: SIGTERM at critical, SIGKILL only at emergency.
RT-5: Notification cooldown per level (5 minutes).
RT-6: Atomic write via tmp+rename.
"""

import fcntl
import json
import os
import re
import resource
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --- Configuration ---
STATE_FILE = Path.home() / ".claude" / ".locks" / ".memory-state.json"
STATE_TMP = STATE_FILE.with_suffix(".tmp")
LOG_DIR = Path.home() / ".claude" / "logs"
LOCK_FILE = Path.home() / ".claude" / ".locks" / ".memory-watchdog.lock"
HEURISTICS_FILE = Path.home() / ".claude" / ".locks" / ".memory-heuristics.json"

POLL_INTERVAL = 30  # seconds
SELF_MEMORY_LIMIT_MB = 50
NOTIFICATION_COOLDOWN = 300  # 5 minutes per alert level
LOG_RETENTION_DAYS = 3
LOG_MAX_SIZE_MB = 10

# Balloon detection: rate-of-change monitoring
# If total RAM usage grows faster than this threshold, it's a balloon
# regardless of where the absolute percentage sits.
BALLOON_WINDOW_SAMPLES = 6  # 6 samples * 30s = 3-minute rolling window
BALLOON_RATE_MB_PER_MIN = 500  # 500 MB/min growth = balloon
BALLOON_RATE_CRITICAL_MB_PER_MIN = 1500  # 1.5 GB/min = emergency balloon

# Alert thresholds (percentage of physical RAM: wired+active+compressed).
# CALIBRATED FOR macOS Apple Silicon (16 GB):
#   - macOS baseline wired memory is 5-8 GB (kernel, GPU, filesystem)
#   - "Healthy" is typically 70-80% on a 16 GB Mac with apps running
#   - System starts heavy swapping above ~90%
#   - Freeze/crash zone is 95%+
# These thresholds were calibrated against live readings showing 88%
# with the system still functional but swapping (335K swapouts).
THRESHOLDS = {
    "ok": 0,
    "moderate": 65,
    "high": 80,
    "critical": 92,
    "emergency": 96,
}


# --- Memory Reading (native macOS, zero dependencies) ---


def get_total_ram_bytes():
    """Get total physical RAM via sysctl."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return 16 * 1024 * 1024 * 1024  # fallback 16GB


def parse_vm_stat():
    """Parse vm_stat output for memory breakdown.

    Returns dict of stat_name -> bytes.
    Handles both Apple Silicon (16384 page) and Intel (4096 page) Macs.
    """
    try:
        result = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=3)
        output = result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return {}

    # Extract page size from header line
    page_size = 16384  # Apple Silicon default
    m = re.search(r"page size of (\d+) bytes", output)
    if m:
        page_size = int(m.group(1))

    stats = {}
    for line in output.splitlines():
        # Match lines like: "Pages free:                   3842."
        # and: "Pages occupied by compressor:  66988."
        m = re.match(r'^(?:Pages |")?(.+?)(?:")?:\s+(\d+)', line)
        if m:
            key = m.group(1).strip().lower().replace(" ", "_")
            stats[key] = int(m.group(2)) * page_size

    return stats


def get_memory_pressure():
    """Calculate actual memory pressure from vm_stat.

    Returns (used_bytes, total_bytes, breakdown_dict).

    RT-1 FIX: 'Used' = wired + active + occupied_by_compressor.
    This represents memory that can't be freed without killing processes.
    Inactive and purgeable memory is excluded (macOS reclaims it freely).
    """
    total = get_total_ram_bytes()
    stats = parse_vm_stat()

    wired = stats.get("wired_down", 0)
    active = stats.get("active", 0)
    compressed = stats.get("occupied_by_compressor", 0)

    # Real pressure: only memory that requires process termination to free
    used = wired + active + compressed

    mb = 1024 * 1024
    return (
        used,
        total,
        {
            "wired_mb": wired // mb,
            "active_mb": active // mb,
            "compressed_mb": compressed // mb,
            "inactive_mb": stats.get("inactive", 0) // mb,
            "free_mb": stats.get("free", 0) // mb,
        },
    )


def get_process_memory():
    """Get memory usage for Claude, Ollama, and MCP processes.

    RT-2: Sorts by PID (lowest = oldest = primary). Kill order is LIFO.
    """
    try:
        result = subprocess.run(
            ["ps", "-ax", "-o", "pid=,rss=,ppid=,etime=,command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"claude": [], "claude_total_mb": 0, "ollama_mb": 0, "mcp_mb": 0}

    claude_procs = []
    ollama_mb = 0
    mcp_mb = 0

    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 4)
        if len(parts) < 5:
            continue

        try:
            pid = int(parts[0])
            rss_kb = int(parts[1])
            ppid = int(parts[2])
            etime = parts[3]
            cmd = parts[4]
        except (ValueError, IndexError):
            continue

        rss_mb = rss_kb / 1024

        # Claude processes (main sessions and subagents)
        if "claude" in cmd.lower() and (
            "--dangerously" in cmd
            or "/claude " in cmd
            or cmd.strip().endswith("claude")
        ):
            claude_procs.append(
                {
                    "pid": pid,
                    "rss_mb": round(rss_mb),
                    "ppid": ppid,
                    "etime": etime,
                }
            )
        # Ollama model runners (the actual memory hogs)
        elif "ollama" in cmd.lower() and "runner" in cmd.lower():
            ollama_mb += rss_mb
        # MCP server processes
        elif any(
            s in cmd.lower()
            for s in ["server-github", "server-memory", "playwright", "sentry/mcp"]
        ):
            mcp_mb += rss_mb

    # Sort by PID ascending (lowest = oldest = primary)
    claude_procs.sort(key=lambda p: p["pid"])
    if claude_procs:
        claude_procs[0]["type"] = "primary"
        for p in claude_procs[1:]:
            p["type"] = "secondary"

    return {
        "claude": claude_procs,
        "claude_total_mb": round(sum(p["rss_mb"] for p in claude_procs)),
        "ollama_mb": round(ollama_mb),
        "mcp_mb": round(mcp_mb),
    }


# --- Alert Level ---


def calculate_alert_level(used_pct):
    """Determine alert level from memory pressure percentage."""
    if used_pct >= THRESHOLDS["emergency"]:
        return "emergency"
    if used_pct >= THRESHOLDS["critical"]:
        return "critical"
    if used_pct >= THRESHOLDS["high"]:
        return "high"
    if used_pct >= THRESHOLDS["moderate"]:
        return "moderate"
    return "ok"


# --- Balloon Detection ---


class BalloonDetector:
    """Detects rapid memory growth (ballooning) via rate-of-change analysis.

    Tracks a rolling window of (timestamp, used_mb) samples.
    If the growth rate exceeds thresholds, raises the alert level
    INDEPENDENTLY of static thresholds. This catches the scenario where
    memory goes from 50% to 95% in 60 seconds — static thresholds
    would only react when each level is crossed, but balloon detection
    triggers immediately on the growth rate.
    """

    def __init__(self, window_size=BALLOON_WINDOW_SAMPLES):
        self.samples = []  # list of (timestamp, used_mb)
        self.window_size = window_size
        self.last_balloon_alert = 0  # timestamp of last balloon notification

    def add_sample(self, used_mb):
        """Add a memory sample. Maintains rolling window."""
        self.samples.append((time.time(), used_mb))
        if len(self.samples) > self.window_size:
            self.samples = self.samples[-self.window_size :]

    def get_rate_mb_per_min(self):
        """Calculate growth rate in MB/minute over the rolling window.

        Returns float. Positive = growing, negative = shrinking, 0 = insufficient data.
        """
        if len(self.samples) < 2:
            return 0.0

        oldest_ts, oldest_mb = self.samples[0]
        newest_ts, newest_mb = self.samples[-1]
        elapsed_min = (newest_ts - oldest_ts) / 60.0

        if elapsed_min < 0.1:  # Less than 6 seconds of data
            return 0.0

        return (newest_mb - oldest_mb) / elapsed_min

    def detect(self):
        """Detect balloon condition.

        Returns:
            (is_ballooning: bool, severity: str, rate_mb_min: float)
            severity is "warning" (>500 MB/min) or "critical" (>1500 MB/min)
        """
        rate = self.get_rate_mb_per_min()

        if rate >= BALLOON_RATE_CRITICAL_MB_PER_MIN:
            return True, "critical", rate
        if rate >= BALLOON_RATE_MB_PER_MIN:
            return True, "warning", rate
        return False, "none", rate


# --- Actions ---


def send_notification(title, message, sound="Ping"):
    """Send macOS notification via osascript."""
    # Escape quotes in message
    safe_msg = message.replace('"', '\\"').replace("'", "\\'")
    safe_title = title.replace('"', '\\"')
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{safe_msg}" with title "{safe_title}" sound name "{sound}"',
            ],
            capture_output=True,
            timeout=3,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass


def kill_newest_claude(claude_procs, signum=signal.SIGTERM):
    """Kill the newest Claude subprocess (LIFO).

    RT-2: Preserves oldest PID (primary session). Only kills if >1 process.
    RT-4: Uses SIGTERM at critical level (graceful), SIGKILL only at emergency.
    Returns killed PID or None.
    """
    if len(claude_procs) <= 1:
        return None  # Never kill the only/primary process

    # Sort by PID descending (newest first)
    sorted_procs = sorted(claude_procs, key=lambda p: p["pid"], reverse=True)
    target = sorted_procs[0]

    try:
        os.kill(target["pid"], signum)
        return target["pid"]
    except (ProcessLookupError, PermissionError):
        return None


def kill_all_claude_except_primary(claude_procs):
    """Kill all Claude processes except the oldest (primary).

    Returns list of killed PIDs.
    """
    if len(claude_procs) <= 1:
        return []

    sorted_procs = sorted(claude_procs, key=lambda p: p["pid"])
    killed = []

    for proc in sorted_procs[1:]:
        try:
            os.kill(proc["pid"], signal.SIGKILL)
            killed.append(proc["pid"])
        except (ProcessLookupError, PermissionError):
            pass

    return killed


def stop_ollama():
    """Try graceful Ollama model unload, then kill runners if needed."""
    try:
        # Try API-based unload first (cleaner than kill)
        subprocess.run(
            ["ollama", "stop"],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass


# --- State Management ---


def write_state(state):
    """Atomic write of memory state file (RT-6: tmp+rename)."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_TMP, "w") as f:
            json.dump(state, f, indent=2)
        os.rename(str(STATE_TMP), str(STATE_FILE))
    except OSError as e:
        print(f"[watchdog] Failed to write state: {e}", file=sys.stderr)


def read_heuristics():
    """Read heuristics data."""
    try:
        if HEURISTICS_FILE.exists():
            return json.loads(HEURISTICS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {
        "avg_claude_mb": 0,
        "samples": 0,
        "peak_today_mb": 0,
        "peak_today_date": "",
        "peak_today_time": "",
        "incidents_today": 0,
        "incidents_today_date": "",
        "incidents_7d": [],
    }


def update_heuristics(heuristics, claude_total_mb, alert_level):
    """Update running heuristics with latest sample."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Rolling average (capped at 10000 samples to prevent overflow)
    n = heuristics.get("samples", 0)
    avg = heuristics.get("avg_claude_mb", 0)
    if n > 0:
        heuristics["avg_claude_mb"] = round((avg * n + claude_total_mb) / (n + 1))
    else:
        heuristics["avg_claude_mb"] = claude_total_mb
    heuristics["samples"] = min(n + 1, 10000)

    # Daily peak
    if heuristics.get("peak_today_date") != today:
        heuristics["peak_today_mb"] = 0
        heuristics["peak_today_date"] = today
    if claude_total_mb > heuristics.get("peak_today_mb", 0):
        heuristics["peak_today_mb"] = claude_total_mb
        heuristics["peak_today_time"] = datetime.now().strftime("%H:%M")

    # Incident tracking
    if heuristics.get("incidents_today_date") != today:
        heuristics["incidents_today"] = 0
        heuristics["incidents_today_date"] = today
    if alert_level in ("critical", "emergency"):
        heuristics["incidents_today"] = heuristics.get("incidents_today", 0) + 1
        incidents_7d = heuristics.get("incidents_7d", [])
        incidents_7d.append(
            {
                "date": today,
                "time": datetime.now().strftime("%H:%M"),
                "level": alert_level,
            }
        )
        # Keep only last 50 entries (hard cap)
        heuristics["incidents_7d"] = incidents_7d[-50:]

    try:
        HEURISTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HEURISTICS_FILE, "w") as f:
            json.dump(heuristics, f, indent=2)
    except OSError:
        pass

    return heuristics


# --- Forensic Log ---


def get_log_path():
    """Get today's forensic log path."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"memory-{datetime.now().strftime('%Y-%m-%d')}.log"


def write_log_entry(state, event=""):
    """Append one line to today's forensic log.

    Format: HH:MM:SS|level|ram_pct|claude_mb|ollama_mb|mcp_mb|sessions|headroom_mb[|event]
    Q-3: Pipe-delimited, fixed-field, grep-friendly.
    """
    log_path = get_log_path()

    # Check size limit (LOG_MAX_SIZE_MB)
    try:
        if (
            log_path.exists()
            and log_path.stat().st_size > LOG_MAX_SIZE_MB * 1024 * 1024
        ):
            return
    except OSError:
        pass

    ts = datetime.now().strftime("%H:%M:%S")
    level = state.get("alert_level", "?")
    ram_pct = state.get("used_pct", 0)
    claude_mb = state.get("claude_total_mb", 0)
    ollama_mb = state.get("ollama_mb", 0)
    mcp_mb = state.get("mcp_total_mb", 0)
    sessions = state.get("session_count", 0)
    headroom = state.get("headroom_mb", 0)

    line = f"{ts}|{level}|{ram_pct:.0f}|{claude_mb}|{ollama_mb}|{mcp_mb}|{sessions}|{headroom}"
    if event:
        line += f"|{event}"
    line += "\n"

    try:
        with open(log_path, "a") as f:
            f.write(line)
    except OSError:
        pass


def write_log_header():
    """Write header to today's log if it's new."""
    log_path = get_log_path()
    if not log_path.exists() or log_path.stat().st_size == 0:
        try:
            with open(log_path, "a") as f:
                f.write(
                    "# time|level|ram%|claude_mb|ollama_mb|mcp_mb|sessions|headroom_mb|event\n"
                )
        except OSError:
            pass


def rotate_logs():
    """Delete forensic logs older than retention period."""
    try:
        cutoff = time.time() - LOG_RETENTION_DAYS * 86400
        for log_file in LOG_DIR.glob("memory-*.log"):
            try:
                if log_file.stat().st_mtime < cutoff:
                    log_file.unlink()
            except OSError:
                pass
    except OSError:
        pass


# --- Self-Memory Check (RT-3) ---


def check_self_memory():
    """Exit if watchdog itself exceeds memory limit.

    launchd KeepAlive=true will restart us fresh. This prevents
    the memory watchdog from becoming a memory problem itself.
    """
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # macOS: ru_maxrss is in bytes
        rss_mb = usage.ru_maxrss / (1024 * 1024)
        if rss_mb > SELF_MEMORY_LIMIT_MB:
            print(
                f"[watchdog] Self RSS {rss_mb:.0f}MB > {SELF_MEMORY_LIMIT_MB}MB limit, "
                "exiting for launchd restart",
                file=sys.stderr,
            )
            os._exit(0)
    except (AttributeError, OSError):
        pass


# --- Singleton Lock ---


def acquire_lock():
    """Ensure only one watchdog instance runs via flock."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return lock_fd
    except IOError:
        print("[watchdog] Another instance is running, exiting.", file=sys.stderr)
        sys.exit(0)


# --- Main Loop ---


def main():
    lock_fd = acquire_lock()

    total_ram = get_total_ram_bytes()
    total_ram_gb = total_ram / (1024**3)

    # Notification cooldown tracking: level -> last_notification_timestamp
    last_notification = {}

    # Balloon detector — tracks rate of change across samples
    balloon = BalloonDetector()

    heuristics = read_heuristics()

    print(
        f"[watchdog] Started. Total RAM: {total_ram_gb:.1f} GB. PID: {os.getpid()}",
        file=sys.stderr,
    )

    # Rotate old logs on startup
    rotate_logs()
    write_log_header()

    while True:
        try:
            # 1. Read memory pressure (RT-1: wired+active+compressed)
            used_bytes, _, breakdown = get_memory_pressure()
            used_gb = used_bytes / (1024**3)
            used_pct = (used_bytes / total_ram) * 100

            # 2. Read process memory
            procs = get_process_memory()
            claude_procs = procs["claude"]
            claude_total_mb = procs["claude_total_mb"]
            ollama_mb = procs["ollama_mb"]
            mcp_mb = procs["mcp_mb"]
            session_count = len(claude_procs)
            headroom_mb = max(0, round((total_ram - used_bytes) / (1024 * 1024)))

            # 3. Calculate alert level
            alert_level = calculate_alert_level(used_pct)

            # 3b. Balloon detection — rate-of-change analysis
            used_total_mb = round(used_bytes / (1024 * 1024))
            balloon.add_sample(used_total_mb)
            is_ballooning, balloon_severity, balloon_rate = balloon.detect()

            # If ballooning, escalate alert level — but NEVER to kill-triggering
            # levels (critical/emergency). Balloon = warn + block spawning only.
            # Only static RAM thresholds (92%+) should trigger process kills.
            balloon_event = ""
            if is_ballooning:
                if alert_level in ("ok", "moderate"):
                    alert_level = "high"
                    balloon_event = (
                        f"BALLOON:{balloon_severity}:{balloon_rate:.0f}MB/min"
                    )

            can_spawn = alert_level in ("ok", "moderate", "high")

            # 4. Build state
            state = {
                "timestamp": datetime.now().isoformat(),
                "total_ram_gb": round(total_ram_gb, 1),
                "used_ram_gb": round(used_gb, 1),
                "used_pct": round(used_pct, 1),
                "alert_level": alert_level,
                "claude_processes": claude_procs,
                "claude_total_mb": claude_total_mb,
                "ollama_mb": ollama_mb,
                "mcp_total_mb": mcp_mb,
                "session_count": session_count,
                "headroom_mb": headroom_mb,
                "can_spawn_agents": can_spawn,
                "breakdown": breakdown,
                "heuristics": {
                    "avg_claude_mb": heuristics.get("avg_claude_mb", 0),
                    "peak_today_mb": heuristics.get("peak_today_mb", 0),
                    "peak_today_time": heuristics.get("peak_today_time", ""),
                    "incidents_24h": heuristics.get("incidents_today", 0),
                    "incidents_7d": len(heuristics.get("incidents_7d", [])),
                },
                "balloon": {
                    "is_ballooning": is_ballooning,
                    "rate_mb_per_min": round(balloon_rate),
                    "severity": balloon_severity,
                },
            }

            # 5. Write state atomically (RT-6)
            write_state(state)

            # 6. Take action based on alert level
            event = balloon_event  # Pre-populated if balloon detected
            now = time.time()

            if alert_level == "moderate":
                # RT-5: Cooldown per level
                if now - last_notification.get("moderate", 0) > NOTIFICATION_COOLDOWN:
                    send_notification(
                        "Memory Moderate",
                        f"RAM: {used_pct:.0f}% | Claude: {claude_total_mb}MB | Ollama: {ollama_mb}MB",
                    )
                    last_notification["moderate"] = now
                    event = "NOTIFY:moderate"

            elif alert_level == "high":
                if now - last_notification.get("high", 0) > NOTIFICATION_COOLDOWN:
                    msg = f"RAM: {used_pct:.0f}% — avoid agent teams"
                    if ollama_mb > 1024:
                        msg += f". Ollama: {ollama_mb}MB — consider ollama stop"
                    send_notification("Memory HIGH", msg, sound="Sosumi")
                    last_notification["high"] = now
                    event = "NOTIFY:high"

            elif alert_level == "critical":
                # RT-4: SIGTERM first (graceful)
                killed_pid = kill_newest_claude(claude_procs, signal.SIGTERM)
                if killed_pid:
                    send_notification(
                        "Memory CRITICAL",
                        f"RAM: {used_pct:.0f}% — SIGTERM sent to Claude PID {killed_pid}",
                        sound="Basso",
                    )
                    event = f"KILL:SIGTERM:{killed_pid}"
                else:
                    if (
                        now - last_notification.get("critical", 0)
                        > NOTIFICATION_COOLDOWN
                    ):
                        send_notification(
                            "Memory CRITICAL",
                            f"RAM: {used_pct:.0f}% — no subprocess to kill. Run: ollama stop",
                            sound="Basso",
                        )
                        last_notification["critical"] = now
                    event = "ALERT:critical_no_target"

            elif alert_level == "emergency":
                # Kill all Claude except primary
                killed = kill_all_claude_except_primary(claude_procs)
                # Stop Ollama
                stopped_ollama = False
                if ollama_mb > 512:
                    stop_ollama()
                    stopped_ollama = True
                event = f"EMERGENCY:killed_claude_pids={killed}"
                if stopped_ollama:
                    event += ",stopped_ollama"
                send_notification(
                    "MEMORY EMERGENCY",
                    f"RAM: {used_pct:.0f}% — killed {len(killed)} Claude procs"
                    + (", stopped Ollama" if stopped_ollama else ""),
                    sound="Basso",
                )

            # 7. Write forensic log
            write_log_entry(state, event)

            # 8. Update heuristics
            heuristics = update_heuristics(heuristics, claude_total_mb, alert_level)

            # 9. Self-memory check (RT-3)
            check_self_memory()

            # 10. Rotate logs once per hour
            if datetime.now().minute == 0 and datetime.now().second < POLL_INTERVAL:
                rotate_logs()

        except Exception as e:
            print(f"[watchdog] Error in main loop: {e}", file=sys.stderr)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
