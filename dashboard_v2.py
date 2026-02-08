#!/usr/bin/env python3
"""Dashboard V2 — Claude Code Unified Dashboard

Addresses ALL user feedback from DASHBOARD-V2-PRD.md:
- Usage & limits at TOP (daily/weekly/monthly)
- Task priorities from ACTIVE-TASKS.md
- Accurate knowledge base counts (verified directory names)
- Environmental impact tracking
- Clear labels (no abbreviations, no jargon)
- Proper spacing and readability
- Background job monitoring
- Refresh rate visibility

Advisor improvements (Lenny + ChatPRD, 2026-02-07):
- "Next Action" recommendation at very top (Teresa Torres OST)
- Self-validation with warnings (John Lindquist stop-hook pattern)
- Error logging to JSON (Hamel Husain error analysis)
- Data confidence indicators per panel

Usage: python3 dashboard_v2.py
"""

import os
import re
import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.markup import escape as rich_escape
import time
import signal
import tempfile

# === CONFIGURATION ===

RESOURCE_TRACKER = Path.home() / ".claude/.locks/.resource-tracker.json"
ACTIVE_TASKS = Path.home() / "Documents/Obsidian/ACTIVE-TASKS.md"
SCRAPING_QUEUE = Path.home() / "Documents/Obsidian/process/SCRAPING-QUEUE.md"
ERROR_LOG = Path.home() / ".claude/.locks/dashboard_errors.json"

# Subscription model (Max plan)
SUBSCRIPTION_COST = 200.00
DAILY_LIMIT = 50
WEEKLY_LIMIT = 250
MONTHLY_LIMIT = 1000

# Environmental impact constants
CO2_PER_RESPONSE_G = 4.0
MILES_PER_KG_CO2 = 2.58

# Knowledge base sources — VERIFIED directory names and structures
KB_SOURCES = {
    "Cherie Hu (Water & Music)": {
        "path": "cherie-hu/articles",
        "pattern": "*.md",
    },
    "Lenny's Podcast": {
        "path": "lennys-podcast-transcripts/episodes",
        "pattern": "**/*.md",
    },
    "Indie Hackers": {
        "path": "indie-hackers",
        "pattern": "**/*.md",
    },
    "Jesse Cannon": {
        "path": "jesse-cannon/articles",
        "pattern": "*.md",
    },
    "ChatPRD": {
        "path": "chatprd-blog/articles",
        "pattern": "*.md",
    },
    "Obsidian Vault": {
        "path": None,
        "pattern": "**/*.md",
    },
}

console = Console()

# === CACHING (CTO review: glob 3000+ files every 5s is bottleneck) ===
_cache = {}
_cache_ttl = {}
CACHE_TTL_SECONDS = {
    "kb_stats": 60,        # KB counts change rarely
    "services": 30,        # Services change rarely
    "system_memory": 15,   # Disk stats change slowly
    "scraping_jobs": 10,   # Jobs change at scraping speed
    "tracker_data": 10,    # CTO P1: was reading file every 5s uncached
    "active_tasks": 15,    # CTO P1: was parsing file every 5s uncached
    "error_summary": 30,   # CTO P1: was reading file every 5s uncached
}


def cached(key, loader, ttl=None):
    """Return cached value if fresh, otherwise call loader and cache result."""
    if ttl is None:
        ttl = CACHE_TTL_SECONDS.get(key, 10)
    now = time.time()
    if key in _cache and (now - _cache_ttl.get(key, 0)) < ttl:
        return _cache[key]
    result = loader()
    _cache[key] = result
    _cache_ttl[key] = now
    return result


class GlobTimeout(Exception):
    pass


_in_safe_glob = False


def _glob_timeout_handler(signum, frame):
    if _in_safe_glob:
        raise GlobTimeout("glob took too long")
    # Ignore SIGALRM if not in a glob operation (Red Team: external signal safety)


