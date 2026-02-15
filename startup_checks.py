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
import os
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


def check_delegation_health():
    """Step 1k: Live LLM backend health — verifies delegation can actually work."""
    import urllib.request
    results = {}

    # 1. Check GEMINI_API_KEY is set
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    results['gemini_api_key'] = 'set' if gemini_key else 'MISSING'

    # 2. Check Ollama is running and responsive
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/version",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            version = data.get("version", "unknown")
            results['ollama'] = f'running (v{version})'
    except Exception:
        results['ollama'] = 'NOT RUNNING'

    # 3. Check Ollama has models loaded
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            models = [m.get('name', '?') for m in data.get('models', [])]
            results['ollama_models'] = models if models else ['NONE']
    except Exception:
        results['ollama_models'] = ['check_failed']

    # 4. Test prefetch from Ollama (quick ping — "What is 2+2?")
    try:
        payload = json.dumps({
            "model": "mistral:7b",
            "messages": [{"role": "user", "content": "What is 2+2? Answer with just the number."}],
            "stream": False,
            "options": {"num_predict": 10},
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        start = time.time()
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
            answer = data.get("message", {}).get("content", "").strip()[:50]
            latency = round((time.time() - start) * 1000)
            results['ollama_prefetch'] = f'OK ({latency}ms): "{answer}"'
    except Exception as e:
        results['ollama_prefetch'] = f'FAILED: {str(e)[:80]}'

    # 5. Test Gemini REST API (only if key is set)
    if gemini_key:
        try:
            payload = json.dumps({
                "contents": [{"parts": [{"text": "What is 2+2? Answer with just the number."}]}],
                "generationConfig": {"maxOutputTokens": 10, "temperature": 0},
            }).encode()
            req = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": gemini_key,
                },
            )
            start = time.time()
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                answer = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()[:50]
                latency = round((time.time() - start) * 1000)
                results['gemini_api'] = f'OK ({latency}ms): "{answer}"'
        except Exception as e:
            results['gemini_api'] = f'FAILED: {str(e)[:80]}'
    else:
        results['gemini_api'] = 'SKIPPED (no key)'

    # 6. Check delegation hook is registered (check both settings files)
    hook_found = False
    for settings_name in ['settings.json', 'settings.local.json']:
        settings = Path.home() / '.claude' / settings_name
        if not settings.exists():
            continue
        try:
            sdata = json.loads(settings.read_text())
            hooks = sdata.get('hooks', {})
            # Hooks can be nested: {event: [{hooks: [{command: ...}]}]}
            for event_hooks in hooks.values():
                items = event_hooks if isinstance(event_hooks, list) else [event_hooks]
                for item in items:
                    if isinstance(item, dict):
                        inner = item.get('hooks', [item])
                        for h in (inner if isinstance(inner, list) else [inner]):
                            if 'delegation_hook' in str(h):
                                hook_found = True
                    elif 'delegation_hook' in str(item):
                        hook_found = True
        except Exception:
            pass
    results['hook_registered'] = 'yes' if hook_found else 'NOT FOUND'

    # 7. Check compliance file
    comp = LOCKS / 'delegation-compliance.json'
    if comp.exists():
        try:
            cdata = json.loads(comp.read_text())
            results['compliance'] = cdata
        except Exception:
            results['compliance'] = 'invalid_json'
    else:
        results['compliance'] = 'no_file'

    # Determine overall status
    problems = []
    if results['gemini_api_key'] == 'MISSING':
        problems.append('GEMINI_API_KEY not set')
    if 'NOT RUNNING' in str(results.get('ollama', '')):
        problems.append('Ollama not running')
    if 'FAILED' in str(results.get('ollama_prefetch', '')):
        problems.append('Ollama prefetch failed')
    if 'NOT FOUND' in str(results.get('hook_registered', '')):
        problems.append('Delegation hook not registered')

    status = 'ok' if not problems else 'degraded'
    return {'status': status, 'problems': problems, 'data': results}


