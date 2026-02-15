#!/usr/bin/env python3
"""Workflow Calendar System — schedule_checker.py

Tracks when each workflow last ran, what's due today, and detects quarter transitions.
Follows the dual-storage pattern: JSON state file + human-readable Obsidian markdown.

Usage:
    python3 ~/Development/tools/schedule_checker.py check    # JSON: due/overdue workflows
    python3 ~/Development/tools/schedule_checker.py mark <id> # Record workflow ran today
    python3 ~/Development/tools/schedule_checker.py status   # Human-readable overview
    python3 ~/Development/tools/schedule_checker.py link <workflow-id> <roadmap-id>
    python3 ~/Development/tools/schedule_checker.py init     # Initialize from CATALOG.md

State: ~/.claude/.locks/calendar-state.json
Sync:  ~/Documents/Obsidian/process/WORKFLOW-CALENDAR.md
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

STATE_FILE = Path.home() / '.claude' / '.locks' / 'calendar-state.json'
CATALOG_FILE = Path.home() / '.claude' / 'skills' / 'workflow' / 'CATALOG.md'
CALENDAR_MD = Path.home() / 'Documents' / 'Obsidian' / 'process' / 'WORKFLOW-CALENDAR.md'
BUDGET_STATE = Path.home() / '.claude' / '.locks' / '.budget-state.json'

# All 27 workflows with their frequencies and budget tiers (from red team analysis)
WORKFLOW_DEFINITIONS = {
    'plugin-validate':        {'freq': 'per-project',   'tier': 'medium', 'name': 'Plugin Concept Validation'},
    'roadmap-refresh':        {'freq': 'weekly-monday',  'tier': 'medium', 'name': 'Weekly Roadmap Refresh'},
    'single-release':         {'freq': 'per-release',    'tier': 'medium', 'name': 'Single Release Strategy'},
    'wave-scraper':           {'freq': 'on-demand',      'tier': 'extreme', 'name': 'Wave Scraper Campaign'},
    'launch-checklist':       {'freq': 'per-release',    'tier': 'heavy', 'name': 'Launch Checklist Execution'},
    'strategic-review':       {'freq': 'quarterly',      'tier': 'heavy', 'name': 'Quarterly Strategic Review'},
    'content-multiply':       {'freq': 'per-release',    'tier': 'extreme', 'name': 'Content Multiplication Chain'},
    'dsp-feasibility':        {'freq': 'per-project',    'tier': 'medium', 'name': 'DSP Algorithm Feasibility'},
    'morning-kb-health':      {'freq': 'daily',          'tier': 'light', 'name': 'Morning KB Health Check'},
    'plugin-demo':            {'freq': 'per-release',    'tier': 'heavy', 'name': 'Plugin Demo Creation'},
    'album-concept':          {'freq': 'per-project',    'tier': 'medium', 'name': 'Album Concept Development'},
    'competitor-parity':      {'freq': 'monthly',        'tier': 'medium', 'name': 'Competitor Feature Parity'},
    'entropic-rd':            {'freq': 'bi-weekly',      'tier': 'medium', 'name': 'Entropic Effect R&D'},
    'token-efficiency':       {'freq': 'weekly',         'tier': 'heavy', 'name': 'Token Efficiency Audit'},
    'correspondence-growth':  {'freq': 'weekly',         'tier': 'light', 'name': 'Correspondence List Growth'},
    'source-heartbeat':       {'freq': 'weekly-monday',  'tier': 'light', 'name': 'Source Heartbeat Monitor'},
    'plugin-arch':            {'freq': 'per-project',    'tier': 'medium', 'name': 'Plugin Architecture Review'},
    'param-design':           {'freq': 'per-project',    'tier': 'medium', 'name': 'Parameter Design Session'},
    'music-video':            {'freq': 'per-release',    'tier': 'medium', 'name': 'Music Video Production'},
    'sprint-review':          {'freq': 'weekly-friday',  'tier': 'medium', 'name': 'Weekly Plugin Sprint Review'},
    'market-landscape':       {'freq': 'monthly',        'tier': 'medium', 'name': 'Market Landscape Mapping'},
    'skill-digest':           {'freq': 'weekly',         'tier': 'medium', 'name': 'Skill Learning Digest'},
    'blog-outreach':          {'freq': 'monthly',        'tier': 'medium', 'name': 'Music Blog Outreach'},
    'chaos-viz-mode':         {'freq': 'quarterly',      'tier': 'extreme', 'name': 'Chaos Viz Mode Addition'},
    'skill-onboard':          {'freq': 'on-demand',      'tier': 'medium', 'name': 'Skill Onboarding Workflow'},
    'feature-differentiation':{'freq': 'on-demand',      'tier': 'medium', 'name': 'Feature Differentiation'},
    'portfolio-pipeline':     {'freq': 'per-project',    'tier': 'extreme', 'name': 'Portfolio Pipeline'},
}

# Roadmap associations (workflow → roadmap item IDs)
DEFAULT_ROADMAP_LINKS = {
    'plugin-validate': [6],
    'portfolio-pipeline': [52],
    'single-release': [15, 16],
}


def get_quarter(d: date) -> str:
    """Return quarter string like '2026-Q1'."""
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def parse_date(s: str | None) -> date | None:
    """Parse ISO date string to date object."""
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def is_due(freq: str, last_run: date | None, today: date) -> bool:
    """Check if a workflow is due based on its frequency and last run date."""
    if last_run is None:
        # Never run — due for any scheduled frequency
        return freq in ('daily', 'weekly', 'weekly-monday', 'weekly-friday',
                        'bi-weekly', 'monthly', 'quarterly')

    days_since = (today - last_run).days

    if freq == 'daily':
        return days_since >= 1
    elif freq == 'weekly-monday':
        return today.weekday() == 0 and days_since >= 6
    elif freq == 'weekly-friday':
        return today.weekday() == 4 and days_since >= 6
    elif freq == 'weekly':
        return days_since >= 7
    elif freq == 'bi-weekly':
        return days_since >= 14
    elif freq == 'monthly':
        return days_since >= 28
    elif freq == 'quarterly':
        return get_quarter(today) != get_quarter(last_run)
    # per-project, per-release, on-demand: never auto-due
    return False


def is_overdue(freq: str, last_run: date | None, today: date) -> bool:
    """Check if a workflow is past its expected run window."""
    if last_run is None:
        return False

    days_since = (today - last_run).days

    if freq == 'daily':
        return days_since >= 2
    elif freq in ('weekly', 'weekly-monday', 'weekly-friday'):
        return days_since >= 10
    elif freq == 'bi-weekly':
        return days_since >= 21
    elif freq == 'monthly':
        return days_since >= 42
    elif freq == 'quarterly':
        # Overdue if more than 2 weeks into new quarter without running
        if get_quarter(today) != get_quarter(last_run):
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            quarter_start = today.replace(month=quarter_start_month, day=1)
            return (today - quarter_start).days >= 14
    return False


def next_due_date(freq: str, last_run: date | None, today: date) -> str | None:
    """Calculate next due date for a workflow."""
    if freq in ('per-project', 'per-release', 'on-demand'):
        return None

    if last_run is None:
        return today.isoformat()

    if freq == 'daily':
        return (last_run + timedelta(days=1)).isoformat()
    elif freq == 'weekly-monday':
        days_until_monday = (7 - last_run.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        return (last_run + timedelta(days=days_until_monday)).isoformat()
    elif freq == 'weekly-friday':
        days_until_friday = (4 - last_run.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        return (last_run + timedelta(days=days_until_friday)).isoformat()
    elif freq == 'weekly':
        return (last_run + timedelta(days=7)).isoformat()
    elif freq == 'bi-weekly':
        return (last_run + timedelta(days=14)).isoformat()
    elif freq == 'monthly':
        return (last_run + timedelta(days=28)).isoformat()
    elif freq == 'quarterly':
        q = (last_run.month - 1) // 3 + 1
        next_q_month = q * 3 + 1
        next_q_year = last_run.year
        if next_q_month > 12:
            next_q_month = 1
            next_q_year += 1
        return date(next_q_year, next_q_month, 1).isoformat()

    return None


def get_budget_percentage() -> float:
    """Read current budget percentage from budget state file."""
    if not BUDGET_STATE.exists():
        return 0.0
    try:
        data = json.loads(BUDGET_STATE.read_text())
        return float(data.get('five_hour_window', {}).get('percentage', 0.0))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return 0.0


def load_state() -> dict:
    """Load calendar state from JSON file."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    """Save calendar state to JSON file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state['last_updated'] = datetime.now().isoformat(timespec='seconds')
    STATE_FILE.write_text(json.dumps(state, indent=2) + '\n')


