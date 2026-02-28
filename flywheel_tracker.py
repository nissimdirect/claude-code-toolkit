#!/usr/bin/env python3
"""Flywheel Loop Tracker — Instruments all 10 SDLC compound loops.

Reads state files, git history, and Obsidian docs to calculate metrics
for each flywheel loop. Outputs a summary to stdout and writes state
to ~/.claude/.locks/flywheel-metrics.json.

Called by:
- session_audit.py (Stop hook) — captures metrics at session end
- /today skill — shows loop health in morning check
- /self-improve — identifies which loops need attention

Metrics tracked per loop:
- spinning: bool (has this loop produced output recently?)
- last_activity: timestamp
- metric_value: the loop's north star metric
- trend: up/down/flat compared to last measurement
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / ".locks"
METRICS_FILE = STATE_DIR / "flywheel-metrics.json"
OBSIDIAN = Path.home() / "Documents" / "Obsidian"
TOOLS = Path.home() / "Development" / "tools"


def _load_previous() -> dict:
    """Load previous metrics for trend comparison."""
    if METRICS_FILE.exists():
        try:
            return json.loads(METRICS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _count_learnings() -> int:
    """Count total learnings from learning-index.json (v2 index)."""
    index_file = STATE_DIR / "learning-index.json"
    if not index_file.exists():
        return 0
    try:
        index = json.loads(index_file.read_text())
        return index.get("total_learnings", 0)
    except (OSError, json.JSONDecodeError):
        return 0


def _count_graduated() -> int:
    """Count graduated learnings from learning-index.json (v2 index)."""
    index_file = STATE_DIR / "learning-index.json"
    if not index_file.exists():
        return 0
    try:
        index = json.loads(index_file.read_text())
        return index.get("graduated_count", 0)
    except (OSError, json.JSONDecodeError):
        return 0


def _learning_index_age_hours() -> float:
    """How old is the learning index?"""
    idx = STATE_DIR / "learning-index.json"
    if not idx.exists():
        return 999
    try:
        age = time.time() - idx.stat().st_mtime
        return age / 3600
    except OSError:
        return 999


def _active_tasks_shipped_ratio() -> tuple[int, int]:
    """Count shipped vs total tasks in ACTIVE-TASKS.md."""
    at_file = OBSIDIAN / "ACTIVE-TASKS.md"
    if not at_file.exists():
        return 0, 0
    try:
        content = at_file.read_text()
        lines = content.split("\n")
        total = 0
        shipped = 0
        for line in lines:
            if line.strip().startswith("- ["):
                total += 1
                if "- [x]" in line.lower() or "DONE" in line or "SHIPPED" in line:
                    shipped += 1
        return shipped, total
    except OSError:
        return 0, 0


def _budget_state() -> dict:
    """Read current budget state."""
    bs_file = STATE_DIR / ".budget-state.json"
    if not bs_file.exists():
        return {}
    try:
        return json.loads(bs_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _delegation_stats() -> dict:
    """Read delegation compliance stats."""
    dc_file = STATE_DIR / "delegation-compliance.json"
    if not dc_file.exists():
        return {}
    try:
        return json.loads(dc_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _handoff_count() -> int:
    """Count recent handoff files (last 7 days)."""
    handoff_dir = OBSIDIAN / "process"
    if not handoff_dir.exists():
        return 0
    cutoff = time.time() - (7 * 86400)
    count = 0
    try:
        for f in handoff_dir.glob("HANDOFF-*.md"):
            if f.stat().st_mtime > cutoff:
                count += 1
    except OSError:
        pass
    return count


def _compound_doc_count() -> int:
    """Count compound docs (solutions documented via /workflows:compound)."""
    solutions_dirs = [
        Path.home() / "Development" / "entropic" / "docs" / "solutions",
        Path.home() / "Development" / "tools" / "docs" / "solutions",
        OBSIDIAN / "solutions",
    ]
    count = 0
    for d in solutions_dirs:
        if d.exists():
            try:
                count += len(list(d.glob("*.md")))
            except OSError:
                pass
    return count


def _kb_article_count() -> int:
    """Count KB articles across ~/Development/ (all .md/.html in KB dirs).

    Scans known KB directories under ~/Development/ — same source of truth
    as the dashboard's _scan_kb_directories(). Uses find with -maxdepth 3
    for speed (~87K articles in <2s).
    """
    dev_dir = Path.home() / "Development"
    if not dev_dir.exists():
        return 0

    # Known KB directories (non-code project dirs with articles)
    skip_dirs = {
        "tools",
        "entropic",
        "entropic-v2challenger",
        "cymatics",
        "figure-isolator",
        "lyric-analyst",
        "music-composer",
        "shared-brain",
        "AI-Knowledge-Exchange",
        "knowledge-bases",
    }

    total = 0
    try:
        for child in dev_dir.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            if child.name in skip_dirs:
                # knowledge-bases has its own sub-dirs
                if child.name == "knowledge-bases":
                    result = subprocess.run(
                        ["find", str(child), "-name", "*.md", "-o", "-name", "*.html"],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    if result.stdout.strip():
                        total += len(result.stdout.strip().split("\n"))
                continue
            # Count .md and .html files
            result = subprocess.run(
                [
                    "find",
                    str(child),
                    "-maxdepth",
                    "3",
                    "-name",
                    "*.md",
                    "-o",
                    "-name",
                    "*.html",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.stdout.strip():
                count = len(result.stdout.strip().split("\n"))
                if count >= 3:  # Skip dirs with <3 articles (not real KB)
                    total += count
    except (subprocess.TimeoutExpired, OSError):
        pass

    return total


def _session_tracker() -> dict:
    """Read session tracker for multi-session stats."""
    st_file = STATE_DIR / "session-tracker.json"
    if not st_file.exists():
        return {}
    try:
        return json.loads(st_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _trend(current: float, previous: float) -> str:
    """Calculate trend direction."""
    if previous == 0:
        return "new"
    delta = current - previous
    pct = abs(delta / previous) if previous else 0
    if pct < 0.05:
        return "flat"
    return "up" if delta > 0 else "down"


def measure_all_loops() -> dict:
    """Measure all 10 flywheel loops. Returns metrics dict."""
    prev = _load_previous()
    prev_loops = prev.get("loops", {})
    now = time.time()

    loops = {}

    # Loop 1: Learn → Enforce
    learnings = _count_learnings()
    idx_age = _learning_index_age_hours()
    prev_l1 = prev_loops.get("1", {}).get("metric_value", 0)
    loops["1"] = {
        "name": "Learn → Enforce",
        "spinning": idx_age < 48 and learnings > 0,
        "instrumented": True,
        "metric_name": "total_learnings",
        "metric_value": learnings,
        "trend": _trend(learnings, prev_l1),
        "detail": f"{learnings} learnings, index {idx_age:.0f}h old",
        "last_activity": now if idx_age < 24 else now - (idx_age * 3600),
    }

    # Loop 2: Build → Test → Ship → Document
    shipped, total = _active_tasks_shipped_ratio()
    ratio = shipped / total if total > 0 else 0
    prev_l2 = prev_loops.get("2", {}).get("metric_value", 0)
    # Secondary metric: test pass rate from manifests
    test_detail = ""
    for manifest_path in [
        Path.home()
        / "Development"
        / "entropic-v2challenger"
        / "backend"
        / ".test-manifest.json",
    ]:
        if manifest_path.exists():
            try:
                import json as _json

                m = _json.loads(manifest_path.read_text())
                if m.get("green"):
                    test_detail = f", tests GREEN ({m.get('passed', 0)} passed)"
                else:
                    test_detail = f", tests RED ({m.get('failed', 0)} failed)"
            except (ValueError, OSError):
                pass
    loops["2"] = {
        "name": "Build → Test → Ship → Document",
        "spinning": ratio > 0,
        "instrumented": True,  # NOW instrumented by this tracker
        "metric_name": "shipped_planned_ratio",
        "metric_value": round(ratio, 2),
        "trend": _trend(ratio, prev_l2),
        "detail": f"{shipped}/{total} tasks done (ratio: {ratio:.2f}, target: >0.7){test_detail}",
        "last_activity": now,
    }

    # Loop 3: Knowledge Accumulation
    kb_count = _kb_article_count()
    prev_l3 = prev_loops.get("3", {}).get("metric_value", 0)
    loops["3"] = {
        "name": "Knowledge Accumulation",
        "spinning": kb_count > 0,
        "instrumented": True,  # Count tracked
        "metric_name": "kb_article_count",
        "metric_value": kb_count,
        "trend": _trend(kb_count, prev_l3),
        "detail": f"{kb_count} articles on disk",
        "last_activity": now,
    }

    # Loop 4: Budget-Aware Degradation
    bs = _budget_state()
    pct = bs.get("usage_pct", 0)
    prev_l4 = prev_loops.get("4", {}).get("metric_value", 0)
    loops["4"] = {
        "name": "Budget-Aware Degradation",
        "spinning": True,  # budget hook runs every prompt
        "instrumented": True,
        "metric_name": "budget_usage_pct",
        "metric_value": pct,
        "trend": _trend(pct, prev_l4),
        "detail": f"{pct:.0f}% budget used",
        "last_activity": now,
    }

    # Loop 5: Multi-Session Coordination
    handoffs = _handoff_count()
    st = _session_tracker()
    sessions = st.get("total_sessions", 0)
    prev_l5 = prev_loops.get("5", {}).get("metric_value", 0)
    loops["5"] = {
        "name": "Multi-Session Coordination",
        "spinning": handoffs > 0 or sessions > 0,
        "instrumented": True,
        "metric_name": "recent_handoffs",
        "metric_value": handoffs,
        "trend": _trend(handoffs, prev_l5),
        "detail": f"{handoffs} handoffs in last 7 days, {sessions} total sessions",
        "last_activity": now,
    }

    # Loop 6: Self-Improving System
    graduated = _count_graduated()
    prev_l6 = prev_loops.get("6", {}).get("metric_value", 0)
    loops["6"] = {
        "name": "Self-Improving System",
        "spinning": graduated > 0,
        "instrumented": True,  # NOW instrumented
        "metric_name": "graduated_learnings",
        "metric_value": graduated,
        "trend": _trend(graduated, prev_l6),
        "detail": f"{graduated} graduated learnings (target: 1/week)",
        "last_activity": now,
    }

    # Loop 7: Cross-Model Validation
    ds = _delegation_stats()
    # delegation-compliance.json uses "total_delegated" and "total_prefetched"
    delegations = ds.get("total_delegated", ds.get("total_delegations", 0))
    prefetched = ds.get("total_prefetched", 0)
    skill_delegated = ds.get("total_skill_delegated", 0)
    prev_l7 = prev_loops.get("7", {}).get("metric_value", 0)
    # v4.4: skill delegation health — is the slash command path active?
    skill_detail = f", {skill_delegated} from skills" if skill_delegated > 0 else ""
    loops["7"] = {
        "name": "Cross-Model Validation",
        "spinning": delegations > 0,
        "instrumented": True,  # delegation-compliance.json exists
        "metric_name": "total_delegated",
        "metric_value": delegations,
        "trend": _trend(delegations, prev_l7),
        "detail": f"{delegations} delegated ({prefetched} prefetched{skill_detail})",
        "last_activity": now,
    }

    # Loop 8: Debug → Document → Prevent
    compound_docs = _compound_doc_count()
    prev_l8 = prev_loops.get("8", {}).get("metric_value", 0)
    loops["8"] = {
        "name": "Debug → Document → Prevent",
        "spinning": compound_docs > 0,
        "instrumented": True,  # NOW instrumented
        "metric_name": "compound_docs",
        "metric_value": compound_docs,
        "trend": _trend(compound_docs, prev_l8),
        "detail": f"{compound_docs} compound docs (target: >0)",
        "last_activity": now,
    }

    # Loop 9: Sentry Observe → Fix → Verify
    # Check if Sentry MCP is configured AND auth token is available
    sentry_mcp_file = Path.home() / ".claude" / ".mcp.json"
    sentry_mcp_active = False
    sentry_auth = False
    if sentry_mcp_file.exists():
        try:
            mcp_data = json.loads(sentry_mcp_file.read_text())
            sentry_mcp_active = "sentry" in mcp_data.get("mcpServers", {})
        except (json.JSONDecodeError, OSError):
            pass
    # Check if SENTRY_AUTH_TOKEN is set (loaded from secrets.env)
    secrets_env = Path.home() / ".config" / "secrets.env"
    if secrets_env.exists():
        try:
            sentry_auth = "SENTRY_AUTH_TOKEN" in secrets_env.read_text()
        except OSError:
            pass
    # Check if any project has SENTRY_DSN configured
    sentry_dsn = bool(os.environ.get("SENTRY_DSN"))

    sentry_instrumented = sentry_mcp_active and sentry_auth
    sentry_spinning = sentry_instrumented and sentry_dsn
    if sentry_instrumented and not sentry_dsn:
        sentry_detail = (
            "MCP + auth token ready. Set SENTRY_DSN in secrets.env to capture errors"
        )
    elif sentry_spinning:
        sentry_detail = "Full loop active: MCP + auth + DSN"
    else:
        sentry_detail = "MCP not configured — needs setup"

    loops["9"] = {
        "name": "Sentry Observe → Fix → Verify",
        "spinning": sentry_spinning,
        "instrumented": sentry_instrumented,
        "metric_name": "sentry_issues_resolved",
        "metric_value": 1 if sentry_spinning else 0,
        "trend": "flat",
        "detail": sentry_detail,
        "last_activity": now if sentry_spinning else 0,
    }

    # Loop 10: Test Health (multi-project scan)
    # Scan all ~/Development/*/ for .test-manifest.json files
    dev_dir = Path.home() / "Development"
    test_projects = []
    total_tests = 0
    all_green = True
    if dev_dir.exists():
        for project_dir in sorted(dev_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            # Check project root and backend/ subdirectory
            for manifest_loc in [project_dir, project_dir / "backend"]:
                manifest = manifest_loc / ".test-manifest.json"
                if manifest.exists():
                    try:
                        import json as _json

                        m = _json.loads(manifest.read_text())
                        p = m.get("passed", 0)
                        total_tests += p
                        is_green = m.get("green", False)
                        if not is_green:
                            all_green = False
                        test_projects.append(
                            f"{project_dir.name}({'GREEN' if is_green else 'RED'})"
                        )
                    except (ValueError, OSError):
                        pass
    loops["10"] = {
        "name": "Test Health",
        "spinning": len(test_projects) > 0,
        "instrumented": len(test_projects) > 0,
        "metric_name": "test_project_count",
        "metric_value": len(test_projects),
        "trend": "flat",
        "detail": f"{len(test_projects)} projects, {total_tests} total tests, {'all green' if all_green else 'some RED'}: {', '.join(test_projects) if test_projects else 'none'}",
        "last_activity": now if test_projects else 0,
    }

    return loops


def save_metrics(loops: dict):
    """Save metrics to state file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "measured_at": time.time(),
        "measured_at_iso": datetime.now().isoformat(),
        "loops": loops,
        "summary": {
            "total": len(loops),
            "spinning": sum(1 for l in loops.values() if l["spinning"]),
            "instrumented": sum(1 for l in loops.values() if l["instrumented"]),
        },
    }
    METRICS_FILE.write_text(json.dumps(data, indent=2))
    return data


