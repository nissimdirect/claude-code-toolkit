#!/usr/bin/env python3
"""Violation Trend Analyzer — reads ERROR-LOG.md and reports patterns.

Usage:
    python3 ~/Development/tools/violation_trend.py summary   # Quick summary (for /today)
    python3 ~/Development/tools/violation_trend.py report    # Full trend report (for /self-improve)
    python3 ~/Development/tools/violation_trend.py json      # Machine-readable output

Integrated into:
  /today (Step 1g) — surfaces top violation and session count
  /self-improve (Layer 2) — full behavioral trend analysis
"""

import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ERROR_LOG = Path.home() / 'Documents' / 'Obsidian' / 'process' / 'ERROR-LOG.md'


def parse_error_log() -> list[dict]:
    """Parse ERROR-LOG.md into structured violation records."""
    if not ERROR_LOG.exists():
        return []

    content = ERROR_LOG.read_text()
    violations = []

    current_date = None
    for line in content.splitlines():
        # Match date headers: ### 2026-02-14 15:46
        date_match = re.match(r'^### (\d{4}-\d{2}-\d{2} \d{2}:\d{2})', line)
        if date_match:
            current_date = date_match.group(1)
            continue

        # Match violation entries: - **CRITICAL** `edit_without_read` — detail
        viol_match = re.match(
            r'^- \*\*(\w+)\*\* `([^`]+)` — (.+)$', line
        )
        if viol_match and current_date:
            violations.append({
                'timestamp': current_date,
                'severity': viol_match.group(1),
                'type': viol_match.group(2),
                'detail': viol_match.group(3),
            })

    return violations


def count_sessions(violations: list[dict]) -> int:
    """Count distinct session timestamps (unique date-hour combos)."""
    timestamps = {v['timestamp'][:13] for v in violations}  # YYYY-MM-DD HH
    return max(len(timestamps), 1)


def analyze(violations: list[dict]) -> dict:
    """Analyze violations for trends and patterns."""
    if not violations:
        return {
            'total': 0,
            'sessions': 0,
            'per_session': 0.0,
            'by_type': {},
            'by_severity': {},
            'top_type': None,
            'top_detail': None,
            'recent_7d': 0,
            'improving': None,
        }

    sessions = count_sessions(violations)
    type_counts = Counter(v['type'] for v in violations)
    severity_counts = Counter(v['severity'] for v in violations)
    detail_counts = Counter(v['detail'] for v in violations)

    top_type = type_counts.most_common(1)[0] if type_counts else (None, 0)
    top_detail = detail_counts.most_common(1)[0] if detail_counts else (None, 0)

    # Recent vs older (7-day window)
    now = datetime.now()
    recent = [
        v for v in violations
        if _parse_ts(v['timestamp']) and (now - _parse_ts(v['timestamp'])) < timedelta(days=7)
    ]
    older = [
        v for v in violations
        if _parse_ts(v['timestamp']) and (now - _parse_ts(v['timestamp'])) >= timedelta(days=7)
    ]

    # Trend detection: compare recent rate vs older rate
    improving = None
    if older and recent:
        recent_sessions = max(count_sessions(recent), 1)
        older_sessions = max(count_sessions(older), 1)
        recent_rate = len(recent) / recent_sessions
        older_rate = len(older) / older_sessions
        if recent_rate < older_rate * 0.7:
            improving = True
        elif recent_rate > older_rate * 1.3:
            improving = False

    return {
        'total': len(violations),
        'sessions': sessions,
        'per_session': round(len(violations) / sessions, 1),
        'by_type': dict(type_counts.most_common()),
        'by_severity': dict(severity_counts),
        'top_type': top_type[0] if top_type else None,
        'top_type_count': top_type[1] if top_type else 0,
        'top_detail': top_detail[0] if top_detail else None,
        'recent_7d': len(recent),
        'improving': improving,
    }


def _parse_ts(ts_str: str):
    """Parse timestamp string to datetime."""
    try:
        return datetime.strptime(ts_str, '%Y-%m-%d %H:%M')
    except ValueError:
        return None


def print_summary(analysis: dict):
    """Quick summary for /today integration."""
    if analysis['total'] == 0:
        print('Violations: 0 (no data yet)')
        return

    trend = ''
    if analysis['improving'] is True:
        trend = ' (improving)'
    elif analysis['improving'] is False:
        trend = ' (getting worse!)'

    print(f"Violations: {analysis['total']} across {analysis['sessions']} sessions "
          f"({analysis['per_session']}/session){trend}")

    if analysis['top_type']:
        print(f"Top violation: {analysis['top_type']} ({analysis['top_type_count']}x)")

    crit = analysis['by_severity'].get('CRITICAL', 0)
    if crit > 0:
        print(f"CRITICAL: {crit} — needs mechanical enforcement or habit change")


def print_report(analysis: dict):
    """Full trend report for /self-improve integration."""
    print('## Violation Trend Report')
    print(f"Source: {ERROR_LOG}")
    print()

    if analysis['total'] == 0:
        print('No violations recorded yet. System is clean or just deployed.')
        print('Check back after 5+ sessions.')
        return

    print(f"**Total violations:** {analysis['total']}")
    print(f"**Sessions tracked:** {analysis['sessions']}")
    print(f"**Average per session:** {analysis['per_session']}")
    print(f"**Last 7 days:** {analysis['recent_7d']}")
    print()

    if analysis['improving'] is True:
        print('**Trend: IMPROVING** — violation rate is decreasing')
    elif analysis['improving'] is False:
        print('**Trend: WORSENING** — violation rate is increasing. Investigate root cause.')
    else:
        print('**Trend:** Insufficient data for comparison')
    print()

    print('### By Type')
    for vtype, count in sorted(analysis['by_type'].items(), key=lambda x: -x[1]):
        print(f'- `{vtype}`: {count}')
    print()

    print('### By Severity')
    for sev in ['CRITICAL', 'MEDIUM', 'INFO']:
        count = analysis['by_severity'].get(sev, 0)
        if count > 0:
            print(f'- **{sev}**: {count}')
    print()

    if analysis['top_type']:
        print(f"### Top Offender: `{analysis['top_type']}` ({analysis['top_type_count']}x)")
        if analysis['top_detail']:
            print(f"Most common: {analysis['top_detail']}")
        print()

    # Recommendations
    print('### Recommendations')
    if analysis['per_session'] > 3:
        print('- Per-session rate > 3 — consider adding mechanical enforcement for top violation type')
    if analysis['by_severity'].get('CRITICAL', 0) > analysis['total'] * 0.5:
        print('- >50% of violations are CRITICAL — this is a systemic issue, not occasional mistakes')
    if analysis['improving'] is False:
        print('- Worsening trend — review recent session changes that may have introduced regressions')
    if analysis['total'] < 5:
        print('- Insufficient data — collect 5+ sessions before drawing conclusions')


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('summary', 'report', 'json'):
        print('Usage: violation_trend.py summary|report|json')
        sys.exit(1)

    violations = parse_error_log()
    analysis = analyze(violations)

    if sys.argv[1] == 'summary':
        print_summary(analysis)
    elif sys.argv[1] == 'report':
        print_report(analysis)
    elif sys.argv[1] == 'json':
        print(json.dumps(analysis, indent=2))


if __name__ == '__main__':
    main()