def safe_glob(path, pattern, timeout_sec=5):
    """Glob with timeout protection (Red Team Finding 6.1)."""
    global _in_safe_glob
    old_handler = signal.signal(signal.SIGALRM, _glob_timeout_handler)
    _in_safe_glob = True
    try:
        signal.alarm(timeout_sec)
        result = list(path.glob(pattern))
        signal.alarm(0)
        return result
    except GlobTimeout:
        log_error("glob", f"{path}/{pattern}", "timeout", f"glob timed out after {timeout_sec}s")
        return []
    except OSError:
        return []
    finally:
        _in_safe_glob = False
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


# === ERROR LOGGING (Hamel Husain pattern) ===

def log_error(panel, expected, actual, reason):
    """Log a data discrepancy to the error log for pattern analysis."""
    errors = []
    if ERROR_LOG.exists():
        try:
            errors = json.loads(ERROR_LOG.read_text())
        except (json.JSONDecodeError, OSError):
            errors = []

    errors.append({
        "timestamp": datetime.now().isoformat(),
        "panel": panel,
        "expected": expected,
        "actual": actual,
        "reason": reason,
    })

    # Keep last 100 errors
    errors = errors[-100:]

    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file + rename (Red Team: crash during write = corrupt JSON)
        fd, tmp_path = tempfile.mkstemp(dir=ERROR_LOG.parent, suffix='.json')
        with os.fdopen(fd, 'w') as f:
            json.dump(errors, f, indent=2)
        os.replace(tmp_path, ERROR_LOG)
    except OSError:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except (OSError, UnboundLocalError):
            pass


def _get_error_summary():
    """Get summary of recent errors for confidence display."""
    if not ERROR_LOG.exists():
        return {"count": 0, "recent": []}
    try:
        errors = json.loads(ERROR_LOG.read_text())
        # Errors in last 24h
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        recent = [e for e in errors if e.get("timestamp", "") > cutoff]
        return {"count": len(recent), "recent": recent[-3:]}
    except (json.JSONDecodeError, OSError):
        return {"count": 0, "recent": []}


def get_error_summary():
    """Cached error summary — refreshes every 30s (CTO P1: was reading every 5s)."""
    return cached("error_summary", _get_error_summary, ttl=30)


# === SELF-VALIDATION (John Lindquist pattern) ===

def validate_kb_counts(stats):
    """Validate KB counts — checks directories exist. No re-glob (CTO: was double-counting)."""
    warnings = []
    dev_dir = Path.home() / "Development"

    for name, config in KB_SOURCES.items():
        if config["path"] is None:
            source_path = Path.home() / "Documents" / "Obsidian"
        else:
            source_path = dev_dir / config["path"]

        if not source_path.exists():
            if name in stats:
                msg = f"{name}: directory missing but showing {stats[name]}"
                warnings.append(msg)
                log_error("knowledge_base", "directory exists", "missing", msg)
        elif name not in stats:
            msg = f"{name}: directory exists but 0 articles found"
            warnings.append(msg)
            log_error("knowledge_base", ">0", 0, msg)

    return warnings


def validate_usage(usage, data):
    """Validate usage data isn't stale or corrupted."""
    warnings = []

    # Check if resource tracker file exists and is recent
    if not RESOURCE_TRACKER.exists():
        warnings.append("Resource tracker file missing — counts may be zero")
        return warnings

    try:
        mtime = RESOURCE_TRACKER.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        if age_hours > 24:
            warnings.append(f"Resource tracker not updated in {int(age_hours)}h")
            log_error("usage", "recent data", f"{int(age_hours)}h old", "stale tracker")
    except OSError:
        pass

    # Sanity: today's count shouldn't exceed daily limit by 10x
    if usage["today"] > DAILY_LIMIT * 10:
        warnings.append(f"Today's count suspiciously high: {usage['today']}")
        log_error("usage", f"<{DAILY_LIMIT * 10}", usage["today"], "suspicious count")

    return warnings


