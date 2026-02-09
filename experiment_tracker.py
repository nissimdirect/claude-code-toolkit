#!/usr/bin/env python3
"""Experiment Tracker — Code-first experiment lifecycle management.

Usage:
    python3 experiment_tracker.py list                    # List all active experiments
    python3 experiment_tracker.py check                   # Session start/end check
    python3 experiment_tracker.py add "hypothesis" "method" "metric"  # Add new experiment
    python3 experiment_tracker.py update <id> <status> ["result"]     # Update status
    python3 experiment_tracker.py report                  # Generate summary report

Statuses: pending | running | completed | failed | invalidated

Experiment file: ~/Documents/Obsidian/process/ACTIVE-EXPERIMENTS.md
Results codified by Lenny (CPO) via /ask-lenny after completion.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

EXPERIMENTS_FILE = Path.home() / 'Documents' / 'Obsidian' / 'process' / 'ACTIVE-EXPERIMENTS.md'
EXPERIMENTS_JSON = Path.home() / '.claude' / '.locks' / 'experiments-state.json'


def load_experiments() -> list:
    """Load experiments from JSON state file."""
    if not EXPERIMENTS_JSON.exists():
        return []
    try:
        return json.loads(EXPERIMENTS_JSON.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def save_experiments(experiments: list):
    """Save experiments to JSON state file."""
    EXPERIMENTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    EXPERIMENTS_JSON.write_text(json.dumps(experiments, indent=2))


def sync_markdown(experiments: list):
    """Write experiments to the Obsidian markdown file."""
    EXPERIMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    active = [e for e in experiments if e['status'] in ('pending', 'running')]
    completed = [e for e in experiments if e['status'] == 'completed']
    failed = [e for e in experiments if e['status'] in ('failed', 'invalidated')]

    lines = [
        '# Active Experiments',
        '',
        '> Managed by `experiment_tracker.py`. Lenny (CPO) codifies learnings.',
        f'> Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        '',
        f'**Active:** {len(active)} | **Completed:** {len(completed)} | **Failed/Invalid:** {len(failed)}',
        '',
        '---',
        '',
    ]

    if active:
        lines.append('## Active Experiments')
        lines.append('')
        for e in active:
            status_icon = '🔬' if e['status'] == 'running' else '⏳'
            lines.append(f'### {status_icon} EXP-{e["id"]:03d}: {e["hypothesis"]}')
            lines.append(f'- **Status:** {e["status"]}')
            lines.append(f'- **Method:** {e["method"]}')
            lines.append(f'- **Success metric:** {e["metric"]}')
            lines.append(f'- **Source:** {e.get("source", "manual")}')
            lines.append(f'- **Created:** {e["created"]}')
            if e.get('notes'):
                lines.append(f'- **Notes:** {e["notes"]}')
            lines.append('')

    if completed:
        lines.append('## Completed Experiments')
        lines.append('')
        lines.append('| ID | Hypothesis | Result | Date |')
        lines.append('|----|-----------|--------|------|')
        for e in completed:
            result = e.get('result', 'no result recorded')
            lines.append(f'| EXP-{e["id"]:03d} | {e["hypothesis"][:50]} | {result[:60]} | {e.get("completed_date", "?")} |')
        lines.append('')

    if failed:
        lines.append('## Failed / Invalidated')
        lines.append('')
        for e in failed:
            lines.append(f'- **EXP-{e["id"]:03d}:** {e["hypothesis"]} — {e.get("result", "no reason")}')
        lines.append('')

    lines.append('---')
    lines.append('')
    lines.append('## Experiment Protocol')
    lines.append('')
    lines.append('1. **Add:** `python3 experiment_tracker.py add "hypothesis" "method" "metric"`')
    lines.append('2. **Start:** `python3 experiment_tracker.py update <id> running`')
    lines.append('3. **Complete:** `python3 experiment_tracker.py update <id> completed "result"`')
    lines.append('4. **Codify:** Invoke `/ask-lenny` to turn result into product learning')
    lines.append('5. **Propagate:** Update CLAUDE.md, behavioral-principles.md, or skills as needed')
    lines.append('')

    EXPERIMENTS_FILE.write_text('\n'.join(lines))


def add_experiment(hypothesis: str, method: str, metric: str, source: str = 'manual') -> dict:
    """Add a new experiment."""
    experiments = load_experiments()
    next_id = max((e['id'] for e in experiments), default=0) + 1

    exp = {
        'id': next_id,
        'hypothesis': hypothesis,
        'method': method,
        'metric': metric,
        'source': source,
        'status': 'pending',
        'created': datetime.now().strftime('%Y-%m-%d'),
        'notes': '',
        'result': '',
        'completed_date': '',
    }

    experiments.append(exp)
    save_experiments(experiments)
    sync_markdown(experiments)
    return exp


def update_experiment(exp_id: int, status: str, result: str = ''):
    """Update experiment status."""
    experiments = load_experiments()
    for e in experiments:
        if e['id'] == exp_id:
            old_status = e['status']
            e['status'] = status
            if result:
                e['result'] = result
            if status == 'completed':
                e['completed_date'] = datetime.now().strftime('%Y-%m-%d')
                # Print highly visible completion banner
                print('=' * 60)
                print(f'  EXPERIMENT VALIDATED: EXP-{exp_id:03d}')
                print(f'  "{e["hypothesis"]}"')
                print(f'  Result: {result or "no result recorded"}')
                print(f'  Duration: {e["created"]} -> {e["completed_date"]}')
                print('=' * 60)
                print(f'  Next: invoke /ask-lenny to codify as product learning')
                print(f'  Then: run `python3 {__file__} archive {exp_id}` to clean up')
                print('=' * 60)
            break
    else:
        print(f'Experiment EXP-{exp_id:03d} not found')
        sys.exit(1)

    save_experiments(experiments)
    sync_markdown(experiments)


def archive_experiments():
    """Move completed/failed/invalidated experiments to archive section.

    Removes them from the active JSON list and appends to an archive file.
    This keeps the active experiment list clean and focused.
    """
    experiments = load_experiments()
    active = [e for e in experiments if e['status'] in ('pending', 'running')]
    done = [e for e in experiments if e['status'] not in ('pending', 'running')]

    if not done:
        print('No completed experiments to archive.')
        return

    # Append to archive file
    archive_file = Path.home() / 'Documents' / 'Obsidian' / 'process' / 'EXPERIMENTS-ARCHIVE.md'
    archive_file.parent.mkdir(parents=True, exist_ok=True)

    archive_lines = []
    if archive_file.exists():
        archive_lines = archive_file.read_text().strip().split('\n')
    else:
        archive_lines = [
            '# Experiment Archive',
            '',
            '> Completed, failed, and invalidated experiments moved here from active tracking.',
            '',
        ]

    archive_lines.append(f'\n## Archived {datetime.now().strftime("%Y-%m-%d")}')
    archive_lines.append('')
    for e in done:
        status_icon = {'completed': '[VALIDATED]', 'failed': '[FAILED]', 'invalidated': '[INVALID]'}
        icon = status_icon.get(e['status'], '[?]')
        archive_lines.append(f'### {icon} EXP-{e["id"]:03d}: {e["hypothesis"]}')
        archive_lines.append(f'- **Result:** {e.get("result", "none")}')
        archive_lines.append(f'- **Period:** {e["created"]} - {e.get("completed_date", "?")}')
        archive_lines.append(f'- **Method:** {e["method"]}')
        archive_lines.append(f'- **Metric:** {e["metric"]}')
        archive_lines.append('')

    archive_file.write_text('\n'.join(archive_lines))

    # Save only active experiments
    save_experiments(active)
    sync_markdown(active)

    print(f'Archived {len(done)} experiments -> {archive_file}')
    print(f'Active experiments remaining: {len(active)}')


def session_check():
    """Session start/end check — returns summary for hook injection."""
    experiments = load_experiments()
    active = [e for e in experiments if e['status'] in ('pending', 'running')]
    running = [e for e in experiments if e['status'] == 'running']

    completed = [e for e in experiments if e['status'] == 'completed']

    if not active and not completed:
        print(json.dumps({'status': 'no_experiments', 'message': 'No active experiments.'}))
        return

    summary_parts = []
    if completed:
        summary_parts.append(f'{len(completed)} VALIDATED (need archiving):')
        for e in completed:
            summary_parts.append(f'  EXP-{e["id"]:03d}: {e["hypothesis"][:50]} -> {e.get("result", "?")[:30]}')

    if running:
        summary_parts.append(f'{len(running)} running:')
        for e in running:
            summary_parts.append(f'  EXP-{e["id"]:03d}: {e["hypothesis"][:60]}')

    pending = [e for e in experiments if e['status'] == 'pending']
    if pending:
        summary_parts.append(f'{len(pending)} pending:')
        for e in pending[:3]:  # Show first 3
            summary_parts.append(f'  EXP-{e["id"]:03d}: {e["hypothesis"][:60]}')
        if len(pending) > 3:
            summary_parts.append(f'  ...and {len(pending) - 3} more')

    message = '\n'.join(summary_parts)
    print(json.dumps({
        'status': 'active',
        'active_count': len(active),
        'running_count': len(running),
        'completed_count': len(completed),
        'message': message,
    }))


def list_experiments():
    """List all experiments in a compact format."""
    experiments = load_experiments()
    if not experiments:
        print('No experiments tracked yet.')
        return

    for e in experiments:
        status_map = {
            'pending': '[ ]',
            'running': '[~]',
            'completed': '[x]',
            'failed': '[!]',
            'invalidated': '[-]',
        }
        icon = status_map.get(e['status'], '[?]')
        print(f'{icon} EXP-{e["id"]:03d} ({e["status"]}): {e["hypothesis"][:70]}')


def report():
    """Generate summary report."""
    experiments = load_experiments()
    total = len(experiments)
    by_status = {}
    for e in experiments:
        by_status.setdefault(e['status'], []).append(e)

    print(f'Experiment Report — {datetime.now().strftime("%Y-%m-%d")}')
    print(f'Total: {total}')
    for status, exps in by_status.items():
        print(f'  {status}: {len(exps)}')

    completed = by_status.get('completed', [])
    if completed:
        print(f'\nRecent completions:')
        for e in completed[-5:]:
            print(f'  EXP-{e["id"]:03d}: {e["result"][:60]}')


def main():
    parser = argparse.ArgumentParser(description='Experiment Tracker')
    subparsers = parser.add_subparsers(dest='command')

    subparsers.add_parser('list', help='List all experiments')
    subparsers.add_parser('check', help='Session check (JSON output)')
    subparsers.add_parser('report', help='Summary report')
    subparsers.add_parser('archive', help='Archive completed/failed experiments')

    add_parser = subparsers.add_parser('add', help='Add experiment')
    add_parser.add_argument('hypothesis', help='What you believe to be true')
    add_parser.add_argument('method', help='How to test it')
    add_parser.add_argument('metric', help='How to measure success')
    add_parser.add_argument('--source', default='manual', help='Where this came from')

    update_parser = subparsers.add_parser('update', help='Update experiment')
    update_parser.add_argument('id', type=int, help='Experiment ID')
    update_parser.add_argument('status', choices=['pending', 'running', 'completed', 'failed', 'invalidated'])
    update_parser.add_argument('result', nargs='?', default='', help='Result description')

    args = parser.parse_args()

    if args.command == 'list':
        list_experiments()
    elif args.command == 'check':
        session_check()
    elif args.command == 'report':
        report()
    elif args.command == 'archive':
        archive_experiments()
    elif args.command == 'add':
        exp = add_experiment(args.hypothesis, args.method, args.metric, args.source)
        print(f'Added EXP-{exp["id"]:03d}: {exp["hypothesis"]}')
    elif args.command == 'update':
        update_experiment(args.id, args.status, args.result)
        if args.status != 'completed':  # completed prints its own banner
            print(f'Updated EXP-{args.id:03d} → {args.status}')
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