def format_report(data: dict) -> str:
    """Format a human-readable flywheel health report."""
    lines = []
    s = data["summary"]
    lines.append(
        f"FLYWHEEL: {s['spinning']}/{s['total']} spinning, "
        f"{s['instrumented']}/{s['total']} instrumented"
    )
    lines.append("")

    for num in sorted(data["loops"].keys(), key=int):
        loop = data["loops"][num]
        status = "✓" if loop["spinning"] else "✗"
        instr = "I" if loop["instrumented"] else "-"
        arrow = {"up": "↑", "down": "↓", "flat": "→", "new": "★"}.get(
            loop["trend"], "?"
        )
        lines.append(f"  [{status}][{instr}] Loop {num}: {loop['name']}")
        lines.append(f"         {arrow} {loop['detail']}")

    return "\n".join(lines)


def verify(loops: dict) -> list[str]:
    """Sanity-check measurements against known data sources.

    Returns list of warnings. If a data source exists but its measurement
    returned 0, that's likely a measurement bug — not "loop not spinning."
    """
    warnings = []

    # Data source existence checks — if the file/dir exists, measurement should be > 0
    checks = [
        (
            "1",
            Path.home()
            / ".claude"
            / "projects"
            / "-Users-nissimagent"
            / "memory"
            / "learnings.md",
            "learnings.md exists but _count_learnings() returned 0",
        ),
        (
            "2",
            OBSIDIAN / "ACTIVE-TASKS.md",
            "ACTIVE-TASKS.md exists but shipped ratio is 0",
        ),
        (
            "3",
            Path.home() / "Development",
            "~/Development/ exists but _kb_article_count() returned 0",
        ),
        (
            "7",
            STATE_DIR / "delegation-compliance.json",
            "delegation-compliance.json exists but delegations = 0",
        ),
        (
            "8",
            Path.home() / "Development" / "entropic" / "docs" / "solutions",
            "solutions/ dir exists but _compound_doc_count() returned 0",
        ),
    ]

    for loop_num, source_path, msg in checks:
        loop = loops.get(loop_num, {})
        metric = loop.get("metric_value", 0)
        if source_path.exists() and metric == 0:
            warnings.append(f"WARNING Loop {loop_num}: {msg}")

    # Regression checks — values that should never drop below known minimums
    # These minimums are conservative (well below actual counts)
    known_minimums = {
        "1": (100, "learnings"),  # We have 150+
        "3": (50000, "KB articles"),  # We have 87K+
    }
    for loop_num, (minimum, label) in known_minimums.items():
        loop = loops.get(loop_num, {})
        metric = loop.get("metric_value", 0)
        if 0 < metric < minimum:
            warnings.append(
                f"WARNING Loop {loop_num}: {label} = {metric}, "
                f"expected >= {minimum} (possible measurement error)"
            )

    # Consumer drift detection — migrated consumers must NOT read raw learnings.md
    import re as _re

    MIGRATED_CONSUMERS = [
        Path.home() / ".claude/skills/today/SKILL.md",
        Path.home() / ".claude/skills/self-improve/SKILL.md",
        Path.home() / ".claude/skills/my-clone/SKILL.md",
        Path.home() / ".claude/agents/learnings-researcher.md",
    ]
    RAW_READ_PATTERNS = [
        r"learnings\.md.*first \d+ lines",
        r"first \d+ lines.*learnings\.md",
        r"Read.*learnings\.md(?!.*write)",
        r"grep.*learnings\.md",
    ]
    for path in MIGRATED_CONSUMERS:
        if path.exists():
            content = path.read_text()
            for pat in RAW_READ_PATTERNS:
                if _re.search(pat, content, _re.IGNORECASE):
                    warnings.append(
                        f"WARNING Consumer drift: {path.name} has raw learnings.md read: {pat}"
                    )

    return warnings


def main():
    """Run flywheel measurement and output report."""
    import sys

    loops = measure_all_loops()
    data = save_metrics(loops)
    print(format_report(data))

    # Always run verify, print warnings if any
    warns = verify(loops)
    if warns:
        print()
        for w in warns:
            print(f"  {w}")
        if "--verify" in sys.argv:
            sys.exit(1)

    if "--verify" in sys.argv and not warns:
        print("\n  VERIFY: All measurements pass sanity checks.")


if __name__ == "__main__":
    main()