def build_context_package():
    """Build delegation context package for Gemini/Qwen handoff."""
    try:
        result = subprocess.run(
            [sys.executable, str(HOME / 'Development' / 'tools' / 'build_context_pkg.py'), '--validate'],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout.strip()
        if result.returncode == 0:
            return {'status': 'ok', 'data': output}
        else:
            return {'status': 'failed', 'data': output or result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {'status': 'timeout'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def check_gemini_routing():
    """Step 1l: Gemini template routing health — checks eval log and daily counter."""
    eval_log = LOCKS / 'gemini-route-eval.jsonl'
    counter_file = LOCKS / 'gemini-daily-counter.json'
    results = {}

    # 1. Parse eval log
    if eval_log.exists():
        try:
            lines = [l.strip() for l in eval_log.read_text().strip().split('\n') if l.strip()]
            entries = [json.loads(l) for l in lines]
            total = len(entries)
            ok = sum(1 for e in entries if e.get('success'))
            total_saved = sum(e.get('est_tokens_saved', 0) for e in entries)

            # Per-category stats
            by_cat = {}
            for e in entries:
                cat = e.get('category', 'unknown')
                if cat not in by_cat:
                    by_cat[cat] = {'calls': 0, 'ok': 0}
                by_cat[cat]['calls'] += 1
                if e.get('success'):
                    by_cat[cat]['ok'] += 1

            results['eval_log'] = {
                'total_calls': total,
                'success': ok,
                'success_rate': round(ok / total * 100) if total else 0,
                'est_tokens_saved': total_saved,
                'categories_used': len(by_cat),
                'top_categories': sorted(by_cat.items(), key=lambda x: x[1]['calls'], reverse=True)[:5],
            }
        except Exception as e:
            results['eval_log'] = {'error': str(e)}
    else:
        results['eval_log'] = {'total_calls': 0, 'message': 'No routing data yet'}

    # 2. Parse daily counter
    if counter_file.exists():
        try:
            counter = json.loads(counter_file.read_text())
            results['daily_counter'] = {
                'date': counter.get('date', '?'),
                'count': counter.get('count', 0),
                'cap': 200,
                'pct_used': round(counter.get('count', 0) / 200 * 100),
            }
        except Exception as e:
            results['daily_counter'] = {'error': str(e)}
    else:
        results['daily_counter'] = {'count': 0, 'message': 'No counter yet'}

    # 3. Check template files exist
    template_dir = TOOLS / 'gemini-templates'
    if template_dir.exists():
        templates = list(template_dir.glob('*.txt'))
        results['templates_on_disk'] = len(templates)
    else:
        results['templates_on_disk'] = 0

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
        'delegation_health': check_delegation_health,
        'gemini_routing': check_gemini_routing,
        'context_package': build_context_package,
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

    # Delegation health problems
    deleg_health = results.get('delegation_health', {})
    for prob in deleg_health.get('problems', []):
        issues.append(f'delegation:{prob}')

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

    # Delegation stats
    deleg = checks.get('delegation', {})
    if deleg.get('status') == 'ok':
        d = deleg['data']
        lines.append(f"Delegation stats: {d['total_prompts']} prompts, {d['total_delegated']} delegated, {d['consecutive_ignored']} ignored")

    # Delegation health (live LLM checks)
    dh = checks.get('delegation_health', {})
    if dh.get('status'):
        dhd = dh.get('data', {})
        lines.append(f"Delegation health: {dh['status'].upper()}")
        lines.append(f"  Gemini API key: {dhd.get('gemini_api_key', '?')}")
        lines.append(f"  Ollama: {dhd.get('ollama', '?')}")
        lines.append(f"  Ollama models: {', '.join(dhd.get('ollama_models', ['?']))}")
        lines.append(f"  Ollama prefetch: {dhd.get('ollama_prefetch', '?')}")
        lines.append(f"  Gemini API: {dhd.get('gemini_api', '?')}")
        lines.append(f"  Hook registered: {dhd.get('hook_registered', '?')}")
        if dh.get('problems'):
            for p in dh['problems']:
                lines.append(f"  PROBLEM: {p}")

    # Gemini routing
    gr = checks.get('gemini_routing', {}).get('data', {})
    eval_data = gr.get('eval_log', {})
    daily = gr.get('daily_counter', {})
    if eval_data.get('total_calls', 0) > 0:
        lines.append(f"Gemini routing: {eval_data['total_calls']} calls, {eval_data.get('success_rate', 0)}% success, ~{eval_data.get('est_tokens_saved', 0):,} tokens saved")
        top = eval_data.get('top_categories', [])
        if top:
            top_str = ', '.join(f"{cat}({s['calls']})" for cat, s in top[:3])
            lines.append(f"  Top templates: {top_str}")
    else:
        lines.append("Gemini routing: No routing data yet")
    if daily.get('count', 0) > 0:
        lines.append(f"  Gemini API today: {daily['count']}/{daily.get('cap', 200)} ({daily.get('pct_used', 0)}%)")
    lines.append(f"  Templates on disk: {gr.get('templates_on_disk', '?')}")

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
