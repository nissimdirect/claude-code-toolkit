#!/usr/bin/env python3
"""Quick delegation stats dashboard.

Usage: python3 ~/Development/tools/delegation_stats.py
"""

import json
from pathlib import Path
from collections import Counter

AUDIT_LOG = Path.home() / ".claude" / ".locks" / "delegation-hook-audit.log"
EVAL_LOG = Path.home() / ".claude" / ".locks" / "gemini-route-eval.jsonl"
COMPLIANCE = Path.home() / ".claude" / ".locks" / "delegation-compliance.json"
COUNTER = Path.home() / ".claude" / ".locks" / "gemini-daily-counter.json"

def parse_audit_line(line):
    """Extract key=value pairs from audit log line."""
    parts = {}
    for token in line.split():
        if '=' in token and not token.startswith('['):
            k, v = token.split('=', 1)
            parts[k] = v
    return parts

def main():
    print("=" * 55)
    print("  DELEGATION VISIBILITY DASHBOARD")
    print("=" * 55)

    # --- Hook Audit ---
    if AUDIT_LOG.exists():
        lines = [l.strip() for l in AUDIT_LOG.read_text().strip().split('\n') if l.strip()]
        entries = [parse_audit_line(l) for l in lines]

        actions = Counter(e.get('action', 'unknown') for e in entries)
        models = Counter(e.get('exec', 'unknown') for e in entries)
        prefetched = sum(1 for e in entries if e.get('prefetch') == 'OK')
        latencies = [int(e['latency'].rstrip('ms')) for e in entries if 'latency' in e]
        avg_lat = sum(latencies) // max(len(latencies), 1) if latencies else 0

        print(f"\n  Hook fires:       {len(entries)}")
        print(f"  Pre-fetched OK:   {prefetched} ({prefetched*100//max(len(entries),1)}%)")
        print(f"  Avg latency:      {avg_lat}ms")
        print(f"\n  Actions:")
        for action, count in actions.most_common():
            print(f"    {action:25s} {count:3d}")
        print(f"\n  Models executed:")
        for model, count in models.most_common():
            print(f"    {model:25s} {count:3d}")
    else:
        print("\n  No audit log yet.")

    # --- Gemini Route Eval ---
    if EVAL_LOG.exists():
        route_lines = [l.strip() for l in EVAL_LOG.read_text().strip().split('\n') if l.strip()]
        route_entries = [json.loads(l) for l in route_lines]
        cats = Counter(e['category'] for e in route_entries)
        total_saved = sum(e.get('est_tokens_saved', 0) for e in route_entries)
        ok = sum(1 for e in route_entries if e.get('success'))

        print(f"\n  --- Gemini Route Templates ---")
        print(f"  Calls:            {len(route_entries)}")
        print(f"  Success:          {ok}/{len(route_entries)}")
        print(f"  Est tokens saved: ~{total_saved:,}")
        print(f"\n  By category:")
        for cat, count in cats.most_common():
            print(f"    {cat:25s} {count:3d}")
    else:
        print("\n  No template routing data yet.")

    # --- Gemini Daily Counter ---
    if COUNTER.exists():
        try:
            counter = json.loads(COUNTER.read_text())
            print(f"\n  --- Gemini API Today ---")
            print(f"  Date:             {counter.get('date', '?')}")
            print(f"  Requests:         {counter.get('count', 0)}/200 cap (250 free tier)")
        except (json.JSONDecodeError, OSError):
            pass

    # --- Compliance ---
    if COMPLIANCE.exists():
        try:
            comp = json.loads(COMPLIANCE.read_text())
            print(f"\n  --- Compliance ---")
            print(f"  Total prompts:    {comp.get('total_prompts', 0)}")
            print(f"  Delegation rate:  {comp.get('delegation_rate', '0%')}")
            print(f"  Backend failures: {comp.get('backend_failures', 0)}")
        except (json.JSONDecodeError, OSError):
            pass

    print(f"\n{'=' * 55}")

if __name__ == '__main__':
    main()
