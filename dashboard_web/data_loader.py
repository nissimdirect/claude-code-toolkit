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
DELEGATION_AUDIT_LOG = HOME / ".claude/.locks/delegation-hook-audit.log"
DELEGATION_EVAL_LOG = HOME / ".claude/.locks/gemini-route-eval.jsonl"
DELEGATION_COUNTER = HOME / ".claude/.locks/gemini-daily-counter.json"
DELEGATION_COMPLIANCE = HOME / ".claude/.locks/delegation-compliance.json"
DELEGATION_DISABLED = HOME / ".claude/.locks/gemini-route-disabled.json"

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
    "delegation_stats": 10,
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


# === KB SOURCE LOADING — FILESYSTEM SCAN (GROUND TRUTH) ===

# Directory name → advisor skill mapping.
# data-sources.json is for the SCRAPER config, not the dashboard.
# The dashboard scans the filesystem directly and maps to skills.
DIR_TO_SKILL = {
    # Art Director
    "fonts-in-use": "art-director",
    "art-direction": "art-director",
    "brand-new": "art-director",
    "lukew": "art-director",
    "smashing-mag": "art-director",
    "art-director": "art-director",
    "art-portfolio": "art-director",
    "the-brand-identity": "art-director",
    "its-nice-that": "art-director",
    # Atrium (art criticism)
    "art-criticism": "atrium",
    "atrium": "atrium",
    "creative-independent": "atrium",
    "creative-interviews": "atrium",
    "hyperallergic": "atrium",
    "e-flux": "atrium",
    "bomb-magazine": "atrium",
    "bomb-magazine-interviews": "atrium",
    "texte-zur-kunst": "atrium",
    "momus": "atrium",
    "usa-fellows": "atrium",
    "cc-awardees": "atrium",
    "artadia": "atrium",
    "ubuweb": "atrium",
    "situationist": "atrium",
    "creative-capital": "atrium",
    "stanford-aesthetics": "atrium",
    "creative-review": "atrium",
    "design-observer": "atrium",
    "creative-boom": "atrium",
    "david-lynch": "atrium",
    # Don Norman (UX)
    "ux-design": "don-norman",
    "don-norman": "don-norman",
    "nngroup": "don-norman",
    "a-list-apart": "don-norman",
    "baymard": "don-norman",
    "laws-of-ux": "don-norman",
    "ux-myths": "don-norman",
    "deceptive-design": "don-norman",
    # Music Biz (combined cherie + jesse + ari)
    "music-business": "music-biz",
    "music-marketing": "music-biz",
    "cherie-hu": "music-biz",
    "jesse-cannon": "music-biz",
    "jesse-cannon-test": "music-biz",
    # Audio Production (DSP, mixing, mastering, engineering)
    "audio-production": "audio-production",
    # Music Composer (composition, production techniques, electronic music)
    "music-production": "music-composer",
    # CTO
    "cto": "cto",
    "cto-leaders": "cto",
    "security-leaders": "cto",
    "plugin-devs": "cto",
    "airwindows": "cto",
    "valhalla-dsp": "cto",
    "fabfilter": "cto",
    "circuit-modeling": "cto",
    # Ask Lenny
    "lenny": "ask-lenny",
    "lennys-podcast-transcripts": "ask-lenny",
    "lennys-newsletter": "ask-lenny",
    # ChatPRD
    "chatprd-blog": "ask-chatprd",
    # Indie Trinity
    "indie-hackers": "ask-indie-trinity",
    # Marketing
    "marketing-hacker": "marketing-hacker",
    # Creative
    "chaos-strategies": "creative",
    "brian-eno": "creative",
    # Music Composer
    "music-composer": "music-composer",
    # System/reference
    "obsidian-docs": "system",
    "YouTubeTranscripts": "system",
    "tools": "system",
}

# Directories to skip (not KB content)
SKIP_DIRS = {
    "AI-Knowledge-Exchange", "claude-code-toolkit", "entropic",
    "JUCE", "test-scrape-fixed", "fan-capture-mvp", "lyric-analyst",
    "ghostwriter", "references", "shared-brain", "qwen", "gemini",
    "cymatics", "dashboard_web",
}