def cmd_init(force: bool = False) -> None:
    """Initialize calendar-state.json from CATALOG.md definitions."""
    existing = load_state()
    if existing and existing.get('workflows') and not force:
        wf_count = len(existing.get('workflows', {}))
        marked = sum(1 for w in existing.get('workflows', {}).values() if w.get('last_run'))
        print(f"Error: calendar-state.json already exists ({wf_count} workflows, {marked} with run history).")
        print("Use 'init --force' to reinitialize (this erases all run history).")
        sys.exit(1)
    today_d = date.today()
    state = {
        'last_updated': datetime.now().isoformat(timespec='seconds'),
        'current_quarter': get_quarter(today_d),
        'workflows': {},
        'roadmap_links': DEFAULT_ROADMAP_LINKS,
    }

    for wf_id, defn in WORKFLOW_DEFINITIONS.items():
        nd = next_due_date(defn['freq'], None, today_d)
        state['workflows'][wf_id] = {
            'last_run': None,
            'frequency': defn['freq'],
            'budget_tier': defn['tier'],
            'next_due': nd,
        }

    save_state(state)
    print(f"Initialized calendar-state.json with {len(WORKFLOW_DEFINITIONS)} workflows.")
    print(f"Current quarter: {get_quarter(today_d)}")
    print(f"State file: {STATE_FILE}")


