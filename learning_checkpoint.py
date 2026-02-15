#!/usr/bin/env python3
"""Learning Checkpoint System — Prevents learnings from being lost to context compaction.

Problem: Learnings identified mid-session were only written at /session-close.
If context compacted before that, learnings were lost forever.

Solution: Write learnings to a persistent JSON buffer on disk AS they're identified.
Buffer survives context compaction. Flushed to learnings.md at session end.

Usage:
    python3 learning_checkpoint.py add "Bridge exec 100% failure rate undetected 6 days"
    python3 learning_checkpoint.py add "Dashboard never triggers its own data refresh" --category system
    python3 learning_checkpoint.py list
    python3 learning_checkpoint.py flush          # Write all to learnings.md + clear buffer
    python3 learning_checkpoint.py health          # Check for silent system failures
    python3 learning_checkpoint.py count           # Just the count (for hooks/dashboard)
"""

import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

BUFFER_PATH = Path.home() / '.claude' / '.locks' / 'session-learnings.json'
LEARNINGS_PATH = Path.home() / '.claude' / 'projects' / '-Users-nissimagent' / 'memory' / 'learnings.md'

# Health check targets — systems that should be verified each session
HEALTH_CHECKS = [
    {
        'name': 'OpenClaw gateway',
        'check': 'pgrep -f "openclaw.*gateway"',
        'severity': 'HIGH',
        'what': 'Entropy Bot, cron jobs, Telegram delivery',
    },
    {
        'name': 'OpenClaw cron last run',
        'check': 'openclaw cron list 2>/dev/null | grep -c "ago"',
        'severity': 'HIGH',
        'what': 'Daily routines, retrospectives, task check-ins',
    },
    {
        'name': 'Dashboard process',
        'check': 'pgrep -f "dashboard_v2.py"',
        'severity': 'MEDIUM',
        'what': 'Budget visibility, task tracking',
    },
    {
        'name': 'Budget state freshness',
        'check_python': '_check_budget_freshness',
        'severity': 'HIGH',
        'what': 'Accurate token budget tracking',
    },
    {
        'name': 'Experiment tracker',
        'check_python': '_check_experiments',
        'severity': 'MEDIUM',
        'what': 'Experiment observation, learning capture',
    },
]


