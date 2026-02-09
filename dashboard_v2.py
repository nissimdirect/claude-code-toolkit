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

BUDGET_STATE = Path.home() / ".claude/.locks/.budget-state.json"
ACTIVE_TASKS = Path.home() / "Documents/Obsidian/ACTIVE-TASKS.md"
SCRAPING_QUEUE = Path.home() / "Documents/Obsidian/process/SCRAPING-QUEUE.md"
ERROR_LOG = Path.home() / ".claude/.locks/dashboard_errors.json"

# Subscription model (Max plan)
SUBSCRIPTION_COST = 200.00
FIVE_HOUR_TOKEN_BUDGET = 220_000

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

    if not BUDGET_STATE.exists():
        warnings.append("Budget state file missing — run track_resources.py")
        return warnings

    try:
        mtime = BUDGET_STATE.stat().st_mtime
        age_min = (time.time() - mtime) / 60
        if age_min > 30:
            warnings.append(f"Budget data is {int(age_min)}m old — run track_resources.py")
            log_error("usage", "recent data", f"{int(age_min)}m old", "stale budget state")
    except OSError:
        pass

    # Sanity: percentage shouldn't exceed 100 by much
    if usage["percentage"] > 110:
        warnings.append(f"Window percentage suspiciously high: {usage['percentage']:.0f}%")
        log_error("usage", "<110%", usage["percentage"], "suspicious percentage")

    return warnings


# === DATA LOADERS ===