def cmd_check() -> None:
    """Output JSON with due/overdue workflows and quarter change detection."""
    state = load_state()
    if not state:
        print(json.dumps({'error': 'No calendar state. Run: schedule_checker.py init'}))
        sys.exit(1)

    today_d = date.today()
    budget_pct = get_budget_percentage()
    quarter_changed = get_quarter(today_d) != state.get('current_quarter', get_quarter(today_d))

    due = []
    overdue = []
    budget_filtered = []

    for wf_id, defn in WORKFLOW_DEFINITIONS.items():
        wf_state = state.get('workflows', {}).get(wf_id, {})
        freq = wf_state.get('frequency', defn['freq'])
        tier = wf_state.get('budget_tier', defn['tier'])
        last_run = parse_date(wf_state.get('last_run'))

        wf_due = is_due(freq, last_run, today_d)
        wf_overdue = is_overdue(freq, last_run, today_d)

        if not wf_due and not wf_overdue:
            continue

        entry = {
            'id': wf_id,
            'name': defn['name'],
            'frequency': freq,
            'budget_tier': tier,
            'last_run': last_run.isoformat() if last_run else None,
            'days_since': (today_d - last_run).days if last_run else None,
        }

        # Budget filtering
        if budget_pct > 70 and tier not in ('light',):
            budget_filtered.append(entry)
            continue
        elif budget_pct > 50 and tier in ('heavy', 'extreme'):
            budget_filtered.append(entry)
            continue

        if wf_overdue:
            overdue.append(entry)
        elif wf_due:
            due.append(entry)

    # Quarter transition special handling
    quarter_info = None
    if quarter_changed:
        old_q = state.get('current_quarter', '?')
        new_q = get_quarter(today_d)
        quarter_info = {
            'old_quarter': old_q,
            'new_quarter': new_q,
            'message': f"{old_q} -> {new_q}. Strategic review + quarterly goal setting are due.",
        }
        # Ensure strategic-review shows as urgent
        sr_in_due = any(w['id'] == 'strategic-review' for w in due + overdue)
        if not sr_in_due:
            sr_entry = {
                'id': 'strategic-review',
                'name': 'Quarterly Strategic Review',
                'frequency': 'quarterly',
                'budget_tier': 'heavy',
                'last_run': None,
                'days_since': None,
                'urgent': True,
            }
            due.insert(0, sr_entry)

    result = {
        'date': today_d.isoformat(),
        'quarter': get_quarter(today_d),
        'budget_pct': round(budget_pct, 1),
        'due': due,
        'overdue': overdue,
        'quarter_change': quarter_changed,
        'quarter_info': quarter_info,
        'budget_filtered': budget_filtered,
    }

    print(json.dumps(result, indent=2))