def _fast_count_md(path):
    """Count .md files using subprocess (handles 30K+ files without timeout)."""
    try:
        result = subprocess.run(
            ["find", str(path), "-name", "*.md", "-type", "f"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            return len([l for l in lines if l])
        return 0
    except (subprocess.TimeoutExpired, OSError):
        return 0


def _scan_kb_directories():
    """Scan ~/Development/ for ALL KB directories and map to skills.

    This is the ground truth — counts actual .md files on disk,
    not what data-sources.json claims. data-sources.json is scraper
    config; the dashboard shows reality.
    """
    dev_dir = HOME / "Development"
    if not dev_dir.exists():
        return {}

    sources = {}
    seen_paths = set()

    for child in sorted(dev_dir.iterdir()):
        if not child.is_dir():
            continue
        dirname = child.name
        if dirname.startswith(".") or dirname in SKIP_DIRS:
            continue

        # Check if this is a parent dir with sub-sources (cto-leaders/, etc.)
        skill = DIR_TO_SKILL.get(dirname)
        if skill and dirname in ("cto-leaders", "security-leaders", "indie-hackers"):
            # Scan subdirectories as individual sources
            for sub in sorted(child.iterdir()):
                if not sub.is_dir() or sub.name.startswith("."):
                    continue
                count = _fast_count_md(sub)
                if count > 0:
                    friendly = sub.name.replace("-", " ").replace("_", " ").title()
                    sources[friendly] = {"path": sub, "skill": skill, "count": count}
                    seen_paths.add(str(sub))
            continue

        # Regular directory
        count = _fast_count_md(child)
        if count < 3:
            continue  # Skip dirs with <3 .md files (not real KB)

        if skill is None:
            skill = "unclassified"

        friendly = dirname.replace("-", " ").replace("_", " ").title()
        sources[friendly] = {"path": child, "skill": skill, "count": count}
        seen_paths.add(str(child))

    return sources


def _load_knowledge_base_stats():
    """Count articles across ALL knowledge bases by scanning the filesystem.

    Groups by advisor skill for the web dashboard display.
    Ground truth = what's on disk, not what config files claim.
    """
    sources = _scan_kb_directories()
    stats = {}
    by_skill = {}
    total = 0

    for name, info in sources.items():
        count = info["count"]
        skill = info["skill"]

        stats[name] = count
        total += count
        if skill not in by_skill:
            by_skill[skill] = {"sources": [], "total": 0}
        by_skill[skill]["sources"].append({"name": name, "count": count})
        by_skill[skill]["total"] += count

    # Add Obsidian vault as a special source
    obsidian_path = HOME / "Documents/Obsidian"
    if obsidian_path.exists():
        obsidian_count = _fast_count_md(obsidian_path)
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


# === CURRENT SESSION ===

def _find_current_session():
    """Find the most recently active JSONL session file.

    Returns stats for the session actively being written to (mtime within
    last 5 minutes). This represents 'this session' for the dashboard.
    """
    projects_dir = HOME / ".claude" / "projects"
    if not projects_dir.exists():
        return None

    best = None
    best_mtime = 0
    cutoff = time.time() - 300  # 5 min

    for d in projects_dir.iterdir():
        if not d.is_dir():
            continue
        for f in d.glob("*.jsonl"):
            if "subagents" in str(f):
                continue
            try:
                mt = f.stat().st_mtime
                if mt > cutoff and mt > best_mtime:
                    best = f
                    best_mtime = mt
            except OSError:
                continue

    if not best:
        return None

    # Parse token usage from this session
    tokens = 0
    messages = 0
    try:
        with open(best, 'r') as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    usage = record.get('message', {}).get('usage', {})
                    inp = usage.get('input_tokens', 0)
                    out = usage.get('output_tokens', 0)
                    if inp > 0 or out > 0:
                        tokens += inp + out
                        messages += 1
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        return None

    return {
        "session_id": best.stem[:8],
        "tokens": tokens,
        "messages": messages,
        "file": str(best),
    }


def get_current_session_stats():
    return cached("current_session", _find_current_session, ttl=5)


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


# === DELEGATION STATS ===

def _load_delegation_stats():
    """Load Gemini template routing and delegation hook stats."""
    data = {
        "hook_fires": 0,
        "prefetched": 0,
        "avg_latency_ms": 0,
        "route_calls": 0,
        "route_success": 0,
        "route_success_pct": 0,
        "est_tokens_saved": 0,
        "gemini_today": 0,
        "gemini_date": "",
        "gemini_cap": 250,
        "delegation_rate": "0%",
        "total_prompts": 0,
        "by_category": {},
        "by_action": {},
        "by_model": {},
        "by_exec": {},
        "disabled_templates": [],
        "warned_templates": [],
        "session_tokens_saved": 0,
        "session_route_calls": 0,
        "session_claude_tokens": 0,
        "session_efficiency_pct": 0,
        "today_tokens_saved": 0,
        "today_route_calls": 0,
        "est_tokens_saved": 0,
        "alltime_efficiency_pct": 0,
        "lifetime_claude_tokens": 0,
        "today_efficiency_pct": 0,
        "by_date": [],
    }

    # Hook audit log
    if DELEGATION_AUDIT_LOG.exists():
        try:
            lines = [l.strip() for l in DELEGATION_AUDIT_LOG.read_text().strip().split('\n') if l.strip()]
            actions = {}
            model_picks = {}   # classifier suggestions (model= field)
            exec_backends = {} # actual execution (exec= field)
            latencies = []
            prefetched = 0
            for line in lines:
                parts = {}
                for token in line.split():
                    if '=' in token and not token.startswith('['):
                        k, v = token.split('=', 1)
                        parts[k] = v
                action = parts.get('action', 'unknown')
                actions[action] = actions.get(action, 0) + 1
                # Track model classifier picks
                model = parts.get('model')
                if model:
                    model_picks[model] = model_picks.get(model, 0) + 1
                # Track actual execution backend
                exec_be = parts.get('exec')
                if exec_be:
                    exec_backends[exec_be] = exec_backends.get(exec_be, 0) + 1
                if parts.get('prefetch') == 'OK':
                    prefetched += 1
                if 'latency' in parts:
                    try:
                        latencies.append(int(parts['latency'].rstrip('ms')))
                    except ValueError:
                        pass

            data["hook_fires"] = len(lines)
            data["prefetched"] = prefetched
            data["avg_latency_ms"] = sum(latencies) // max(len(latencies), 1) if latencies else 0
            data["by_action"] = actions
            data["by_model"] = model_picks
            data["by_exec"] = exec_backends
        except (OSError, ValueError):
            pass

    # Gemini route eval log — with session/daily/all-time breakdowns
    if DELEGATION_EVAL_LOG.exists():
        try:
            route_lines = [l.strip() for l in DELEGATION_EVAL_LOG.read_text().strip().split('\n') if l.strip()]
            cats = {}
            ok = 0
            total_saved = 0
            by_date = {}  # date_str -> {calls, success, tokens_saved}
            today_str = datetime.now().strftime('%Y-%m-%d')

            # Session boundary: find when the current burst started
            # Use budget state's since_last_gap.gap_started if available
            # Normalize to naive local time for comparison with eval log timestamps
            session_start = None
            if BUDGET_STATE.exists():
                try:
                    bs = json.loads(BUDGET_STATE.read_text())
                    gap_started = bs.get('since_last_gap', {}).get('gap_started')
                    if gap_started:
                        # Convert TZ-aware UTC to naive local time
                        from datetime import timezone
                        try:
                            dt = datetime.fromisoformat(gap_started)
                            if dt.tzinfo is not None:
                                dt = dt.astimezone().replace(tzinfo=None)
                            session_start = dt.strftime('%Y-%m-%dT%H:%M:%S')
                        except (ValueError, TypeError):
                            session_start = gap_started[:19]
                except (json.JSONDecodeError, OSError):
                    pass

            session_saved = 0
            session_calls = 0

            for line in route_lines:
                entry = json.loads(line)
                cat = entry.get('category', 'unknown')
                ts = entry.get('ts', '')
                saved = entry.get('est_tokens_saved', 0)
                success = entry.get('success', False)

                cats[cat] = cats.get(cat, 0) + 1
                if success:
                    ok += 1
                total_saved += saved

                # Daily aggregation
                date_key = ts[:10] if len(ts) >= 10 else 'unknown'
                if date_key not in by_date:
                    by_date[date_key] = {"calls": 0, "success": 0, "tokens_saved": 0}
                by_date[date_key]["calls"] += 1
                if success:
                    by_date[date_key]["success"] += 1
                by_date[date_key]["tokens_saved"] += saved

                # Session aggregation (entries after gap_started)
                if session_start and ts >= session_start:
                    session_saved += saved
                    session_calls += 1

            data["route_calls"] = len(route_lines)
            data["route_success"] = ok
            data["route_success_pct"] = round(ok * 100 / max(len(route_lines), 1))
            data["est_tokens_saved"] = total_saved
            data["by_category"] = cats

            # Session breakdown
            data["session_tokens_saved"] = session_saved
            data["session_route_calls"] = session_calls

            # Daily breakdown (sorted, last 7 days)
            sorted_dates = sorted(by_date.items(), reverse=True)[:7]
            data["by_date"] = [
                {"date": d, **stats} for d, stats in sorted_dates
            ]

            # Today's totals
            today_data = by_date.get(today_str, {"calls": 0, "success": 0, "tokens_saved": 0})
            data["today_tokens_saved"] = today_data["tokens_saved"]
            data["today_route_calls"] = today_data["calls"]

        except (OSError, json.JSONDecodeError, ValueError):
            pass

    # Compute delegation efficiency ratio
    # = tokens_saved / (claude_tokens + tokens_saved) * 100
    # Cross-reference with budget state for Claude's token usage
    if BUDGET_STATE.exists():
        try:
            bs = json.loads(BUDGET_STATE.read_text())
            gap = bs.get('since_last_gap', {})
            lifetime = bs.get('lifetime', {})

            session_claude = gap.get('tokens_used', 0)
            session_saved = data.get('session_tokens_saved', 0)
            session_total = session_claude + session_saved
            data["session_efficiency_pct"] = round(
                session_saved * 100 / session_total) if session_total > 0 else 0
            data["session_claude_tokens"] = session_claude

            lifetime_claude = lifetime.get('total_tokens', 0)
            alltime_saved = data.get('est_tokens_saved', 0)
            alltime_total = lifetime_claude + alltime_saved
            data["alltime_efficiency_pct"] = round(
                alltime_saved * 100 / alltime_total) if alltime_total > 0 else 0
            data["lifetime_claude_tokens"] = lifetime_claude

            # Today's efficiency: today_saved vs today's Claude usage
            # Use 5h window tokens as today's Claude proxy (most accurate)
            window_tokens = bs.get('five_hour_window', {}).get('tokens_used', 0)
            today_saved = data.get('today_tokens_saved', 0)
            today_total = window_tokens + today_saved
            data["today_efficiency_pct"] = round(
                today_saved * 100 / today_total) if today_total > 0 else 0

        except (json.JSONDecodeError, OSError):
            pass

    # Daily counter
    if DELEGATION_COUNTER.exists():
        try:
            counter = json.loads(DELEGATION_COUNTER.read_text())
            data["gemini_today"] = counter.get('count', 0)
            data["gemini_date"] = counter.get('date', '')
        except (json.JSONDecodeError, OSError):
            pass

    # Compliance
    if DELEGATION_COMPLIANCE.exists():
        try:
            comp = json.loads(DELEGATION_COMPLIANCE.read_text())
            data["delegation_rate"] = comp.get('delegation_rate', '0%')
            data["total_prompts"] = comp.get('total_prompts', 0)
        except (json.JSONDecodeError, OSError):
            pass

    # Quality gate — disabled/warned templates
    if DELEGATION_DISABLED.exists():
        try:
            disabled_data = json.loads(DELEGATION_DISABLED.read_text())
            data["disabled_templates"] = disabled_data.get('disabled', [])
            data["warned_templates"] = disabled_data.get('warned', [])
        except (json.JSONDecodeError, OSError):
            pass

    return data


def get_delegation_stats():
    return cached("delegation_stats", _load_delegation_stats, ttl=10)


# === AGGREGATE (for /api/data) ===

def _smart_model_recommendation(usage):
    """Pick model recommendation using the gap window as primary signal.

    The 5-hour rolling window is a client-side ESTIMATE that doesn't
    sync with Anthropic's actual rate-limit resets. The gap window
    (usage since last 30+ min break) is more reliable because it
    tracks the actual burst of activity the user cares about.

    If the user is actively using Claude (gap window has messages),
    use the gap window percentage. Only fall back to 5h if no gap data.
    """
    gap = usage.get("since_last_gap", {})
    gap_msgs = gap.get("messages", 0)
    gap_tokens = gap.get("tokens_used", 0)

    five_pct = usage.get("percentage", 0)

    # Estimate gap percentage against the same budget
    budget = usage.get("budget", 500_000)
    gap_pct = (gap_tokens / budget * 100) if budget > 0 else 0

    # Gap window is primary when user has active messages
    effective_pct = gap_pct if gap_msgs > 0 else five_pct

    if effective_pct >= 95:
        return "wind_down", "limit"
    elif effective_pct >= 85:
        return "sonnet", "critical"
    elif effective_pct >= 70:
        return "sonnet", "warning"
    elif effective_pct >= 50:
        return "opus", "info"
    return "opus", "ok"


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
    session = get_current_session_stats()
    delegation = get_delegation_stats()

    # Override model recommendation with smart logic
    smart_rec, smart_alert = _smart_model_recommendation(usage)
    usage["model_recommendation"] = smart_rec
    usage["alert_level"] = smart_alert

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
            "alert_level": smart_alert,
        },
        "current_session": session,
        "delegation": delegation,
    }
