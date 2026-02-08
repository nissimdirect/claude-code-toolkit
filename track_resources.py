#!/usr/bin/env python3
"""
Resource tracking for Claude Code sessions
Tracks tokens, costs, and carbon footprint across all sessions
"""

import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Pricing (as of 2026-02)
PRICING = {
    'claude-sonnet-4-5-20250929': {
        'input': 3.00 / 1_000_000,   # $3 per million input tokens
        'output': 15.00 / 1_000_000,  # $15 per million output tokens
        'carbon': 0.0105  # grams CO2e per 1000 tokens (average)
    },
    'claude-opus-4-6': {
        'input': 15.00 / 1_000_000,
        'output': 75.00 / 1_000_000,
        'carbon': 0.0525
    },
    'claude-haiku-4-5-20251001': {
        'input': 0.80 / 1_000_000,
        'output': 4.00 / 1_000_000,
        'carbon': 0.0028
    }
}

def parse_session_file(jsonl_path):
    """Parse a session JSONL file and extract token usage"""
    usage_data = {
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 0,
        'messages': 0,
        'model': None,
        'start_time': None,
        'end_time': None
    }

    try:
        with open(jsonl_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)

                    # Extract timestamps (top-level field)
                    if 'timestamp' in data:
                        ts = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                        if not usage_data['start_time']:
                            usage_data['start_time'] = ts
                        usage_data['end_time'] = ts

                    # In Claude Code JSONL, model and usage are nested
                    # inside the 'message' object for assistant responses
                    msg = data.get('message', {})

                    # Extract model (inside message)
                    if not usage_data['model'] and 'model' in msg:
                        model = msg['model']
                        if model != '<synthetic>':
                            usage_data['model'] = model

                    # Extract token usage (inside message.usage)
                    usage = msg.get('usage', {})
                    input_tok = usage.get('input_tokens', 0)
                    output_tok = usage.get('output_tokens', 0)
                    cache_create = usage.get('cache_creation_input_tokens', 0)
                    cache_read = usage.get('cache_read_input_tokens', 0)

                    if input_tok > 0 or output_tok > 0 or cache_create > 0 or cache_read > 0:
                        usage_data['input_tokens'] += input_tok
                        usage_data['output_tokens'] += output_tok
                        usage_data['cache_creation_tokens'] += cache_create
                        usage_data['cache_read_tokens'] += cache_read
                        usage_data['messages'] += 1

                except json.JSONDecodeError:
                    continue

    except Exception as e:
        print(f"Error parsing {jsonl_path}: {e}")

    return usage_data

def calculate_costs(input_tokens, output_tokens, model,
                    cache_creation_tokens=0, cache_read_tokens=0):
    """Calculate cost and carbon for token usage.
    Cache creation is billed at 1.25x input price.
    Cache reads are billed at 0.1x input price.
    """
    if model not in PRICING:
        # Default to Sonnet if unknown
        model = 'claude-sonnet-4-5-20250929'

    pricing = PRICING[model]

    input_cost = input_tokens * pricing['input']
    output_cost = output_tokens * pricing['output']
    cache_create_cost = cache_creation_tokens * pricing['input'] * 1.25
    cache_read_cost = cache_read_tokens * pricing['input'] * 0.1

    cost = {
        'input': input_cost,
        'output': output_cost,
        'cache_creation': cache_create_cost,
        'cache_read': cache_read_cost,
        'total': input_cost + output_cost + cache_create_cost + cache_read_cost,
    }

    total_tokens = input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens
    carbon = (total_tokens / 1000) * pricing['carbon']

    return cost, carbon

def scan_all_sessions():
    """Scan all Claude Code session files"""
    claude_dir = Path.home() / '.claude' / 'projects'

    if not claude_dir.exists():
        return []

    sessions = []
    for jsonl_file in claude_dir.rglob('*.jsonl'):
        # Skip subagent files for now (they're included in main session)
        if 'subagents' in str(jsonl_file):
            continue

        usage = parse_session_file(jsonl_file)
        if (usage['input_tokens'] > 0 or usage['output_tokens'] > 0
                or usage.get('cache_creation_tokens', 0) > 0
                or usage.get('cache_read_tokens', 0) > 0):
            usage['session_file'] = str(jsonl_file)
            usage['session_id'] = jsonl_file.stem
            sessions.append(usage)

    return sessions