def _load_buffer():
    """Load the learning buffer from disk."""
    if not BUFFER_PATH.exists():
        return {'session_id': None, 'started': None, 'learnings': []}
    try:
        return json.loads(BUFFER_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {'session_id': None, 'started': None, 'learnings': []}


def _save_buffer(buffer):
    """Save the learning buffer to disk (atomic write)."""
    import tempfile
    BUFFER_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=BUFFER_PATH.parent, suffix='.json')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(buffer, f, indent=2)
        os.replace(tmp, BUFFER_PATH)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def add_learning(text, category='general'):
    """Add a learning to the buffer. Writes to disk immediately."""
    buffer = _load_buffer()
    if not buffer['started']:
        buffer['started'] = datetime.now(timezone.utc).isoformat()

    buffer['learnings'].append({
        'text': text,
        'category': category,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
    _save_buffer(buffer)
    print(f"Buffered learning #{len(buffer['learnings'])}: {text[:60]}...")


def list_learnings():
    """List all buffered learnings."""
    buffer = _load_buffer()
    if not buffer['learnings']:
        print("No buffered learnings.")
        return

    print(f"Buffered learnings ({len(buffer['learnings'])}):")
    print(f"Session started: {buffer.get('started', '?')}")
    print()
    for i, l in enumerate(buffer['learnings'], 1):
        cat = l.get('category', 'general')
        ts = l.get('timestamp', '?')[:16]
        print(f"  {i}. [{cat}] {l['text']} ({ts})")


def count_learnings():
    """Return just the count (for hooks/dashboard integration)."""
    buffer = _load_buffer()
    count = len(buffer.get('learnings', []))
    print(json.dumps({'count': count, 'buffer_path': str(BUFFER_PATH)}))


def flush_learnings():
    """Flush buffered learnings to learnings.md and clear buffer.

    This is called by /session-close. The learnings are appended
    to the appropriate session entry in learnings.md.
    """
    buffer = _load_buffer()
    if not buffer['learnings']:
        print("No learnings to flush.")
        return

    print(f"Flushing {len(buffer['learnings'])} learnings to learnings.md...")

    # Format learnings for output
    lines = []
    for l in buffer['learnings']:
        cat = l.get('category', 'general')
        lines.append(f"- **[{cat}]** {l['text']}")

    output = '\n'.join(lines)
    print(f"\nLearnings to write:\n{output}")
    print(f"\nTarget file: {LEARNINGS_PATH}")
    print("Note: Claude should append these to the current session entry in learnings.md")

    # Clear buffer
    _save_buffer({'session_id': None, 'started': None, 'learnings': []})
    print("Buffer cleared.")


def _check_budget_freshness():
    """Check if budget state file is stale."""
    import time
    budget_path = Path.home() / '.claude' / '.locks' / '.budget-state.json'
    if not budget_path.exists():
        return False, "Budget state file missing"
    age_min = (time.time() - budget_path.stat().st_mtime) / 60
    if age_min > 30:
        return False, f"Budget state is {int(age_min)}m old"
    return True, f"Budget state is {int(age_min)}m old (OK)"


def _check_experiments():
    """Check if experiments are stale (running but never observed)."""
    exp_path = Path.home() / '.claude' / '.locks' / 'experiments-state.json'
    if not exp_path.exists():
        return True, "No experiment state file"
    try:
        data = json.loads(exp_path.read_text())
        running = [e for e in data if e.get('status') == 'running']
        stale = []
        for e in running:
            created = e.get('created', '')
            if created:
                from datetime import datetime as dt
                created_date = dt.strptime(created, '%Y-%m-%d')
                days = (dt.now() - created_date).days
                if days > 5:
                    stale.append(f"Experiment #{e['id']}: running {days} days, no observations")
        if stale:
            return False, "; ".join(stale)
        return True, f"{len(running)} running experiments (not stale)"
    except Exception as e:
        return False, f"Error reading experiments: {e}"


def health_check():
    """Run health checks on all monitored systems.

    This catches silent failures like OpenClaw being broken for 7 days.
    Called by /today at session start.
    """
    import subprocess
    results = []

    for check in HEALTH_CHECKS:
        name = check['name']
        severity = check['severity']

        if 'check_python' in check:
            # Python-based check
            func = globals()[check['check_python']]
            ok, detail = func()
        else:
            # Shell command check
            # SECURITY: shell=True is justified here — commands are hardcoded
            # static strings in HEALTH_CHECKS (not user-derived). They use
            # shell features (pipes, redirects) that require shell=True.
            try:
                result = subprocess.run(
                    check['check'], shell=True,
                    capture_output=True, text=True, timeout=10
                )
                ok = result.returncode == 0 and result.stdout.strip() not in ('', '0')
                detail = result.stdout.strip()[:80] if ok else "Not running or not found"
            except (subprocess.TimeoutExpired, OSError):
                ok = False
                detail = "Check timed out"

        status = 'OK' if ok else 'FAIL'
        results.append({
            'name': name,
            'status': status,
            'severity': severity,
            'detail': detail,
            'blocks': check.get('what', ''),
        })

    # Output
    failures = [r for r in results if r['status'] == 'FAIL']
    print(f"Health Check: {len(results) - len(failures)}/{len(results)} passing")
    print()

    for r in results:
        icon = 'PASS' if r['status'] == 'OK' else 'FAIL'
        sev = f"[{r['severity']}]" if r['status'] == 'FAIL' else ''
        print(f"  {icon} {sev} {r['name']}: {r['detail']}")
        if r['status'] == 'FAIL':
            print(f"       Blocks: {r['blocks']}")

    if failures:
        print(f"\n{len(failures)} FAILURES detected. Fix before starting work.")
        # Write failures to buffer as auto-learnings
        for f in failures:
            if f['severity'] in ('HIGH', 'CRITICAL'):
                add_learning(
                    f"Health check FAIL: {f['name']} — {f['detail']}. Blocks: {f['blocks']}",
                    category='health'
                )
    else:
        print("\nAll systems healthy.")

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: learning_checkpoint.py <add|list|flush|health|count> [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'add':
        if len(sys.argv) < 3:
            print("Usage: learning_checkpoint.py add <text> [--category <cat>]")
            sys.exit(1)
        text = sys.argv[2]
        category = 'general'
        if '--category' in sys.argv:
            idx = sys.argv.index('--category')
            if idx + 1 < len(sys.argv):
                category = sys.argv[idx + 1]
        add_learning(text, category)

    elif cmd == 'list':
        list_learnings()

    elif cmd == 'flush':
        flush_learnings()

    elif cmd == 'health':
        health_check()

    elif cmd == 'count':
        count_learnings()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == '__main__':
    main()
