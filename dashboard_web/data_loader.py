#!/usr/bin/env python3
"""Data loader for web dashboard — shared data module.

Ports data loading logic from dashboard_v2.py (terminal dashboard),
removes all rich dependency, outputs JSON-serializable dicts.

CRITICAL FIX: Reads KB sources dynamically from data-sources.json
instead of hardcoded 6-source dict (was missing 83% of KB).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# === CONFIGURATION ===

HOME = Path.home()
BUDGET_STATE = HOME / ".claude/.locks/.budget-state.json"
ACTIVE_TASKS = HOME / "Documents/Obsidian/ACTIVE-TASKS.md"
SCRAPING_QUEUE = HOME / "Documents/Obsidian/process/SCRAPING-QUEUE.md"
ERROR_LOG = HOME / ".claude/.locks/dashboard_errors.json"
DATA_SOURCES = HOME / ".claude/data-sources.json"
TRACKER_SCRIPT = HOME / "Development/tools/track_resources.py"

SUBSCRIPTION_COST = 200.00
FIVE_HOUR_TOKEN_BUDGET = 500_000

# === CACHING ===

_cache = {}
_cache_ttl = {}
CACHE_TTL_SECONDS = {
    "kb_stats": 60,
    "services": 30,
    "system_memory": 15,
    "scraping_jobs": 10,
    "tracker_data": 10,
    "active_tasks": 15,
    "error_summary": 30,
    "all_data": 0.5,   # 500ms for the combined API endpoint
    "kb_data": 60,     # 60s for KB-only endpoint
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


# === SAFE GLOB WITH TIMEOUT ===

class GlobTimeout(Exception):
    pass


def safe_glob(path, pattern, timeout_sec=5):
    """Glob with timeout protection (thread-safe — no SIGALRM).

    Uses a worker thread instead of signal.alarm so it works inside
    Flask's threaded request handler.
    """
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    def _do_glob():
        return list(path.glob(pattern))

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_glob)
            return future.result(timeout=timeout_sec)
    except FuturesTimeout:
        log_error("glob", f"{path}/{pattern}", "timeout", f"glob timed out after {timeout_sec}s")
        return []
    except OSError:
        return []


# === ERROR LOGGING ===

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
    errors = errors[-100:]

    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=ERROR_LOG.parent, suffix='.json')
        with os.fdopen(fd, 'w') as f:
            json.dump(errors, f, indent=2)
        os.replace(tmp_path, ERROR_LOG)
    except OSError:
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
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        recent = [e for e in errors if e.get("timestamp", "") > cutoff]
        return {"count": len(recent), "recent": recent[-3:]}
    except (json.JSONDecodeError, OSError):
        return {"count": 0, "recent": []}


def get_error_summary():
    return cached("error_summary", _get_error_summary, ttl=30)


# === DYNAMIC KB SOURCE LOADING (THE FIX) ===

def load_kb_sources_from_json():
    """Load ALL KB sources dynamically from data-sources.json.

    This is the critical fix: dashboard_v2.py hardcoded 6 sources,
    missing 83% of the actual knowledge base. This reads them all.
    """
    if not DATA_SOURCES.exists():
        return {}

    try:
        raw = json.loads(DATA_SOURCES.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    sources = {}
    for entry in raw.get("sources", []):
        # Skip comment entries and non-active/scraping sources
        if "_comment" in entry:
            continue

        source_id = entry.get("id", "")
        status = entry.get("status", "")
        local_path = entry.get("local_path", "")
        skill = entry.get("skill", "unknown")
        article_count = entry.get("article_count", 0)

        # Only include sources that have been scraped (active or scraping)
        if status not in ("active", "scraping"):
            continue

        if not local_path:
            continue

        # Expand ~ to home directory
        expanded_path = Path(local_path.replace("~", str(HOME)))

        # Build a friendly name from the id
        friendly_name = source_id.replace("-", " ").replace("_", " ").title()

        sources[friendly_name] = {
            "path": expanded_path,
            "skill": skill,
            "declared_count": article_count,
            "id": source_id,
        }

    return sources


def _count_articles_in_dir(path):
    """Count markdown files in a directory (the actual article count)."""
    if not path.exists():
        return 0

    # Try common patterns: articles subdir, then root .md files
    patterns = [
        "articles/*.md",
        "episodes/**/*.md",
        "**/*.md",
    ]

    # First check if there's an articles/ subdir
    articles_dir = path / "articles"
    if articles_dir.exists():
        return len(safe_glob(articles_dir, "*.md", timeout_sec=3))

    # Check for episodes/ subdir (podcasts)
    episodes_dir = path / "episodes"
    if episodes_dir.exists():
        return len(safe_glob(episodes_dir, "**/*.md", timeout_sec=3))

    # Fallback: count all .md at root (not recursive, avoids counting READMEs in subdirs)
    count = len(safe_glob(path, "*.md", timeout_sec=3))
    if count > 0:
        return count

    # Last resort: recursive .md
    return len(safe_glob(path, "**/*.md", timeout_sec=5))


def _load_knowledge_base_stats():
    """Count articles across ALL knowledge bases using dynamic sources.

    Groups by advisor skill for the web dashboard display.
    """
    sources = load_kb_sources_from_json()
    stats = {}
    by_skill = {}
    total = 0

    for name, config in sources.items():
        path = config["path"]
        skill = config["skill"]
        declared = config["declared_count"]

        # Use declared count from data-sources.json if directory doesn't exist
        # (some sources may have article_count but no local files yet)
        if path.exists():
            count = _count_articles_in_dir(path)
        elif declared > 0:
            count = declared
        else:
            count = 0

        if count > 0:
            stats[name] = count
            total += count
            if skill not in by_skill:
                by_skill[skill] = {"sources": [], "total": 0}
            by_skill[skill]["sources"].append({"name": name, "count": count})
            by_skill[skill]["total"] += count

    # Add Obsidian vault as a special source
    obsidian_path = HOME / "Documents/Obsidian"
    if obsidian_path.exists():
        obsidian_count = len(safe_glob(obsidian_path, "**/*.md", timeout_sec=5))
        if obsidian_count > 0:
            stats["Obsidian Vault"] = obsidian_count
            total += obsidian_count
            if "system" not in by_skill:
                by_skill["system"] = {"sources": [], "total": 0}
            by_skill["system"]["sources"].append({"name": "Obsidian Vault", "count": obsidian_count})
            by_skill["system"]["total"] += obsidian_count

    return stats, total, by_skill


def get_knowledge_base_stats():
    return cached("kb_stats", _load_knowledge_base_stats, ttl=60)


# === BUDGET / USAGE ===

def _load_tracker_data():
    """Load budget state from .budget-state.json."""
    if not BUDGET_STATE.exists():
        return None
    try:
        return json.loads(BUDGET_STATE.read_text())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def load_tracker_data():
    return cached("tracker_data", _load_tracker_data, ttl=10)


def get_usage_stats(data):
    """Extract 5-hour window, since-last-gap, and lifetime from budget state JSON."""
    empty_gap = {
        "tokens_used": 0, "messages": 0, "gap_started": None,
        "carbon_g": 0, "wh": 0,
    }
    empty_lifetime = {
        "total_tokens": 0, "total_messages": 0, "total_sessions": 0,
        "first_session": None, "total_carbon_g": 0, "total_wh": 0,
    }

    if data is None:
        return {
            "percentage": 0,
            "tokens_used": 0,
            "budget": FIVE_HOUR_TOKEN_BUDGET,
            "remaining": FIVE_HOUR_TOKEN_BUDGET,
            "messages": 0,
            "window_carbon_g": 0,
            "window_wh": 0,
            "model_recommendation": "opus",
            "alert_level": "ok",
            "weekly_opus_tokens": 0,
            "weekly_opus_messages": 0,
            "weekly_sonnet_tokens": 0,
            "weekly_sonnet_messages": 0,
            "since_last_gap": empty_gap,
            "lifetime": empty_lifetime,
        }

    window = data.get("five_hour_window", {})
    weekly = data.get("weekly", {})
    since_gap = data.get("since_last_gap", empty_gap)
    lifetime = data.get("lifetime", empty_lifetime)

    return {
        "percentage": window.get("percentage", 0),
        "tokens_used": window.get("tokens_used", 0),
        "budget": window.get("budget", FIVE_HOUR_TOKEN_BUDGET),
        "remaining": window.get("remaining", FIVE_HOUR_TOKEN_BUDGET),
        "messages": window.get("messages", 0),
        "window_carbon_g": window.get("carbon_g", 0),
        "window_wh": window.get("wh", 0),
        "model_recommendation": data.get("model_recommendation", "opus"),
        "alert_level": data.get("alert_level", "ok"),
        "weekly_opus_tokens": weekly.get("opus_tokens", 0),
        "weekly_opus_messages": weekly.get("opus_messages", 0),
        "weekly_sonnet_tokens": weekly.get("sonnet_tokens", 0),
        "weekly_sonnet_messages": weekly.get("sonnet_messages", 0),
        "since_last_gap": since_gap,
        "lifetime": lifetime,
    }


def get_budget_age_minutes():
    """Return the age of the budget state file in minutes."""
    if not BUDGET_STATE.exists():
        return None
    try:
        mtime = BUDGET_STATE.stat().st_mtime
        return (time.time() - mtime) / 60
    except OSError:
        return None


# === ENVIRONMENTAL IMPACT ===

def co2_equivalence(co2_g):
    """Convert CO2 grams to a relatable real-world equivalent."""
    if co2_g < 1:
        return "< 1 Google search"
    elif co2_g < 8:
        searches = co2_g / 0.3
        return f"~{searches:.0f} Google searches"
    elif co2_g < 36:
        charges = co2_g / 8
        if charges < 1.5:
            return "~1 smartphone charge"
        return f"~{charges:.0f} smartphone charges"
    elif co2_g < 200:
        hours = co2_g / 36
        if hours < 1.5:
            return "~1 hr Netflix streaming"
        return f"~{hours:.0f} hrs Netflix streaming"
    else:
        miles = co2_g / 404
        if miles < 1:
            return f"~{miles:.1f} miles driving"
        return f"~{miles:.0f} miles driving"


def get_environmental_impact(data):
    """Read environmental impact from budget state JSON."""
    if data is None:
        return {"co2_g": 0, "wh": 0, "level": "Unknown", "color": "gray", "equiv": ""}

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
        "equiv": co2_equivalence(co2_g),
    }


# === TASKS ===

def _parse_active_tasks():
    """Parse top tasks from ACTIVE-TASKS.md."""
    tasks = []
    if not ACTIVE_TASKS.exists():
        return tasks

    try:
        if ACTIVE_TASKS.stat().st_size > 1_000_000:
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
        elif is_blocked:
            status = "BLOCKED"
        elif is_wip:
            status = "IN PROG"
        else:
            status = "NEXT"

        tasks.append({
            "name": task_name[:50],
            "status": status,
        })

    priority_order = {"BLOCKED": 0, "IN PROG": 1, "NEXT": 2, "DONE": 3}
    tasks.sort(key=lambda t: priority_order.get(t["status"], 4))
    return tasks[:10]


def parse_active_tasks():
    return cached("active_tasks", _parse_active_tasks, ttl=15)


def get_next_action(tasks):
    """Determine the single most important next action (Teresa Torres OST)."""
    if not tasks:
        return {"text": "Open ACTIVE-TASKS.md and add your current focus", "level": "warning"}

    blocked = [t for t in tasks if t["status"] == "BLOCKED"]
    wip = [t for t in tasks if t["status"] == "IN PROG"]
    next_up = [t for t in tasks if t["status"] == "NEXT"]

    if blocked:
        return {"text": f"UNBLOCK: {blocked[0]['name']}", "level": "error"}
    elif wip:
        return {"text": f"CONTINUE: {wip[0]['name']}", "level": "warning"}
    elif next_up:
        return {"text": f"START: {next_up[0]['name']}", "level": "info"}
    else:
        return {"text": "All tasks done - check MASTER-ROADMAP-RANKING.md", "level": "ok"}


# === BACKGROUND SERVICES & JOBS ===

def _load_background_services():
    """Check PopChaos launchd services."""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=2,
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
                    elif exit_code != "0":
                        status = "Crashed"
                    else:
                        status = "Stopped"

                    services.append({
                        "name": name.replace("-", " ").replace("_", " ").title(),
                        "status": status,
                    })
        return services
    except Exception:
        return []


def check_background_services():
    return cached("services", _load_background_services, ttl=30)


def _load_active_scraping_jobs():
    """Check for running scraping processes."""
    jobs = {"active": [], "completed": [], "failed": []}

    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True, text=True, timeout=2,
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
                    jobs["active"].append({"name": friendly_name, "pid": pid})
    except Exception:
        pass

    queue_path = SCRAPING_QUEUE
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
    return cached("scraping_jobs", _load_active_scraping_jobs, ttl=10)


# === SYSTEM ===

def _load_system_memory():
    """Get system disk stats."""
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
    return cached("system_memory", _load_system_memory, ttl=15)


# === VALIDATION ===

def validate_data(usage, kb_stats):
    """Validate data and return warnings list."""
    warnings = []

    # Check budget data age
    age = get_budget_age_minutes()
    if age is not None and age > 5:
        warnings.append(f"Budget data is {int(age)}m old")

    if usage["percentage"] > 200:
        warnings.append(f"Window percentage suspiciously high: {usage['percentage']:.0f}%")

    return warnings


# === REFRESH ===

def refresh_budget_data():
    """Run track_resources.py in the background to update .budget-state.json."""
    if not TRACKER_SCRIPT.exists():
        return False
    try:
        subprocess.Popen(
            [sys.executable, str(TRACKER_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


# === AGGREGATE (for /api/data) ===

def get_all_dashboard_data():
    """Load all dashboard data into a single JSON-serializable dict."""
    data = load_tracker_data()
    usage = get_usage_stats(data)
    env_impact = get_environmental_impact(data)
    kb_stats, kb_total, kb_by_skill = get_knowledge_base_stats()
    tasks = parse_active_tasks()
    next_action = get_next_action(tasks)
    services = check_background_services()
    jobs = check_active_scraping_jobs()
    memory = get_system_memory()
    error_summary = get_error_summary()
    warnings = validate_data(usage, kb_stats)
    budget_age = get_budget_age_minutes()

    return {
        "timestamp": datetime.now().isoformat(),
        "next_action": next_action,
        "usage": usage,
        "environmental": env_impact,
        "kb": {
            "stats": kb_stats,
            "total": kb_total,
            "by_skill": kb_by_skill,
            "source_count": len(kb_stats),
        },
        "tasks": tasks,
        "services": services,
        "jobs": jobs,
        "system": memory,
        "errors": error_summary,
        "warnings": warnings,
        "budget_age_minutes": round(budget_age, 1) if budget_age else None,
        "budget_state": {
            "generated": data.get("generated", "") if data else "",
            "alert_level": data.get("alert_level", "ok") if data else "ok",
        },
    }