def generate_report(sessions, output_path=None):
    """Generate markdown report of all resource usage"""

    # Sort by start time
    sessions = sorted(sessions, key=lambda x: x['start_time'] or datetime.min, reverse=True)

    # Calculate totals
    total_input = sum(s['input_tokens'] for s in sessions)
    total_output = sum(s['output_tokens'] for s in sessions)
    total_cache_create = sum(s.get('cache_creation_tokens', 0) for s in sessions)
    total_cache_read = sum(s.get('cache_read_tokens', 0) for s in sessions)
    total_messages = sum(s['messages'] for s in sessions)

    # Group by model for cost calculation
    costs_by_model = defaultdict(lambda: {'input': 0, 'output': 0,
                                          'cache_creation': 0, 'cache_read': 0})
    for session in sessions:
        model = session['model'] or 'claude-sonnet-4-5-20250929'
        costs_by_model[model]['input'] += session['input_tokens']
        costs_by_model[model]['output'] += session['output_tokens']
        costs_by_model[model]['cache_creation'] += session.get('cache_creation_tokens', 0)
        costs_by_model[model]['cache_read'] += session.get('cache_read_tokens', 0)

    total_cost = 0
    total_carbon = 0
    for model, tokens in costs_by_model.items():
        cost, carbon = calculate_costs(tokens['input'], tokens['output'], model,
                                       tokens['cache_creation'], tokens['cache_read'])
        total_cost += cost['total']
        total_carbon += carbon

    # Generate markdown
    report = f"""# Claude Code Resource Tracker

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Sessions:** {len(sessions)}

---

## 📊 Lifetime Totals

| Metric | Value |
|--------|-------|
| **Input Tokens** | {total_input:,} |
| **Output Tokens** | {total_output:,} |
| **Cache Create Tokens** | {total_cache_create:,} |
| **Cache Read Tokens** | {total_cache_read:,} |
| **Total Tokens** | {total_input + total_output + total_cache_create + total_cache_read:,} |
| **Messages** | {total_messages:,} |
| **Total Cost** | ${total_cost:.2f} |
| **Total Carbon** | {total_carbon:.2f}g CO₂e |

**Average per Session:**
- Tokens: {(total_input + total_output) // max(len(sessions), 1):,}
- Cost: ${total_cost / max(len(sessions), 1):.2f}
- Carbon: {total_carbon / max(len(sessions), 1):.2f}g CO₂e

---

## 🔥 Current Session

"""

    # Current session (most recent)
    if sessions:
        current = sessions[0]
        model = current['model'] or 'claude-sonnet-4-5-20250929'
        cost, carbon = calculate_costs(current['input_tokens'], current['output_tokens'], model,
                                       current.get('cache_creation_tokens', 0),
                                       current.get('cache_read_tokens', 0))

        duration = "Unknown"
        if current['start_time'] and current['end_time']:
            delta = current['end_time'] - current['start_time']
            hours = delta.total_seconds() / 3600
            duration = f"{hours:.1f}h"

        report += f"""**Session ID:** `{current['session_id']}`
**Started:** {current['start_time'].strftime('%Y-%m-%d %H:%M') if current['start_time'] else 'Unknown'}
**Duration:** {duration}
**Model:** {model.split('-')[1].title() if '-' in model else model}

| Metric | Value |
|--------|-------|
| Input Tokens | {current['input_tokens']:,} |
| Output Tokens | {current['output_tokens']:,} |
| Total Tokens | {current['input_tokens'] + current['output_tokens']:,} |
| Messages | {current['messages']} |
| Cost | ${cost['total']:.2f} |
| Carbon | {carbon:.2f}g CO₂e |

---

## 📈 Session History

| Date | Duration | Tokens | Cost | Carbon | Model |
|------|----------|--------|------|--------|-------|
"""

        for session in sessions[:20]:  # Last 20 sessions
            model = session['model'] or 'claude-sonnet-4-5-20250929'
            cost, carbon = calculate_costs(session['input_tokens'], session['output_tokens'], model,
                                           session.get('cache_creation_tokens', 0),
                                           session.get('cache_read_tokens', 0))

            date = session['start_time'].strftime('%Y-%m-%d') if session['start_time'] else 'Unknown'
            duration = "?"
            if session['start_time'] and session['end_time']:
                delta = session['end_time'] - session['start_time']
                hours = delta.total_seconds() / 3600
                if hours < 1:
                    duration = f"{int(hours * 60)}m"
                else:
                    duration = f"{hours:.1f}h"

            tokens = session['input_tokens'] + session['output_tokens']
            model_name = model.split('-')[1].title() if '-' in model else model

            report += f"| {date} | {duration} | {tokens:,} | ${cost['total']:.2f} | {carbon:.1f}g | {model_name} |\n"

    report += f"""
---

## 💰 Cost Breakdown by Model

"""

    for model, tokens in costs_by_model.items():
        cost, carbon = calculate_costs(tokens['input'], tokens['output'], model,
                                       tokens['cache_creation'], tokens['cache_read'])
        model_name = model.split('-')[1].title() if '-' in model else model
        sessions_count = sum(1 for s in sessions if (s['model'] or 'claude-sonnet-4-5-20250929') == model)

        report += f"""**{model_name}**
- Sessions: {sessions_count}
- Input: {tokens['input']:,} tokens (${cost['input']:.2f})
- Output: {tokens['output']:,} tokens (${cost['output']:.2f})
- Cache Create: {tokens['cache_creation']:,} tokens (${cost['cache_creation']:.2f})
- Cache Read: {tokens['cache_read']:,} tokens (${cost['cache_read']:.2f})
- Total: ${cost['total']:.2f} / {carbon:.2f}g CO₂e

"""

    report += f"""---

## 🌱 Environmental Impact

**Total Carbon Footprint:** {total_carbon:.2f}g CO₂e

**Context:**
- Equivalent to {total_carbon / 0.411:.1f} seconds of gasoline car driving
- Equivalent to {total_carbon / 184:.4f} kWh of electricity (US grid average)
- Equivalent to {total_carbon / 21:.2f} smartphone charges

**Carbon Intensity by Model:**
- Haiku: ~0.0028g CO₂e per 1K tokens (most efficient)
- Sonnet: ~0.0105g CO₂e per 1K tokens
- Opus: ~0.0525g CO₂e per 1K tokens (most capable, highest impact)

---

## 💡 Optimization Tips

**To reduce token usage:**
1. Use Haiku for simple tasks (5-10x cheaper than Sonnet)
2. Clear context when switching topics (`/clear`)
3. Use code tools (Python/Bash) instead of token-heavy processing
4. Compress or summarize long documents before reading
5. Use specific file ranges when reading large files

**Sustainability goal:** <$50/month, <5,000g CO₂e/month (current: ${total_cost:.2f}/month, {total_carbon:.1f}g)

---

**Related:** [[MEMORY]] | [[ACTIVE-TASKS]] | [[RECURRING-TASKS]]

**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"Report saved to: {output_path}")

    return report

if __name__ == '__main__':
    print("Scanning Claude Code sessions...")
    sessions = scan_all_sessions()
    print(f"Found {len(sessions)} sessions")

    output_path = Path.home() / 'Documents' / 'Obsidian' / 'RESOURCE-TRACKER.md'
    report = generate_report(sessions, output_path)

    print(f"\n✅ Resource report generated!")
    print(f"📊 Lifetime totals:")

    total_input = sum(s['input_tokens'] for s in sessions)
    total_output = sum(s['output_tokens'] for s in sessions)
    total_cache_create = sum(s.get('cache_creation_tokens', 0) for s in sessions)
    total_cache_read = sum(s.get('cache_read_tokens', 0) for s in sessions)

    costs_by_model = defaultdict(lambda: {'input': 0, 'output': 0,
                                          'cache_creation': 0, 'cache_read': 0})
    for session in sessions:
        model = session['model'] or 'claude-sonnet-4-5-20250929'
        costs_by_model[model]['input'] += session['input_tokens']
        costs_by_model[model]['output'] += session['output_tokens']
        costs_by_model[model]['cache_creation'] += session.get('cache_creation_tokens', 0)
        costs_by_model[model]['cache_read'] += session.get('cache_read_tokens', 0)

    total_cost = 0
    total_carbon = 0
    for model, tokens in costs_by_model.items():
        cost, carbon = calculate_costs(tokens['input'], tokens['output'], model,
                                       tokens['cache_creation'], tokens['cache_read'])
        total_cost += cost['total']
        total_carbon += carbon

    all_tokens = total_input + total_output + total_cache_create + total_cache_read
    print(f"   Tokens: {all_tokens:,} (input: {total_input:,}, output: {total_output:,}, cache: {total_cache_create + total_cache_read:,})")
    print(f"   Cost: ${total_cost:.2f}")
    print(f"   Carbon: {total_carbon:.2f}g CO₂e")