def cmd_mark(workflow_id: str) -> None:
    """Mark a workflow as having run today."""
    state = load_state()
    if not state:
        print(f"Error: No calendar state. Run: schedule_checker.py init")
        sys.exit(1)

    if workflow_id not in WORKFLOW_DEFINITIONS:
        print(f"Error: Unknown workflow '{workflow_id}'")
        print(f"Valid IDs: {', '.join(sorted(WORKFLOW_DEFINITIONS.keys()))}")
        sys.exit(1)

    today_d = date.today()
    workflows = state.setdefault('workflows', {})
    defn = WORKFLOW_DEFINITIONS[workflow_id]

    wf = workflows.setdefault(workflow_id, {
        'frequency': defn['freq'],
        'budget_tier': defn['tier'],
    })
    wf['last_run'] = today_d.isoformat()
    wf['next_due'] = next_due_date(defn['freq'], today_d, today_d)

    # Update current quarter if needed
    state['current_quarter'] = get_quarter(today_d)

    save_state(state)
    print(f"Marked '{workflow_id}' as run on {today_d.isoformat()}")
    if wf['next_due']:
        print(f"Next due: {wf['next_due']}")


def cmd_link(workflow_id: str, roadmap_id: str) -> None:
    """Associate a workflow with a roadmap item."""
    state = load_state()
    if not state:
        print(f"Error: No calendar state. Run: schedule_checker.py init")
        sys.exit(1)

    if workflow_id not in WORKFLOW_DEFINITIONS:
        print(f"Error: Unknown workflow '{workflow_id}'")
        print(f"Valid IDs: {', '.join(sorted(WORKFLOW_DEFINITIONS.keys()))}")
        sys.exit(1)

    try:
        rid = int(roadmap_id)
    except ValueError:
        print(f"Error: roadmap_id must be an integer, got '{roadmap_id}'")
        sys.exit(1)

    links = state.setdefault('roadmap_links', {})
    wf_links = links.setdefault(workflow_id, [])
    if rid not in wf_links:
        wf_links.append(rid)

    save_state(state)
    print(f"Linked workflow '{workflow_id}' to roadmap item #{rid}")