def _load_tracker_data():
    """Load budget state from .budget-state.json (written by track_resources.py)."""
    if not BUDGET_STATE.exists():
        return None
    try:
        return json.loads(BUDGET_STATE.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def load_tracker_data():
    """Cached tracker data — refreshes every 10s (CTO P1: was reading every 5s)."""
    return cached("tracker_data", _load_tracker_data, ttl=10)


def get_usage_stats(data):
    """Extract 5-hour window usage from budget state JSON."""
    if data is None:
        return {
            "percentage": 0,
            "tokens_used": 0,
            "budget": FIVE_HOUR_TOKEN_BUDGET,
            "remaining": FIVE_HOUR_TOKEN_BUDGET,
            "messages": 0,
            "model_recommendation": "opus",
            "alert_level": "ok",
            "weekly_opus_tokens": 0,
            "weekly_opus_messages": 0,
            "weekly_sonnet_tokens": 0,
            "weekly_sonnet_messages": 0,
        }

    window = data.get("five_hour_window", {})
    weekly = data.get("weekly", {})

    return {
        "percentage": window.get("percentage", 0),
        "tokens_used": window.get("tokens_used", 0),
        "budget": window.get("budget", FIVE_HOUR_TOKEN_BUDGET),
        "remaining": window.get("remaining", FIVE_HOUR_TOKEN_BUDGET),
        "messages": window.get("messages", 0),
        "model_recommendation": data.get("model_recommendation", "opus"),
        "alert_level": data.get("alert_level", "ok"),
        "weekly_opus_tokens": weekly.get("opus_tokens", 0),
        "weekly_opus_messages": weekly.get("opus_messages", 0),
        "weekly_sonnet_tokens": weekly.get("sonnet_tokens", 0),
        "weekly_sonnet_messages": weekly.get("sonnet_messages", 0),
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


def get_environmental_impact(data):
    """Read environmental impact from budget state JSON."""
    if data is None:
        return {"co2_g": 0, "wh": 0, "level": "Unknown", "color": "dim"}

    env = data.get("environmental", {})
    co2_g = env.get("total_carbon_g", 0)
    wh = env.get("total_wh", 0)

    if co2_g < 500:
        level = "Low"
        color = "green"
    elif co2_g < 2000:
        level = "Moderate"
        color = "yellow"
    else:
        level = "High"
        color = "red"

    return {
        "co2_g": round(co2_g, 1),
        "wh": round(wh, 1),
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
    """Render Usage & Limits panel — 5-hour rolling window + model recommendation."""
    text = Text()

    pct = usage["percentage"]
    remaining = usage["remaining"]
    tokens_used = usage["tokens_used"]
    budget = usage["budget"]
    model_rec = usage["model_recommendation"]
    alert_level = usage["alert_level"]

    # Color based on alert level
    level_colors = {
        "ok": "green", "info": "cyan", "warning": "yellow",
        "critical": "red", "limit": "red bold",
    }
    bar_color = level_colors.get(alert_level, "white")

    # Progress bar
    bar_width = 30
    filled = int(min(pct, 100) / 100 * bar_width)
    bar = "\u2588" * filled + "\u2591" * (bar_width - filled)

    text.append("  5-Hour Window: ", style="bold")
    text.append(bar, style=bar_color)
    text.append(f"  {pct:.0f}%\n", style=bar_color + " bold")

    text.append(f"  Tokens:   {tokens_used:>10,} / {budget:,}", style=bar_color)
    text.append(f"   ({remaining:,} left)\n", style="dim")
    text.append(f"  Messages: {usage['messages']}\n", style="dim")

    # Model recommendation
    text.append("\n  Model: ", style="bold")
    rec_styles = {
        "opus": ("green", "Opus (full power)"),
        "sonnet": ("yellow", "Sonnet recommended (save budget)"),
        "wind_down": ("red bold", "WIND DOWN — close agents"),
    }
    rec_style, rec_label = rec_styles.get(model_rec, ("white", model_rec))
    text.append(rec_label, style=rec_style)
    text.append("\n")

    # Weekly breakdown
    text.append(f"\n  Weekly: ", style="bold")
    text.append(f"Opus {usage['weekly_opus_tokens']:,}tok/{usage['weekly_opus_messages']}msg", style="dim")
    text.append(f"  |  ", style="dim")
    text.append(f"Sonnet {usage['weekly_sonnet_tokens']:,}tok/{usage['weekly_sonnet_messages']}msg\n", style="dim")

    # Subscription + environmental
    text.append(f"  Plan: Max (${SUBSCRIPTION_COST:.0f}/mo)", style="dim")
    text.append(f"   |   ", style="dim")
    text.append(f"{env_impact['wh']:.0f} Wh", style="dim")
    text.append(f"  |  ", style="dim")
    text.append(f"{env_impact['co2_g']:.0f}g CO2", style=env_impact["color"])
    text.append("\n")

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
    """Render budget state info panel."""
    text = Text()

    if data is None:
        text.append("  No budget data available.\n", style="dim")
        text.append("  Run: python3 ~/Development/tools/track_resources.py\n", style="dim")
    else:
        # Show when data was generated
        generated = data.get("generated", "Unknown")
        if generated != "Unknown":
            try:
                gen_dt = datetime.fromisoformat(generated.replace("Z", "+00:00"))
                age_min = (datetime.now(gen_dt.tzinfo) - gen_dt).total_seconds() / 60
                text.append("  Data Age: ", style="bold")
                if age_min < 5:
                    text.append(f"{age_min:.0f}m ago", style="green")
                elif age_min < 30:
                    text.append(f"{age_min:.0f}m ago", style="yellow")
                else:
                    text.append(f"{age_min:.0f}m ago (stale)", style="red")
                text.append("\n")
            except (ValueError, TypeError):
                text.append(f"  Generated: {generated}\n", style="dim")

        # Alert level indicator
        alert = data.get("alert_level", "ok")
        alert_display = {
            "ok": ("[green]OK[/green]", "Budget healthy"),
            "info": ("[cyan]INFO[/cyan]", "Budget above 50%"),
            "warning": ("[yellow]WARNING[/yellow]", "Switch to Sonnet"),
            "critical": ("[red]CRITICAL[/red]", "Sonnet only"),
            "limit": ("[red bold]LIMIT[/red bold]", "Wind down now"),
        }
        icon, desc = alert_display.get(alert, ("[dim]?[/dim]", "Unknown"))
        text.append(f"\n  Alert: {icon}  ", style="bold")
        text.append(f"{desc}\n", style="dim")

        # Environmental breakdown
        env = data.get("environmental", {})
        text.append(f"\n  Energy:  {env.get('total_wh', 0):.0f} Wh (lifetime)\n", style="dim")
        text.append(f"  Carbon:  {env.get('total_carbon_g', 0):.0f}g CO2e\n", style="dim")

        text.append(f"\n  Source: .budget-state.json\n", style="dim")

    return Panel(
        text,
        title="[bold blue]  BUDGET STATE  [/bold blue]",
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
    env_impact = get_environmental_impact(data)
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
        Layout(name="usage", size=12),
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
    import subprocess
    LOCKFILE.parent.mkdir(parents=True, exist_ok=True)

    # Check 1: Is another dashboard_v2.py process already running (regardless of lock file)?
    try:
        result = subprocess.run(
            ["pgrep", "-f", "dashboard_v2.py"],
            capture_output=True, text=True, timeout=5
        )
        running_pids = [
            int(p) for p in result.stdout.strip().split("\n")
            if p.strip() and int(p) != os.getpid()
        ]
        if running_pids:
            # Update lock file to reflect actual running PID
            LOCKFILE.write_text(str(running_pids[0]))
            return False  # Another instance is genuinely running
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass

    # Check 2: Lock file PID check (fallback)
    if LOCKFILE.exists():
        try:
            old_pid = int(LOCKFILE.read_text().strip())
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