# === DATA LOADERS ===

def _load_tracker_data():
    """Load resource tracking data from session tracker."""
    if not RESOURCE_TRACKER.exists():
        return {"sessions": {}, "daily": {}}
    try:
        return json.loads(RESOURCE_TRACKER.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {"sessions": {}, "daily": {}}


def load_tracker_data():
    """Cached tracker data — refreshes every 10s (CTO P1: was reading every 5s)."""
    return cached("tracker_data", _load_tracker_data, ttl=10)


def get_usage_stats(data):
    """Calculate usage for today, this week, this month."""
    now = datetime.now()
    today_key = now.strftime("%Y-%m-%d")
    daily = data.get("daily", {})
    if not isinstance(daily, dict):
        daily = {}

    today_responses = daily.get(today_key, {}).get("responses", 0)

    week_start = now - timedelta(days=now.weekday())
    week_responses = 0
    for date_str, day_data in daily.items():
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if date >= week_start.replace(hour=0, minute=0, second=0):
                week_responses += day_data.get("responses", 0)
        except ValueError:
            continue

    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    month_responses = 0
    for date_str, day_data in daily.items():
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if date >= month_start:
                month_responses += day_data.get("responses", 0)
        except ValueError:
            continue

    return {
        "today": today_responses,
        "week": week_responses,
        "month": month_responses,
    }


def _load_knowledge_base_stats():
    """Count articles across all knowledge bases using VERIFIED paths."""
    dev_dir = Path.home() / "Development"
    stats = {}
    total = 0

    for name, config in KB_SOURCES.items():
        if config["path"] is None:
            source_path = Path.home() / "Documents" / "Obsidian"
        else:
            source_path = dev_dir / config["path"]

        if source_path.exists():
            count = len(safe_glob(source_path, config["pattern"]))
            if count > 0:
                stats[name] = count
                total += count

    return stats, total


def get_knowledge_base_stats():
    """Cached KB stats — refreshes every 60s (CTO: was globbing 3000+ files every 5s)."""
    return cached("kb_stats", _load_knowledge_base_stats, ttl=60)


def _parse_active_tasks():
    """Parse top tasks from ACTIVE-TASKS.md for the priority buffer."""
    tasks = []
    if not ACTIVE_TASKS.exists():
        return tasks

    try:
        # Guard against huge files (Red Team: 100MB file = memory exhaustion)
        if ACTIVE_TASKS.stat().st_size > 1_000_000:
            log_error("tasks", "<1MB", f"{ACTIVE_TASKS.stat().st_size}B", "ACTIVE-TASKS.md too large")
            return tasks
        content = ACTIVE_TASKS.read_text()
    except OSError:
        return tasks

    in_relevant_section = False
    stop_sections = {"completed", "deferred", "notes"}

    for raw_line in content.split("\n"):
        if raw_line.startswith("## "):
            section_lower = raw_line.lower()
            if any(kw in section_lower for kw in ["current focus", "next up", "blocked", "research", "infrastructure"]):
                in_relevant_section = True
            elif any(kw in section_lower for kw in stop_sections):
                in_relevant_section = False
            else:
                in_relevant_section = False
            continue

        if not in_relevant_section:
            continue

        if raw_line.startswith("  "):
            continue

        line = raw_line.strip()

        if not line.startswith("- "):
            continue

        match = re.search(r'\*\*(.+?)\*\*', line)
        if not match:
            continue
        task_name = match.group(1)

        is_done = line.startswith("- [x]") or "\u2705" in line
        is_blocked = "\u23f8\ufe0f" in line or "BLOCKED" in line.upper()
        is_wip = "IN PROGRESS" in line.upper() or "\U0001f504" in line

        if is_done:
            status = "DONE"
            color = "green"
        elif is_blocked:
            status = "BLOCKED"
            color = "red"
        elif is_wip:
            status = "IN PROG"
            color = "yellow"
        else:
            status = "NEXT"
            color = "dim"

        tasks.append({
            "name": task_name[:40],
            "status": status,
            "color": color,
        })

    priority_order = {"BLOCKED": 0, "IN PROG": 1, "NEXT": 2, "DONE": 3}
    tasks.sort(key=lambda t: priority_order.get(t["status"], 4))

    return tasks[:10]


def parse_active_tasks():
    """Cached task parser — refreshes every 15s (CTO P1: was parsing every 5s)."""
    return cached("active_tasks", _parse_active_tasks, ttl=15)


def get_next_action(tasks):
    """Determine the single most important next action (Teresa Torres OST pattern).

    Logic: Find the first non-DONE, non-BLOCKED task. If everything is blocked,
    surface the blocker. If everything is done, suggest moving to next project.
    """
    if not tasks:
        return "Open ACTIVE-TASKS.md and add your current focus", "yellow"

    # Find first blocked item — that's the real bottleneck
    blocked = [t for t in tasks if t["status"] == "BLOCKED"]
    wip = [t for t in tasks if t["status"] == "IN PROG"]
    next_up = [t for t in tasks if t["status"] == "NEXT"]

    if blocked:
        return f"UNBLOCK: {blocked[0]['name']}", "red bold"
    elif wip:
        return f"CONTINUE: {wip[0]['name']}", "yellow bold"
    elif next_up:
        return f"START: {next_up[0]['name']}", "cyan bold"
    else:
        return "All tasks done — check MASTER-ROADMAP-RANKING.md for next project", "green"


def _load_background_services():
    """Check PopChaos launchd services."""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        services = []
        for line in result.stdout.split("\n"):
            if "popchaos" in line.lower():
                parts = line.split()
                if len(parts) >= 3:
                    pid = parts[0]
                    exit_code = parts[1]
                    name = parts[2].replace("com.popchaos.", "")

                    if pid != "-":
                        status = "Running"
                        icon = "[green]OK[/green]"
                    elif exit_code != "0":
                        status = "Crashed"
                        icon = "[red]ERR[/red]"
                    else:
                        status = "Stopped"
                        icon = "[yellow]OFF[/yellow]"

                    friendly = name.replace("-", " ").replace("_", " ").title()

                    services.append({
                        "name": friendly,
                        "status": status,
                        "icon": icon,
                    })
        return services
    except Exception:
        return []


def check_background_services():
    """Cached background services — refreshes every 30s."""
    return cached("services", _load_background_services, ttl=30)


def _load_active_scraping_jobs():
    """Check for running scraping processes."""
    jobs = {"active": [], "completed": [], "failed": []}

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        scraper_keywords = [
            ("scrape_obsidian", "Obsidian Docs"),
            ("scrape-all", "Full Scrape"),
            ("scraper.py", "Web Scraper"),
            ("knowledge_scraper", "Knowledge Scraper"),
            ("auto_tag_corpus", "Auto Tagger"),
        ]

        for line in result.stdout.split("\n"):
            if "python" not in line:
                continue
            for keyword, friendly_name in scraper_keywords:
                if keyword in line and "grep" not in line:
                    pid = line.split()[1] if len(line.split()) > 1 else "?"
                    jobs["active"].append({
                        "name": friendly_name,
                        "pid": pid,
                    })
    except Exception:
        pass

    queue_path = SCRAPING_QUEUE
    if not queue_path.exists():
        queue_path = Path.home() / "Documents/Obsidian/SCRAPING-QUEUE.md"

    if queue_path.exists():
        try:
            content = queue_path.read_text()
            for line in content.split("\n"):
                if "Completed" in line and "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 2:
                        source = parts[1].strip()
                        if source and source != "Source":
                            jobs["completed"].append(source)
        except OSError:
            pass

    return jobs


def check_active_scraping_jobs():
    """Cached scraping jobs — refreshes every 10s."""
    return cached("scraping_jobs", _load_active_scraping_jobs, ttl=10)


def _load_system_memory():
    """Get system memory stats."""
    stats = {}
    try:
        result = subprocess.run(
            ["du", "-sh", "/private/tmp/claude-501"],
            capture_output=True, text=True, timeout=5,
        )
        stats["claude_temp"] = result.stdout.split()[0] if result.returncode == 0 else "N/A"

        result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            lines = result.stdout.split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    stats["disk_free"] = parts[3]
                    stats["disk_pct"] = parts[4]
    except Exception:
        stats["claude_temp"] = "N/A"
        stats["disk_free"] = "N/A"
        stats["disk_pct"] = "0%"

    return stats


def get_system_memory():
    """Cached system memory — refreshes every 15s."""
    return cached("system_memory", _load_system_memory, ttl=15)


def get_environmental_impact(month_responses):
    """Calculate environmental impact estimates."""
    co2_kg = (month_responses * CO2_PER_RESPONSE_G) / 1000
    miles_equiv = co2_kg * MILES_PER_KG_CO2

    if co2_kg < 0.5:
        level = "Low"
        color = "green"
    elif co2_kg < 2.0:
        level = "Moderate"
        color = "yellow"
    else:
        level = "High"
        color = "red"

    return {
        "co2_kg": round(co2_kg, 2),
        "miles": round(miles_equiv, 1),
        "level": level,
        "color": color,
    }


# === RENDER PANELS ===

def render_next_action_panel(action_text, action_style, warnings):
    """Render the Next Action banner — the single most important thing to do now."""
    text = Text()
    text.append("  >> ", style="bold")
    text.append(action_text, style=action_style)
    text.append(" <<", style="bold")

    # Show validation warnings if any
    if warnings:
        text.append(f"\n  Data warnings ({len(warnings)}):", style="red dim")
        for w in warnings[:2]:
            text.append(f"\n    ! {w}", style="red dim")

    return Panel(
        text,
        title="[bold white on dark_green]  NEXT ACTION  [/bold white on dark_green]",
        border_style="green",
        padding=(0, 1),
    )


def render_usage_panel(usage, env_impact, usage_warnings):
    """Render Usage & Limits panel — TOP of dashboard per user request."""
    text = Text()

    # Dynamic width for large numbers (QA BUG #11: overflow at 10000+)
    w = max(4, len(str(max(usage["today"], usage["week"], usage["month"], MONTHLY_LIMIT))))

    # Daily
    day_pct = min(100, int((usage["today"] / DAILY_LIMIT) * 100)) if DAILY_LIMIT else 0
    day_left = max(0, DAILY_LIMIT - usage["today"])
    day_color = "green" if day_pct < 70 else ("yellow" if day_pct < 90 else "red")
    text.append("  Today:      ", style="bold")
    text.append(f"{usage['today']:{w}} / {DAILY_LIMIT}", style=day_color)
    text.append(f"   ({day_left} left)\n", style="dim")

    # Weekly
    wk_pct = min(100, int((usage["week"] / WEEKLY_LIMIT) * 100)) if WEEKLY_LIMIT else 0
    wk_left = max(0, WEEKLY_LIMIT - usage["week"])
    wk_color = "green" if wk_pct < 70 else ("yellow" if wk_pct < 90 else "red")
    text.append("  This Week:  ", style="bold")
    text.append(f"{usage['week']:{w}} / {WEEKLY_LIMIT}", style=wk_color)
    text.append(f"   ({wk_left} left)\n", style="dim")

    # Monthly
    mo_pct = min(100, int((usage["month"] / MONTHLY_LIMIT) * 100)) if MONTHLY_LIMIT else 0
    mo_left = max(0, MONTHLY_LIMIT - usage["month"])
    mo_color = "green" if mo_pct < 70 else ("yellow" if mo_pct < 90 else "red")
    text.append("  This Month: ", style="bold")
    text.append(f"{usage['month']:{w}} / {MONTHLY_LIMIT}", style=mo_color)
    text.append(f"   ({mo_left} left)\n", style="dim")

    # Subscription
    text.append(f"\n  Plan: Max (${SUBSCRIPTION_COST:.0f}/mo)", style="dim")

    # Environmental impact
    text.append(f"   |   Carbon: ", style="dim")
    text.append(f"{env_impact['co2_kg']} kg CO2", style=env_impact["color"])
    text.append(f" ({env_impact['miles']} mi driven)\n", style="dim")

    # Usage warnings
    if usage_warnings:
        for w in usage_warnings:
            text.append(f"  ! {w}\n", style="red dim")

    return Panel(
        text,
        title="[bold cyan]  USAGE & LIMITS  [/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    )


def render_task_panel(tasks):
    """Render Task Priorities panel — shows top 10 from ACTIVE-TASKS.md."""
    table = Table(
        show_header=True,
        header_style="bold",
        box=None,
        padding=(0, 2),
        pad_edge=True,
    )
    table.add_column("Status", width=8, justify="center")
    table.add_column("Task", width=42)

    if not tasks:
        table.add_row("[dim]--[/dim]", "[dim]No tasks found[/dim]")
    else:
        for task in tasks:
            status_display = {
                "DONE": "[green]  DONE [/green]",
                "IN PROG": "[yellow]  WIP  [/yellow]",
                "BLOCKED": "[red] BLOCK [/red]",
                "NEXT": "[dim]  NEXT [/dim]",
            }.get(task.get("status", "???"), "[dim]  ???  [/dim]")

            safe_name = rich_escape(task['name'])
            table.add_row(status_display, f"[{task['color']}]{safe_name}[/{task['color']}]")

    return Panel(
        table,
        title="[bold magenta]  TASK PRIORITIES  [/bold magenta]",
        subtitle="[dim]Source: ACTIVE-TASKS.md[/dim]",
        border_style="magenta",
        padding=(0, 0),
    )


def render_kb_panel(stats, total, kb_warnings):
    """Render Knowledge Base panel with ACCURATE counts + validation."""
    text = Text()
    text.append(f"  Total: {total:,} articles", style="bold green")

    if kb_warnings:
        text.append(f"  (!) {len(kb_warnings)} warnings", style="red dim")
    text.append("\n\n")

    max_count = max(stats.values(), default=1) or 1
    for name, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        bar_len = min(20, int((count / max_count) * 20))
        bar = "\u2588" * bar_len
        text.append(f"  {name:<28} ", style="white")
        text.append(f"{count:>5,}", style="cyan bold")
        text.append(f"  {bar}\n", style="cyan dim")

    return Panel(
        text,
        title="[bold green]  KNOWLEDGE BASE  [/bold green]",
        border_style="green",
        padding=(0, 0),
    )


def render_sessions_panel(data):
    """Render Recent Sessions with CLEAR labels."""
    table = Table(
        show_header=True,
        header_style="bold",
        box=None,
        padding=(0, 1),
    )
    table.add_column("Session", width=12)
    table.add_column("Responses", justify="right", width=10)
    table.add_column("Last Active", width=18)
    table.add_column("Status", width=10)

    sessions = data.get("sessions", {})
    def _sort_key(item):
        val = item[1].get("last_response", 0)
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    items = sorted(
        sessions.items(),
        key=_sort_key,
        reverse=True,
    )[:10]

    for session_id, sdata in items:
        resp_count = sdata.get("response_count", 0)

        last_ts = sdata.get("last_response", 0)
        try:
            last_dt = datetime.fromtimestamp(last_ts)
            age_hours = (datetime.now() - last_dt).total_seconds() / 3600
            last_str = last_dt.strftime("%b %d  %H:%M")

            if age_hours < 1:
                status = "[green]Active[/green]"
            elif age_hours < 24:
                status = "[yellow]Recent[/yellow]"
            else:
                status = "[dim]Old[/dim]"
        except (ValueError, TypeError, OSError):
            last_str = "Unknown"
            status = "[dim]Unknown[/dim]"

        short_id = session_id.replace("session-", "")

        table.add_row(short_id, str(resp_count), last_str, status)

    return Panel(
        table,
        title="[bold blue]  RECENT SESSIONS  [/bold blue]",
        border_style="blue",
        padding=(0, 0),
    )


def render_jobs_panel(jobs):
    """Render Background Jobs panel."""
    text = Text()

    text.append("  Active:\n", style="bold yellow")
    if jobs["active"]:
        for job in jobs["active"]:
            text.append(f"    {job['name']}", style="green")
            text.append(f"  (PID {job['pid']})\n", style="dim")
    else:
        text.append("    None running\n", style="dim")

    text.append("\n")

    text.append("  Completed:\n", style="bold green")
    if jobs["completed"]:
        for name in jobs["completed"][:5]:
            text.append(f"    {name}\n", style="green dim")
        if len(jobs["completed"]) > 5:
            text.append(f"    +{len(jobs['completed']) - 5} more\n", style="dim")
    else:
        text.append("    None recorded\n", style="dim")

    return Panel(
        text,
        title="[bold yellow]  BACKGROUND JOBS  [/bold yellow]",
        border_style="yellow",
        padding=(0, 0),
    )


def render_system_panel(memory, services, error_summary):
    """Render combined System + Background Services + Data Health panel."""
    text = Text()

    # Memory
    text.append("  Memory:\n", style="bold")
    text.append(f"    Claude temp:  {memory.get('claude_temp', 'N/A')}\n", style="white")

    disk_pct = memory.get("disk_pct", "0%")
    try:
        pct_val = int(disk_pct.rstrip("%"))
        disk_color = "green" if pct_val < 75 else ("yellow" if pct_val < 90 else "red")
    except ValueError:
        disk_color = "white"
    text.append(f"    Disk free:    {memory.get('disk_free', 'N/A')} ", style="white")
    text.append(f"({disk_pct})\n", style=disk_color)

    text.append("\n")

    # Background services
    text.append("  Background Services:\n", style="bold")
    if services:
        for svc in services:
            text.append(f"    {svc['icon']}  {svc['name']}\n")
    else:
        text.append("    No services detected\n", style="dim")

    text.append("\n")

    # Data health (error log summary)
    err_count = error_summary.get("count", 0)
    text.append("  Data Health:\n", style="bold")
    if err_count == 0:
        text.append("    All checks passing\n", style="green")
    else:
        text.append(f"    {err_count} issue(s) in 24h\n", style="red")
        for err in error_summary.get("recent", [])[:2]:
            text.append(f"    ! {err.get('reason', '?')[:35]}\n", style="red dim")

    return Panel(
        text,
        title="[bold red]  SYSTEM  [/bold red]",
        border_style="red",
        padding=(0, 0),
    )


# === MAIN LAYOUT ===

def generate_layout():
    """Generate the full dashboard layout, priority-ordered per PRD."""
    # Load all data
    data = load_tracker_data()
    usage = get_usage_stats(data)
    env_impact = get_environmental_impact(usage["month"])
    kb_stats, kb_total = get_knowledge_base_stats()
    tasks = parse_active_tasks()
    services = check_background_services()
    jobs = check_active_scraping_jobs()
    memory = get_system_memory()
    error_summary = get_error_summary()
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    # Self-validation
    kb_warnings = validate_kb_counts(kb_stats)
    usage_warnings = validate_usage(usage, data)
    all_warnings = kb_warnings + usage_warnings

    # Next action recommendation
    action_text, action_style = get_next_action(tasks)

    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="next_action", size=5),
        Layout(name="usage", size=9),
        Layout(name="middle", size=15),
        Layout(name="bottom", size=14),
        Layout(name="footer", size=3),
    )

    # Header
    header = Text(justify="center")
    header.append("\n")
    header.append("  CLAUDE CODE DASHBOARD  ", style="bold white on blue")
    header.append(f"   {now}   ", style="dim")
    header.append("Updates every 5s", style="dim italic")
    layout["header"].update(Panel(header, style="blue"))

    # Next Action — the single most important thing (Teresa Torres OST)
    layout["next_action"].update(render_next_action_panel(action_text, action_style, all_warnings))

    # Usage & Limits
    layout["usage"].update(render_usage_panel(usage, env_impact, usage_warnings))

    # Middle row: Tasks + Knowledge Base
    layout["middle"].split_row(
        Layout(render_task_panel(tasks), name="tasks", ratio=1),
        Layout(render_kb_panel(kb_stats, kb_total, kb_warnings), name="kb", ratio=1),
    )

    # Bottom row: Sessions + Jobs + System
    layout["bottom"].split_row(
        Layout(render_sessions_panel(data), name="sessions", ratio=2),
        Layout(render_jobs_panel(jobs), name="jobs", ratio=1),
        Layout(render_system_panel(memory, services, error_summary), name="system", ratio=1),
    )

    # Footer
    footer = Text(justify="center")
    footer.append("\n")
    footer.append("  Ctrl+C to exit  ", style="dim")
    footer.append("|", style="dim")
    footer.append(f"  Last refresh: {now}  ", style="dim italic")
    footer.append("|", style="dim")
    now_dt = datetime.now()
    if now_dt.weekday() == 4:  # Friday
        footer.append("  Weekly review: What did the dashboard miss this week?", style="yellow dim")
    else:
        days_to_fri = (4 - now_dt.weekday()) % 7
        footer.append(f"  Review in {days_to_fri}d", style="dim")
    layout["footer"].update(Panel(footer, style="dim"))

    return layout


