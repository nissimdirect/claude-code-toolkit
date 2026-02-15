#!/usr/bin/env python3
"""Consolidated Startup Health Checks — startup_checks.py

Runs ALL /today health checks in parallel and returns a single JSON summary.
Replaces 14 sequential tool calls with ONE invocation. Code > Tokens.

Usage:
    python3 ~/Development/tools/startup_checks.py           # Full check (all steps)
    python3 ~/Development/tools/startup_checks.py --json     # JSON-only output
    python3 ~/Development/tools/startup_checks.py --run-workflows  # Also auto-run code-only workflow steps

Created: 2026-02-15 | Owner: /today skill
"""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

HOME = Path.home()
TOOLS = HOME / 'Development' / 'tools'
HOOKS = HOME / '.claude' / 'hooks'
LOCKS = HOME / '.claude' / '.locks'

# ─── Individual Check Functions ───────────────────────────────────────────────

def check_experiments():
    """Step 1d: Active experiments"""
    try:
        r = subprocess.run(
            ['python3', str(TOOLS / 'experiment_tracker.py'), 'check'],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        return {'status': 'ok', 'data': data}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_consistency():
    """Step 1e: Cross-file consistency"""
    try:
        r = subprocess.run(
            ['python3', str(TOOLS / 'consistency_checker.py'), '--summary'],
            capture_output=True, text=True, timeout=30
        )
        output = r.stdout.strip()
        # Parse "Consistency: N issues (X critical, Y high) | Z fixable"
        parts = {}
        if 'issues' in output:
            import re
            m = re.search(r'(\d+) issues.*?(\d+) critical.*?(\d+) high', output)
            if m:
                parts = {'total': int(m.group(1)), 'critical': int(m.group(2)), 'high': int(m.group(3))}
        return {'status': 'ok', 'data': parts, 'raw': output}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_rule_inflation():
    """Step 1f: Rule inflation gate"""
    try:
        r = subprocess.run(
            ['python3', str(TOOLS / 'coverage_matrix.py'), 'gate'],
            capture_output=True, text=True, timeout=15
        )
        output = r.stdout.strip()
        passed = 'GATE PASSED' in output or r.returncode == 0
        # Extract counts
        counts = {}
        for line in output.split('\n'):
            line = line.strip()
            for cat in ['core_principles', 'domain_principles', 'meta_directives', 'claude_md_rules']:
                if cat in line:
                    parts = line.split()
                    try:
                        idx = parts.index(cat)
                        counts[cat] = {'count': int(parts[idx+1]), 'cap': int(parts[idx+2])}
                    except (IndexError, ValueError):
                        pass
        return {'status': 'passed' if passed else 'failed', 'data': counts, 'raw': output}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_hooks():
    """Step 1g: Hook regression tests"""
    try:
        r = subprocess.run(
            ['python3', str(HOOKS / 'hook_test.py'), '--quick', '--json'],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        return {'status': 'ok', 'data': data}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_learning_index():
    """Step 1h: Learning system health"""
    try:
        idx = LOCKS / 'learning-index.json'
        if not idx.exists():
            return {'status': 'rebuild_needed', 'reason': 'Index missing'}
        if time.time() - idx.stat().st_mtime > 86400:
            return {'status': 'rebuild_needed', 'reason': 'Index stale (>24h)'}
        data = json.loads(idx.read_text())
        return {'status': 'ok', 'data': {
            'total': data.get('total_learnings', 0),
            'graduation_candidates': data.get('graduation_candidates', 0),
            'mechanical': data.get('mechanical_count', 0),
            'judgment': data.get('judgment_count', 0),
        }}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_schedule():
    """Step 1h(2): Workflow calendar"""
    try:
        r = subprocess.run(
            ['python3', str(TOOLS / 'schedule_checker.py'), 'check'],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        # Summarize: count by tier
        due = data.get('due', [])
        by_tier = {}
        for w in due:
            t = w.get('budget_tier', 'unknown')
            by_tier[t] = by_tier.get(t, 0) + 1
        return {'status': 'ok', 'data': {
            'due_count': len(due),
            'by_tier': by_tier,
            'workflows': [{'id': w['id'], 'name': w['name'], 'tier': w['budget_tier'], 'freq': w['frequency']} for w in due],
            'quarter_change': data.get('quarter_change', False),
        }}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_violations():
    """Step 1i: Violation trends"""
    try:
        r = subprocess.run(
            ['python3', str(TOOLS / 'violation_trend.py'), 'summary'],
            capture_output=True, text=True, timeout=15
        )
        output = r.stdout.strip()
        # Parse "Violations: N across M sessions (X/session)\nTop violation: Y (Zx)"
        import re
        data = {'raw': output}
        m = re.search(r'(\d+) across (\d+) sessions.*?([\d.]+)/session', output)
        if m:
            data['total'] = int(m.group(1))
            data['sessions'] = int(m.group(2))
            data['per_session'] = float(m.group(3))
        m2 = re.search(r'Top violation: (\w+) \((\d+)x\)', output)
        if m2:
            data['top_type'] = m2.group(1)
            data['top_count'] = int(m2.group(2))
        return {'status': 'ok', 'data': data}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_delegation():
    """Step 1j: Delegation audit log"""
    try:
        log = LOCKS / 'delegation-hook-audit.log'
        comp = LOCKS / 'delegation-compliance.json'
        if not log.exists():
            return {'status': 'no_data', 'message': 'No audit log yet'}

        lines = log.read_text().strip().split('\n')
        models, tones = {}, {}
        for line in lines:
            for token in line.split():
                if token.startswith('model='):
                    m = token.split('=')[1]
                    models[m] = models.get(m, 0) + 1
                if token.startswith('tone='):
                    t = token.split('=')[1]
                    tones[t] = tones.get(t, 0) + 1
        total = len(lines)
        delegatable = total - models.get('claude', 0)

        compliance = {}
        if comp.exists():
            compliance = json.loads(comp.read_text())

        return {'status': 'ok', 'data': {
            'total_prompts': total,
            'delegatable': delegatable,
            'delegatable_pct': round(delegatable / total * 100) if total > 0 else 0,
            'models': models,
            'tones': tones,
            'consecutive_ignored': compliance.get('consecutive_ignored', 0),
            'total_delegated': compliance.get('total_delegated', 0),
        }}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_repos():
    """Step 1b: Uncommitted work in active repos"""
    repos = [
        HOME / 'Development' / 'entropic',
        HOME / 'Development' / 'tools',
        HOME / 'Development' / 'cymatics',
    ]
    results = {}
    for repo in repos:
        if not (repo / '.git').exists():
            results[repo.name] = {'status': 'not_git'}
            continue
        try:
            r = subprocess.run(
                ['git', 'status', '-s'],
                capture_output=True, text=True, timeout=10, cwd=str(repo)
            )
            changes = r.stdout.strip()
            results[repo.name] = {
                'status': 'dirty' if changes else 'clean',
                'changes': changes if changes else None,
            }
        except Exception as e:
            results[repo.name] = {'status': 'error', 'error': str(e)}
    return {'status': 'ok', 'data': results}


def check_openclaw_exchange():
    """Step 1c: New files from Entropy Bot"""
    exchange = HOME / 'Development' / 'AI-Knowledge-Exchange' / 'entropy-insights'
    if not exchange.exists():
        return {'status': 'no_dir'}
    try:
        # Find files modified in last 48 hours
        cutoff = time.time() - (48 * 3600)
        new_files = []
        for f in exchange.rglob('*.md'):
            if f.stat().st_mtime > cutoff:
                new_files.append({
                    'name': f.name,
                    'path': str(f.relative_to(exchange)),
                    'modified': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
                })
        return {'status': 'ok', 'data': {'new_files': new_files, 'count': len(new_files)}}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


# ─── Workflow Auto-Run (code-only parts) ─────────────────────────────────────

def run_workflow_testing_pipeline():
    """Workflow: testing-pipeline — code-only parts"""
    results = {}
    # 1. py_compile all tools
    tools_dir = TOOLS
    compile_errors = []
    for py in tools_dir.glob('*.py'):
        r = subprocess.run(
            ['python3', '-m', 'py_compile', str(py)],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            compile_errors.append(py.name)
    results['py_compile'] = {'total': len(list(tools_dir.glob('*.py'))), 'errors': compile_errors}

    # 2. Consistency checker (already running in parallel, just mark as done)
    results['consistency'] = 'included_in_main_checks'

    return {'status': 'ok', 'data': results}


def run_workflow_backup_audit():
    """Workflow: backup-audit — code-only parts"""
    results = {}
    # 1. Check state files are valid JSON
    state_files = [
        LOCKS / 'calendar-state.json',
        LOCKS / '.budget-state.json',
        LOCKS / 'learning-index.json',
        LOCKS / 'kb-source-weights.json',
    ]
    for sf in state_files:
        if not sf.exists():
            results[sf.name] = 'missing'
        else:
            try:
                json.loads(sf.read_text())
                results[sf.name] = 'valid'
            except json.JSONDecodeError:
                results[sf.name] = 'invalid_json'

    # 2. Check stale lock files (>24h)
    stale = []
    for lf in LOCKS.glob('*.lock'):
        if time.time() - lf.stat().st_mtime > 86400:
            stale.append(lf.name)
    results['stale_locks'] = stale

    # 3. Check launchd jobs
    try:
        r = subprocess.run(
            ['launchctl', 'list'],
            capture_output=True, text=True, timeout=10
        )
        popchaos = [l for l in r.stdout.split('\n') if 'popchaos' in l.lower()]
        results['launchd'] = popchaos if popchaos else 'none_found'
    except Exception:
        results['launchd'] = 'check_failed'

    return {'status': 'ok', 'data': results}


# ─── Main Orchestrator ────────────────────────────────────────────────────────

def run_all_checks(run_workflows=False):
    """Run all checks in parallel, return unified JSON."""
    checks = {
        'experiments': check_experiments,
        'consistency': check_consistency,
        'rule_inflation': check_rule_inflation,
        'hooks': check_hooks,
        'learning_index': check_learning_index,
        'schedule': check_schedule,
        'violations': check_violations,
        'delegation': check_delegation,
        'repos': check_repos,
        'openclaw_exchange': check_openclaw_exchange,
    }

    if run_workflows:
        checks['wf_testing_pipeline'] = run_workflow_testing_pipeline
        checks['wf_backup_audit'] = run_workflow_backup_audit

    results = {}
    start = time.time()

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fn): name for name, fn in checks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as e:
                results[name] = {'status': 'crash', 'error': str(e)}

    elapsed = round(time.time() - start, 2)

    # Build summary line
    issues = []
    if results.get('rule_inflation', {}).get('status') == 'failed':
        issues.append('rule_inflation_gate_failed')
    if results.get('consistency', {}).get('data', {}).get('critical', 0) > 0:
        issues.append('critical_consistency_issues')
    if results.get('hooks', {}).get('data', {}).get('critical_failures', 0) > 0:
        issues.append('hook_critical_failures')
    if results.get('violations', {}).get('data', {}).get('per_session', 0) > 3:
        issues.append('high_violation_rate')
    if results.get('learning_index', {}).get('status') == 'rebuild_needed':
        issues.append('learning_index_stale')

    dirty_repos = [k for k, v in results.get('repos', {}).get('data', {}).items()
                   if v.get('status') == 'dirty']
    if dirty_repos:
        issues.append(f'uncommitted_work:{",".join(dirty_repos)}')

    output = {
        'timestamp': datetime.now().isoformat(),
        'elapsed_seconds': elapsed,
        'issue_count': len(issues),
        'issues': issues,
        'checks': results,
    }

    return output


def format_human_readable(data):
    """Format JSON results as a compact human-readable summary."""
    lines = []
    lines.append(f"Startup checks completed in {data['elapsed_seconds']}s")
    lines.append("")

    # Issues summary
    if data['issues']:
        lines.append(f"ISSUES ({data['issue_count']}):")
        for issue in data['issues']:
            lines.append(f"  - {issue}")
        lines.append("")

    checks = data['checks']

    # Repos
    repos = checks.get('repos', {}).get('data', {})
    dirty = [k for k, v in repos.items() if v.get('status') == 'dirty']
    if dirty:
        lines.append(f"Repos: {', '.join(dirty)} have uncommitted changes")
    else:
        lines.append("Repos: All clean")

    # Hooks
    hooks = checks.get('hooks', {}).get('data', {})
    lines.append(f"Hooks: {hooks.get('passed', '?')}/{hooks.get('total', '?')} PASS")

    # Learning index
    li = checks.get('learning_index', {})
    if li.get('status') == 'ok':
        d = li['data']
        lines.append(f"Learning: {d['total']} learnings, {d['graduation_candidates']} graduation candidates")
    else:
        lines.append(f"Learning: {li.get('status', 'unknown')} — {li.get('reason', '')}")

    # Rule inflation
    ri = checks.get('rule_inflation', {})
    lines.append(f"Rules: {'PASSED' if ri.get('status') == 'passed' else 'FAILED'}")
    for cat, vals in ri.get('data', {}).items():
        if isinstance(vals, dict):
            status = 'OVER' if vals.get('count', 0) > vals.get('cap', 999) else 'ok'
            lines.append(f"  {cat}: {vals.get('count')}/{vals.get('cap')} ({status})")

    # Consistency
    con = checks.get('consistency', {}).get('data', {})
    if con:
        lines.append(f"Consistency: {con.get('total', 0)} issues ({con.get('critical', 0)} critical)")

    # Violations
    viol = checks.get('violations', {}).get('data', {})
    if viol.get('total'):
        lines.append(f"Violations: {viol['total']} across {viol.get('sessions', '?')} sessions ({viol.get('per_session', '?')}/session), top: {viol.get('top_type', '?')} ({viol.get('top_count', '?')}x)")
    else:
        lines.append("Violations: Clean record")

    # Delegation
    deleg = checks.get('delegation', {})
    if deleg.get('status') == 'ok':
        d = deleg['data']
        lines.append(f"Delegation: {d['total_prompts']} prompts, {d['total_delegated']} delegated, {d['consecutive_ignored']} ignored")

    # Experiments
    exp = checks.get('experiments', {})
    if exp.get('data', {}).get('status') == 'no_experiments':
        lines.append("Experiments: None active")
    else:
        lines.append(f"Experiments: {exp.get('data', {})}")

    # Schedule
    sched = checks.get('schedule', {}).get('data', {})
    if sched:
        lines.append(f"Workflows due: {sched.get('due_count', 0)} (by tier: {sched.get('by_tier', {})})")

    # OpenClaw
    oc = checks.get('openclaw_exchange', {}).get('data', {})
    if oc.get('count', 0) > 0:
        lines.append(f"OpenClaw: {oc['count']} new file(s) in last 48h")
        for f in oc.get('new_files', []):
            lines.append(f"  - {f['name']} ({f['modified']})")

    # Workflow auto-run results
    if 'wf_testing_pipeline' in checks:
        tp = checks['wf_testing_pipeline'].get('data', {})
        pc = tp.get('py_compile', {})
        errors = pc.get('errors', [])
        lines.append(f"WF testing-pipeline: {pc.get('total', 0)} files compiled, {len(errors)} errors")
        if errors:
            for e in errors:
                lines.append(f"  FAIL: {e}")

    if 'wf_backup_audit' in checks:
        ba = checks['wf_backup_audit'].get('data', {})
        stale = ba.get('stale_locks', [])
        invalid = [k for k, v in ba.items() if v == 'invalid_json']
        lines.append(f"WF backup-audit: {len(stale)} stale locks, {len(invalid)} invalid state files")

    return '\n'.join(lines)


if __name__ == '__main__':
    json_only = '--json' in sys.argv
    run_wf = '--run-workflows' in sys.argv

    data = run_all_checks(run_workflows=run_wf)

    if json_only:
        print(json.dumps(data, indent=2))
    else:
        print(format_human_readable(data))
        if data['issues']:
            sys.exit(1)