def cmd_status() -> None:
    """Human-readable overview of all workflow schedules. Also writes WORKFLOW-CALENDAR.md."""
    state = load_state()
    if not state:
        print("No calendar state. Run: schedule_checker.py init")
        sys.exit(1)

    today_d = date.today()
    quarter = get_quarter(today_d)
    lines = []

    lines.append(f"# Workflow Calendar — {today_d.isoformat()}")
    lines.append(f"**Quarter:** {quarter}")
    lines.append(f"**Last updated:** {state.get('last_updated', 'unknown')}")
    lines.append("")

    # Group by status
    due_items = []
    overdue_items = []
    upcoming_items = []
    on_demand_items = []

    for wf_id, defn in WORKFLOW_DEFINITIONS.items():
        wf_state = state.get('workflows', {}).get(wf_id, {})
        freq = wf_state.get('frequency', defn['freq'])
        tier = wf_state.get('budget_tier', defn['tier'])
        last_run = parse_date(wf_state.get('last_run'))
        nd = wf_state.get('next_due')

        entry = {
            'id': wf_id,
            'name': defn['name'],
            'freq': freq,
            'tier': tier,
            'last_run': last_run.isoformat() if last_run else 'never',
            'next_due': nd or 'n/a',
        }

        if freq in ('per-project', 'per-release', 'on-demand'):
            on_demand_items.append(entry)
        elif is_overdue(freq, last_run, today_d):
            overdue_items.append(entry)
        elif is_due(freq, last_run, today_d):
            due_items.append(entry)
        else:
            upcoming_items.append(entry)

    if overdue_items:
        lines.append("## OVERDUE")
        lines.append("| Workflow | Frequency | Last Run | Budget Tier |")
        lines.append("|----------|-----------|----------|-------------|")
        for item in overdue_items:
            lines.append(f"| **{item['name']}** (`{item['id']}`) | {item['freq']} | {item['last_run']} | {item['tier']} |")
        lines.append("")

    if due_items:
        lines.append("## Due Today")
        lines.append("| Workflow | Frequency | Last Run | Budget Tier |")
        lines.append("|----------|-----------|----------|-------------|")
        for item in due_items:
            lines.append(f"| {item['name']} (`{item['id']}`) | {item['freq']} | {item['last_run']} | {item['tier']} |")
        lines.append("")

    if upcoming_items:
        lines.append("## Upcoming")
        lines.append("| Workflow | Frequency | Next Due | Budget Tier |")
        lines.append("|----------|-----------|----------|-------------|")
        for item in upcoming_items:
            lines.append(f"| {item['name']} (`{item['id']}`) | {item['freq']} | {item['next_due']} | {item['tier']} |")
        lines.append("")

    if on_demand_items:
        lines.append("## On-Demand / Per-Project")
        lines.append("| Workflow | Trigger | Last Run | Budget Tier |")
        lines.append("|----------|---------|----------|-------------|")
        for item in on_demand_items:
            lines.append(f"| {item['name']} (`{item['id']}`) | {item['freq']} | {item['last_run']} | {item['tier']} |")
        lines.append("")

    # Roadmap links
    links = state.get('roadmap_links', {})
    if links:
        lines.append("## Roadmap Associations")
        for wf_id, rids in sorted(links.items()):
            name = WORKFLOW_DEFINITIONS.get(wf_id, {}).get('name', wf_id)
            lines.append(f"- **{name}** → Roadmap #{', #'.join(str(r) for r in rids)}")
        lines.append("")

    # Quarter progress
    q_num = (today_d.month - 1) // 3
    q_start = date(today_d.year, q_num * 3 + 1, 1)
    next_q_month = (q_num + 1) * 3 + 1
    next_q_year = today_d.year
    if next_q_month > 12:
        next_q_month = 1
        next_q_year += 1
    q_end = date(next_q_year, next_q_month, 1) - timedelta(days=1)
    q_total = (q_end - q_start).days + 1
    q_elapsed = (today_d - q_start).days + 1
    q_pct = round(q_elapsed / q_total * 100)
    lines.append(f"## Quarter Progress")
    lines.append(f"**{quarter}:** Day {q_elapsed}/{q_total} ({q_pct}%)")
    lines.append("")

    output = '\n'.join(lines)
    print(output)

    # Write to Obsidian
    try:
        CALENDAR_MD.parent.mkdir(parents=True, exist_ok=True)
        CALENDAR_MD.write_text(output + '\n')
    except OSError as e:
        print(f"\nWarning: Could not write {CALENDAR_MD}: {e}", file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print("Usage: schedule_checker.py <command> [args]")
        print("Commands: init, check, mark <id>, status, link <wf-id> <roadmap-id>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'init':
        cmd_init(force='--force' in sys.argv)
    elif cmd == 'check':
        cmd_check()
    elif cmd == 'mark':
        if len(sys.argv) < 3:
            print("Usage: schedule_checker.py mark <workflow-id>")
            sys.exit(1)
        cmd_mark(sys.argv[2])
    elif cmd == 'status':
        cmd_status()
    elif cmd == 'link':
        if len(sys.argv) < 4:
            print("Usage: schedule_checker.py link <workflow-id> <roadmap-id>")
            sys.exit(1)
        cmd_link(sys.argv[2], sys.argv[3])
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: init, check, mark <id>, status, link <wf-id> <roadmap-id>")
        sys.exit(1)


if __name__ == '__main__':
    main()