LOCKFILE = Path.home() / ".claude/.locks/dashboard_v2.pid"


def _acquire_lock():
    """Acquire PID lockfile. Returns True if lock acquired, False if another instance running."""
    LOCKFILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCKFILE.exists():
        try:
            old_pid = int(LOCKFILE.read_text().strip())
            # Check if the old process is still running
            os.kill(old_pid, 0)
            return False  # Process still alive
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass  # Stale lockfile, safe to overwrite
    LOCKFILE.write_text(str(os.getpid()))
    return True


def _release_lock():
    """Release PID lockfile."""
    try:
        if LOCKFILE.exists() and LOCKFILE.read_text().strip() == str(os.getpid()):
            LOCKFILE.unlink()
    except OSError:
        pass


def main():
    """Run the dashboard with proper live updating (no infinite scroll)."""
    if not _acquire_lock():
        console.print("[red]Another dashboard instance is already running.[/red]")
        console.print(f"[dim]Lock file: {LOCKFILE}[/dim]")
        console.print("[dim]If this is wrong, delete the lock file and try again.[/dim]")
        return

    consecutive_errors = 0
    max_consecutive_errors = 5

    try:
        with Live(generate_layout(), refresh_per_second=0.2, screen=True) as live:
            while True:
                time.sleep(5)
                try:
                    live.update(generate_layout())
                    consecutive_errors = 0
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    consecutive_errors += 1
                    log_error("main_loop", "clean render", str(e), f"render crash #{consecutive_errors}")
                    if consecutive_errors >= max_consecutive_errors:
                        console.print(f"\n[red]Dashboard crashed {max_consecutive_errors}x in a row: {e}[/red]\n")
                        break
                    # Show error inline instead of crashing
                    error_text = Text(f"\n  Dashboard render error: {e}\n  Retrying in 5s... ({consecutive_errors}/{max_consecutive_errors})", style="red")
                    live.update(Panel(error_text, title="[red]ERROR[/red]", border_style="red"))
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]\n")
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
