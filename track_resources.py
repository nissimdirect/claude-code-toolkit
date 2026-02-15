#!/usr/bin/env python3
"""
Resource Tracker v2 for Claude Code — PopChaos Labs
Three-layer metric system (Lenny-informed):
  1. Budget Layer — subscription limits, 5-hour window, weekly caps, alerts
  2. Value Layer — API-equivalent ROI on $200/month subscription
  3. Environmental Layer — energy + carbon estimates with sourced constants

Constants are research-backed with citations. See SOURCES at bottom.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

SUBSCRIPTION = {
    'plan': 'Max 20x',
    'monthly_cost': 200.00,
    # 5-hour rolling window limits (community-measured, not official)
    # Source: Portkey, TrueFoundry, GitHub issues #9424, #3873, GitHub Gist eonist
    # Max 20x advertises ~900 messages/5h. At ~600 tokens/msg average = ~540K tokens.
    # Previous 220K was Pro-tier estimate, far too low for Max 20x.
    # Conservative estimate: 500K tokens (may be higher in practice).
    'five_hour_token_budget': 500_000,
    # Weekly limits (approximate, Anthropic doesn't publish exact numbers)
    'weekly_opus_hours': 40,
    'weekly_sonnet_hours': 480,
    # Shared across claude.ai + Claude Code + Claude Desktop
    'shared_pool': True,
}

# API pricing for calculating "value received" (what you'd pay without subscription)
API_PRICING = {
    'claude-opus-4-6': {
        'input': 15.00 / 1_000_000,
        'output': 75.00 / 1_000_000,
        'cache_create_multiplier': 1.25,  # 1.25x input price
        'cache_read_multiplier': 0.10,    # 0.1x input price
    },
    'claude-sonnet-4-5-20250929': {
        'input': 3.00 / 1_000_000,
        'output': 15.00 / 1_000_000,
        'cache_create_multiplier': 1.25,
        'cache_read_multiplier': 0.10,
    },
    'claude-haiku-4-5-20251001': {
        'input': 0.80 / 1_000_000,
        'output': 4.00 / 1_000_000,
        'cache_create_multiplier': 1.25,
        'cache_read_multiplier': 0.10,
    },
}

# ============================================================================
# ENVIRONMENTAL CONSTANTS — ALL SOURCED
# ============================================================================
# Every number here has a citation. Confidence levels noted.

ENERGY = {
    # Watt-hours per query by model class — FOR CLAUDE CODE USAGE
    #
    # Base research values (standard short/chat query):
    #   Opus-class: ~1.0 Wh, Sonnet-class: ~0.4 Wh, Haiku-class: ~0.1 Wh
    #   Source: "How Hungry is AI?" (arXiv:2505.09598, May 2025)
    #   Source: Epoch AI (Feb 2025), Google (arXiv:2508.15734, Aug 2025)
    #
    # Claude Code adjustment: Code queries are heavier than chat queries due to:
    #   - Large system prompts / context windows
    #   - Tool use (file reads, code execution per round-trip)
    #   - Extended thinking
    # Research shows medium queries use ~3x base, long queries ~6x base.
    # We use ~2x base as a weighted estimate for typical Code usage.
    #
    # Confidence: MEDIUM — cross-referenced across 3+ studies, but no
    # Anthropic-published data exists. True values could be 0.5-3x these.
    'wh_per_query': {
        'opus':   2.0,    # Base 1.0 * ~2x Code adjustment. Range: 0.8-6.0
        'sonnet': 0.8,    # Base 0.4 * ~2x Code adjustment. Range: 0.3-2.5
        'haiku':  0.2,    # Base 0.1 * ~2x Code adjustment. Range: 0.05-0.5
    },
}

CARBON = {
    # Grid carbon intensity — grams CO2e per kWh
    # Source: EPA eGRID 2023 (most recent published)
    # Source: Cloud Carbon Footprint (CCF) — AWS region emission factors
    # Source: Google Environmental Report 2024
    # Confidence: HIGH — government/corporate published data
    'grid_intensity_g_per_kwh': {
        'us_average':    380.0,   # EPA eGRID 2023 US average
        'us_virginia':   379.0,   # CCF: AWS us-east-1 (PJM/SERC grid, location-based)
        'us_oregon':      78.0,   # AWS us-west-2 (very clean hydro)
        'gcp_us':        210.0,   # Google Cloud US average (higher renewable mix)
    },
    # Which grid to use for Anthropic (they use AWS + GCP)
    # Confidence: MEDIUM — Anthropic hasn't disclosed exact DC locations
    'assumed_grid': 'us_virginia',  # Conservative assumption (AWS us-east-1)

    # Power Usage Effectiveness (PUE) — total facility energy / IT equipment energy
    # Source: Cloud Carbon Footprint (CCF) default for AWS: 1.135
    # Source: Uptime Institute Global Survey 2024 (industry avg: 1.58)
    # Source: Google Environmental Report 2024 (Google PUE: 1.10)
    # AWS PUE: CCF uses 1.135 based on AWS sustainability disclosures
    # Confidence: HIGH — CCF is the standard tool used by AWS/Google/Microsoft
    'pue': 1.135,

    # No correction factor needed — energy base values already account for
    # Code-style usage patterns (2x base). Previous 2.0x correction was a
    # band-aid calibrated against FOSS Force 3.5g/query, which itself was
    # based on De Vries (2023) overestimates (~3 Wh/query).
    # With updated constants: 2.0 Wh * 1.135 PUE * 379/1000 = 0.86g per Opus query
    # Range: 0.3-2.6g per query depending on query length
}

# Equivalence factors for human-readable comparisons
# All sourced from EPA or peer-reviewed data
EQUIVALENCES = {
    'g_co2_per_google_search':     0.2,    # Source: Google Environmental Report 2024
    'g_co2_per_smartphone_charge': 12.4,   # Source: EPA — 12.7 kWh/yr / 365 * 356g/kWh
    'g_co2_per_mile_driving':      393.0,  # Source: EPA — 8,887g CO2/gallon, 22.6 mpg avg
    'g_co2_per_hour_netflix':      36.0,   # Source: IEA 2024, ~0.1 kWh/hr * 360g/kWh
    'g_co2_per_cup_coffee':        21.0,   # Source: Journal of Cleaner Production 2023
    'wh_per_google_search':        0.30,   # Source: Google — 0.3 Wh per search
}


def calculate_carbon_from_model_msgs(model_msgs):
    """Calculate Wh and CO2g from per-model-class message counts."""
    grid = CARBON['grid_intensity_g_per_kwh'][CARBON['assumed_grid']]
    pue = CARBON['pue']
    total_wh = 0
    for cls, count in model_msgs.items():
        wh_per_q = ENERGY['wh_per_query'].get(cls, 0.9)
        total_wh += count * wh_per_q * pue
    carbon_g = (total_wh / 1000) * grid
    return round(total_wh, 2), round(carbon_g, 2)


# ============================================================================
# SESSION PARSING (unchanged logic, better structure)
# ============================================================================

def parse_session_file(jsonl_path):
    """Parse a session JSONL file and extract token usage per model."""
    data_out = {
        'input_tokens': 0,
        'output_tokens': 0,
        'cache_creation_tokens': 0,
        'cache_read_tokens': 0,
        'messages': 0,
        'model': None,
        'models_used': defaultdict(lambda: {
            'input': 0, 'output': 0, 'cache_create': 0, 'cache_read': 0, 'msgs': 0
        }),
        'start_time': None,
        'end_time': None,
    }

    try:
        with open(jsonl_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)

                    if 'timestamp' in record:
                        ts = datetime.fromisoformat(
                            record['timestamp'].replace('Z', '+00:00'))
                        if not data_out['start_time']:
                            data_out['start_time'] = ts
                        data_out['end_time'] = ts

                    msg = record.get('message', {})

                    model = msg.get('model')
                    if model and model != '<synthetic>':
                        if not data_out['model']:
                            data_out['model'] = model

                    usage = msg.get('usage', {})
                    inp = usage.get('input_tokens', 0)
                    out = usage.get('output_tokens', 0)
                    cc = usage.get('cache_creation_input_tokens', 0)
                    cr = usage.get('cache_read_input_tokens', 0)

                    if inp > 0 or out > 0 or cc > 0 or cr > 0:
                        data_out['input_tokens'] += inp
                        data_out['output_tokens'] += out
                        data_out['cache_creation_tokens'] += cc
                        data_out['cache_read_tokens'] += cr
                        data_out['messages'] += 1

                        if model and model != '<synthetic>':
                            m = data_out['models_used'][model]
                            m['input'] += inp
                            m['output'] += out
                            m['cache_create'] += cc
                            m['cache_read'] += cr
                            m['msgs'] += 1

                except json.JSONDecodeError:
                    continue

    except Exception as e:
        print(f"Error parsing {jsonl_path}: {e}", file=sys.stderr)

    return data_out


def scan_all_sessions():
    """Scan all Claude Code session files."""
    claude_dir = Path.home() / '.claude' / 'projects'
    if not claude_dir.exists():
        return []

    sessions = []
    for jsonl_file in claude_dir.rglob('*.jsonl'):
        if 'subagents' in str(jsonl_file):
            continue

        usage = parse_session_file(jsonl_file)
        total = (usage['input_tokens'] + usage['output_tokens']
                 + usage['cache_creation_tokens'] + usage['cache_read_tokens'])
        if total > 0:
            usage['session_file'] = str(jsonl_file)
            usage['session_id'] = jsonl_file.stem
            sessions.append(usage)

    return sorted(sessions, key=lambda x: x['start_time'] or datetime.min,
                  reverse=True)


# ============================================================================
# LAYER 1: BUDGET — Subscription limits and alerts
# ============================================================================

def get_model_class(model_id):
    """Map model ID to class (opus/sonnet/haiku)."""
    if not model_id:
        return 'sonnet'
    model_lower = model_id.lower()
    if 'opus' in model_lower:
        return 'opus'
    elif 'haiku' in model_lower:
        return 'haiku'
    return 'sonnet'


def _count_tokens_in_window(jsonl_path, window_start):
    """Count tokens from individual messages after window_start.

    This is more accurate than session-level counting because sessions
    can span across Anthropic's window reset boundary. By checking each
    message's timestamp, we only count tokens that actually fall within
    the current window.

    Returns (tokens, messages, model_msgs_dict).
    """
    tokens = 0
    messages = 0
    model_msgs = {}
    try:
        with open(jsonl_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    ts_str = record.get('timestamp')
                    if not ts_str:
                        continue
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    if ts < window_start:
                        continue
                    msg = record.get('message', {})
                    usage = msg.get('usage', {})
                    inp = usage.get('input_tokens', 0)
                    out = usage.get('output_tokens', 0)
                    if inp > 0 or out > 0:
                        tokens += inp + out
                        messages += 1
                        cls = get_model_class(msg.get('model'))
                        model_msgs[cls] = model_msgs.get(cls, 0) + 1
                except (json.JSONDecodeError, ValueError):
                    continue
    except OSError:
        pass
    return tokens, messages, model_msgs


def calculate_five_hour_window(sessions):
    """Estimate usage within the current 5-hour rolling window.

    IMPORTANT: Only counts input + output tokens, NOT cache tokens.
    Cache tokens (cache_creation, cache_read) are Anthropic's internal
    context caching mechanism. They don't represent conversational usage
    and don't count against subscription rate limits.

    Uses per-message timestamp checking (not session-level) to handle
    sessions that span across Anthropic's window reset boundary.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=5)

    window_tokens = 0
    window_messages = 0
    window_model_msgs = {}

    for s in sessions:
        if not s.get('end_time') or s['end_time'] < window_start:
            continue  # Session ended before window — skip entirely

        if s.get('start_time') and s['start_time'] >= window_start:
            # Session fully within window — use pre-computed totals (fast)
            window_tokens += s['input_tokens'] + s['output_tokens']
            window_messages += s['messages']
            for model_id, model_usage in s['models_used'].items():
                cls = get_model_class(model_id)
                window_model_msgs[cls] = window_model_msgs.get(cls, 0) + model_usage['msgs']
        else:
            # Session spans the window boundary — must check per-message
            session_file = s.get('session_file')
            if session_file:
                tok, msg, mmsg = _count_tokens_in_window(session_file, window_start)
                window_tokens += tok
                window_messages += msg
                for cls, count in mmsg.items():
                    window_model_msgs[cls] = window_model_msgs.get(cls, 0) + count

    budget = SUBSCRIPTION['five_hour_token_budget']
    pct = (window_tokens / budget * 100) if budget > 0 else 0

    wh, carbon_g = calculate_carbon_from_model_msgs(window_model_msgs)

    return {
        'tokens_used': window_tokens,
        'budget': budget,
        'percentage': round(pct, 1),
        'messages': window_messages,
        'remaining': max(budget - window_tokens, 0),
        'carbon_g': carbon_g,
        'wh': wh,
    }


def calculate_since_last_gap(sessions, gap_threshold_minutes=30):
    """Find the last 30+ min inactivity gap and count tokens since then.

    This window matches observed Anthropic rate-limit reset behavior
    better than the official 5-hour rolling window model. When you stop
    for 30+ minutes, the rate limit gate appears to partially reset.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=12)

    all_messages = []
    for s in sessions:
        if not s.get('end_time') or s['end_time'] < cutoff:
            continue
        session_file = s.get('session_file')
        if not session_file:
            continue
        try:
            with open(session_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        ts_str = record.get('timestamp')
                        if not ts_str:
                            continue
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        if ts < cutoff:
                            continue
                        msg = record.get('message', {})
                        usage = msg.get('usage', {})
                        inp = usage.get('input_tokens', 0)
                        out = usage.get('output_tokens', 0)
                        if inp > 0 or out > 0:
                            all_messages.append({
                                'ts': ts,
                                'tokens': inp + out,
                                'model': msg.get('model'),
                            })
                    except (json.JSONDecodeError, ValueError):
                        continue
        except OSError:
            continue

    if not all_messages:
        return {
            'tokens_used': 0, 'messages': 0, 'gap_started': None,
            'carbon_g': 0, 'wh': 0,
        }

    all_messages.sort(key=lambda m: m['ts'])

    gap_threshold = timedelta(minutes=gap_threshold_minutes)
    gap_boundary_idx = 0

    for i in range(len(all_messages) - 1, 0, -1):
        gap = all_messages[i]['ts'] - all_messages[i - 1]['ts']
        if gap >= gap_threshold:
            gap_boundary_idx = i
            break

    window_messages = all_messages[gap_boundary_idx:]
    tokens = sum(m['tokens'] for m in window_messages)
    msgs = len(window_messages)
    gap_started = window_messages[0]['ts'].isoformat() if window_messages else None

    model_msgs = {}
    for m in window_messages:
        cls = get_model_class(m.get('model'))
        model_msgs[cls] = model_msgs.get(cls, 0) + 1

    wh, carbon_g = calculate_carbon_from_model_msgs(model_msgs)

    return {
        'tokens_used': tokens,
        'messages': msgs,
        'gap_started': gap_started,
        'carbon_g': carbon_g,
        'wh': wh,
    }


def calculate_weekly_usage(sessions):
    """Estimate weekly usage by model class."""
    now = datetime.now(timezone.utc)
    # Weekly reset is rolling 7 days (Anthropic doesn't publish exact reset day)
    week_start = now - timedelta(days=7)

    opus_messages = 0
    sonnet_messages = 0
    opus_tokens = 0
    sonnet_tokens = 0

    for s in sessions:
        if s['start_time'] and s['start_time'] >= week_start:
            for model_id, model_usage in s['models_used'].items():
                cls = get_model_class(model_id)
                # Only count conversational tokens (not cache)
                total_tok = model_usage['input'] + model_usage['output']
                if cls == 'opus':
                    opus_tokens += total_tok
                    opus_messages += model_usage['msgs']
                else:
                    sonnet_tokens += total_tok
                    sonnet_messages += model_usage['msgs']

    return {
        'opus_tokens': opus_tokens,
        'opus_messages': opus_messages,
        'sonnet_tokens': sonnet_tokens,
        'sonnet_messages': sonnet_messages,
    }


def generate_alerts(five_hour, weekly):
    """Generate alert messages at 10% threshold intervals."""
    alerts = []
    pct = five_hour['percentage']

    # Alert at every 10% threshold
    thresholds = [50, 60, 70, 80, 90, 95, 100]
    for t in thresholds:
        if pct >= t:
            if t == 100:
                alerts.append(f"LIMIT REACHED: 5-hour window at {pct:.0f}%. "
                              "New prompts may be blocked until window resets.")
            elif t >= 90:
                alerts.append(f"CRITICAL: 5-hour window at {pct:.0f}%. "
                              f"~{five_hour['remaining']:,} tokens remaining. "
                              "Wind down or switch to Sonnet.")
            elif t >= 80:
                alerts.append(f"WARNING: 5-hour window at {pct:.0f}%. "
                              "Consider saving remaining budget for critical work.")
            elif t >= 50:
                alerts.append(f"INFO: 5-hour window at {pct:.0f}% "
                              f"({five_hour['remaining']:,} tokens remaining).")
            break  # Only show highest applicable alert

    return alerts


# ============================================================================
# LAYER 2: VALUE — API-equivalent ROI
# ============================================================================

def calculate_api_equivalent(sessions):
    """Calculate what this usage would cost at API rates."""
    total_api_cost = 0

    for s in sessions:
        for model_id, model_usage in s['models_used'].items():
            pricing = API_PRICING.get(model_id)
            if not pricing:
                # Try to match by model class
                cls = get_model_class(model_id)
                for pid, p in API_PRICING.items():
                    if cls in pid.lower():
                        pricing = p
                        break
                if not pricing:
                    pricing = API_PRICING['claude-sonnet-4-5-20250929']

            inp_cost = model_usage['input'] * pricing['input']
            out_cost = model_usage['output'] * pricing['output']
            cc_cost = (model_usage['cache_create'] * pricing['input']
                       * pricing['cache_create_multiplier'])
            cr_cost = (model_usage['cache_read'] * pricing['input']
                       * pricing['cache_read_multiplier'])
            total_api_cost += inp_cost + out_cost + cc_cost + cr_cost

    return total_api_cost


def calculate_monthly_api_equivalent(sessions):
    """Calculate API-equivalent for current calendar month only."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    month_sessions = [s for s in sessions
                      if s['start_time'] and s['start_time'] >= month_start]
    return calculate_api_equivalent(month_sessions), len(month_sessions)


# ============================================================================
# LAYER 3: ENVIRONMENTAL — Energy and carbon with sourced estimates
# ============================================================================

def estimate_energy_and_carbon(sessions):
    """Estimate energy (Wh) and carbon (gCO2e) from token usage.

    Uses message count as primary query estimator (more accurate than
    dividing total tokens). Each API round-trip = 1 query for energy purposes.
    Cache tokens are excluded — they represent server-side caching, not
    additional compute (cache reads are specifically cheaper/faster).
    """
    total_wh = 0
    total_carbon_g = 0

    grid = CARBON['grid_intensity_g_per_kwh'][CARBON['assumed_grid']]
    pue = CARBON['pue']

    per_model = {}

    for s in sessions:
        for model_id, model_usage in s['models_used'].items():
            cls = get_model_class(model_id)
            # Only count conversational tokens for display
            conv_tokens = model_usage['input'] + model_usage['output']

            wh_per_q = ENERGY['wh_per_query'].get(cls, 0.90)

            # Use actual message count as query count (most accurate)
            estimated_queries = model_usage['msgs']

            # Energy: queries * Wh/query * PUE
            session_wh = estimated_queries * wh_per_q * pue

            # Carbon: energy (kWh) * grid intensity (g/kWh)
            session_carbon = (session_wh / 1000) * grid

            total_wh += session_wh
            total_carbon_g += session_carbon

            if cls not in per_model:
                per_model[cls] = {'wh': 0, 'carbon_g': 0, 'tokens': 0,
                                  'queries': 0}
            per_model[cls]['wh'] += session_wh
            per_model[cls]['carbon_g'] += session_carbon
            per_model[cls]['tokens'] += conv_tokens
            per_model[cls]['queries'] += estimated_queries

    return {
        'total_wh': total_wh,
        'total_carbon_g': total_carbon_g,
        'per_model': per_model,
    }


# ============================================================================
# JSON SIDECAR — Fast-read cache for hooks and dashboard
# ============================================================================

BUDGET_STATE_PATH = Path.home() / '.claude' / '.locks' / '.budget-state.json'


def get_model_recommendation(pct):
    """Return (model_recommendation, alert_level) based on 5-hour window percentage."""
    if pct >= 95:
        return 'wind_down', 'limit'
    elif pct >= 85:
        return 'sonnet', 'critical'
    elif pct >= 70:
        return 'sonnet', 'warning'
    elif pct >= 50:
        return 'opus', 'info'
    else:
        return 'opus', 'ok'


def write_budget_state_json(five_hour, weekly, env, since_gap=None, lifetime=None):
    """Write lightweight JSON sidecar for hooks and dashboard to read.

    Atomic write (temp + rename) to prevent corrupt reads.
    """
    model_rec, alert_level = get_model_recommendation(five_hour['percentage'])

    state = {
        'generated': datetime.now(timezone.utc).isoformat(),
        'five_hour_window': {
            'percentage': round(five_hour['percentage'], 1),
            'tokens_used': five_hour['tokens_used'],
            'budget': five_hour['budget'],
            'remaining': five_hour['remaining'],
            'messages': five_hour['messages'],
            'carbon_g': five_hour.get('carbon_g', 0),
            'wh': five_hour.get('wh', 0),
        },
        'since_last_gap': since_gap or {
            'tokens_used': 0, 'messages': 0, 'gap_started': None,
            'carbon_g': 0, 'wh': 0,
        },
        'weekly': {
            'opus_tokens': weekly['opus_tokens'],
            'opus_messages': weekly['opus_messages'],
            'sonnet_tokens': weekly['sonnet_tokens'],
            'sonnet_messages': weekly['sonnet_messages'],
        },
        'environmental': {
            'total_wh': round(env['total_wh'], 1),
            'total_carbon_g': round(env['total_carbon_g'], 1),
        },
        'lifetime': lifetime or {
            'total_tokens': 0, 'total_messages': 0, 'total_sessions': 0,
            'first_session': None, 'total_carbon_g': 0, 'total_wh': 0,
        },
        'model_recommendation': model_rec,
        'alert_level': alert_level,
    }

    try:
        BUDGET_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=BUDGET_STATE_PATH.parent, suffix='.json')
        with os.fdopen(fd, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, BUDGET_STATE_PATH)
    except OSError as e:
        print(f"Warning: Could not write budget state JSON: {e}", file=sys.stderr)
        try:
            os.unlink(tmp_path)
        except (OSError, UnboundLocalError):
            pass


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_report(sessions, output_path=None):
    """Generate the three-layer resource report."""
    if not sessions:
        report = "# Resource Tracker\n\nNo sessions found.\n"
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
        return report

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Compute all metrics
    five_hour = calculate_five_hour_window(sessions)
    weekly = calculate_weekly_usage(sessions)
    alerts = generate_alerts(five_hour, weekly)
    api_equiv_total = calculate_api_equivalent(sessions)
    api_equiv_month, month_sessions = calculate_monthly_api_equivalent(sessions)
    env = estimate_energy_and_carbon(sessions)

    # Compute since-last-gap window
    since_gap = calculate_since_last_gap(sessions)

    # Compute lifetime totals
    total_conv_tokens = sum(s['input_tokens'] + s['output_tokens'] for s in sessions)
    total_all_messages = sum(s['messages'] for s in sessions)
    first_session_time = min(
        (s['start_time'] for s in sessions if s['start_time']),
        default=None)
    lifetime = {
        'total_tokens': total_conv_tokens,
        'total_messages': total_all_messages,
        'total_sessions': len(sessions),
        'first_session': first_session_time.isoformat() if first_session_time else None,
        'total_carbon_g': round(env['total_carbon_g'], 1),
        'total_wh': round(env['total_wh'], 1),
    }

    # Write JSON sidecar for hooks and dashboard
    write_budget_state_json(five_hour, weekly, env, since_gap, lifetime)

    total_tokens = sum(s['input_tokens'] + s['output_tokens']
                       + s['cache_creation_tokens'] + s['cache_read_tokens']
                       for s in sessions)
    total_messages = sum(s['messages'] for s in sessions)

    # ROI calculation
    # How many months of subscription have elapsed?
    if sessions and sessions[-1]['start_time']:
        first_session = min(s['start_time'] for s in sessions if s['start_time'])
        months_elapsed = max(
            (datetime.now(timezone.utc) - first_session).days / 30.0, 1.0)
    else:
        months_elapsed = 1.0
    total_subscription_cost = SUBSCRIPTION['monthly_cost'] * months_elapsed
    roi_multiplier = api_equiv_total / max(total_subscription_cost, 1)

    # Progress bar helper
    def progress_bar(pct, width=20):
        filled = int(min(pct, 100) / 100 * width)
        return f"[{'█' * filled}{'░' * (width - filled)}]"

    # ---- Build report ----
    report = f"""# Claude Code Resource Tracker v2

**Generated:** {now_str}
**Plan:** {SUBSCRIPTION['plan']} (${SUBSCRIPTION['monthly_cost']:.0f}/month)
**Sessions:** {len(sessions)} lifetime | {month_sessions} this month

"""

    # ALERTS (top of report, always visible)
    if alerts:
        report += "## Alerts\n\n"
        for a in alerts:
            report += f"- **{a}**\n"
        report += "\n---\n\n"

    # LAYER 1: BUDGET
    report += f"""## Layer 1: Budget

### 5-Hour Rolling Window
{progress_bar(five_hour['percentage'])} **{five_hour['percentage']:.0f}%** used

| Metric | Value |
|--------|-------|
| Tokens used | {five_hour['tokens_used']:,} / {five_hour['budget']:,} |
| Messages | {five_hour['messages']} |
| Remaining | ~{five_hour['remaining']:,} tokens |

*Note: 5-hour window is approximate. Anthropic does not publish exact token budgets.
Limit resets 5 hours after your first message in the window.*

### Weekly Usage (rolling 7 days)

| Model | Tokens | Messages |
|-------|--------|----------|
| Opus | {weekly['opus_tokens']:,} | {weekly['opus_messages']} |
| Sonnet | {weekly['sonnet_tokens']:,} | {weekly['sonnet_messages']} |

*Opus has a separate, stricter weekly cap (~40 hrs). If you hit it, Sonnet still works.*
*All usage shared across claude.ai, Claude Code, and Claude Desktop.*

### Budget Tips
- Switch to Sonnet (`/model sonnet`) for routine tasks — 5x less quota consumed
- Use `/clear` between unrelated tasks to reduce context bloat
- Check claude.ai Settings > Usage for official usage bars

---

## Layer 2: Value (ROI)

| Metric | Value |
|--------|-------|
| **Subscription cost** | ${total_subscription_cost:.2f} ({months_elapsed:.1f} months) |
| **API-equivalent value** | ${api_equiv_total:,.2f} |
| **ROI multiplier** | **{roi_multiplier:.1f}x** (you received ${roi_multiplier:.1f} of value per $1 spent) |
| **This month API-equivalent** | ${api_equiv_month:,.2f} |

"""

    if roi_multiplier >= 5:
        report += "*Excellent value — you're getting significant leverage from the subscription.*\n\n"
    elif roi_multiplier >= 2:
        report += "*Good value — subscription is working in your favor.*\n\n"
    elif roi_multiplier >= 1:
        report += "*Break-even — consider whether API billing would be cheaper.*\n\n"
    else:
        report += "*Below break-even — API billing might be more cost-effective this month.*\n\n"

    # Cost breakdown by model
    report += "### API-Equivalent by Model\n\n"
    report += "| Model | Input Tokens | Output Tokens | Cache Tokens | API Cost |\n"
    report += "|-------|-------------|---------------|--------------|----------|\n"

    model_totals = defaultdict(lambda: {
        'input': 0, 'output': 0, 'cache_create': 0, 'cache_read': 0})
    for s in sessions:
        for model_id, mu in s['models_used'].items():
            model_totals[model_id]['input'] += mu['input']
            model_totals[model_id]['output'] += mu['output']
            model_totals[model_id]['cache_create'] += mu['cache_create']
            model_totals[model_id]['cache_read'] += mu['cache_read']

    for model_id, totals in sorted(model_totals.items()):
        pricing = API_PRICING.get(model_id,
                                  API_PRICING['claude-sonnet-4-5-20250929'])
        cost = (totals['input'] * pricing['input']
                + totals['output'] * pricing['output']
                + totals['cache_create'] * pricing['input']
                  * pricing['cache_create_multiplier']
                + totals['cache_read'] * pricing['input']
                  * pricing['cache_read_multiplier'])
        cls = get_model_class(model_id)
        cache_total = totals['cache_create'] + totals['cache_read']
        report += (f"| {cls.title()} | {totals['input']:,} | {totals['output']:,} "
                   f"| {cache_total:,} | ${cost:,.2f} |\n")

    report += f"""
---

## Layer 3: Environmental Impact

### Energy Consumption

| Metric | Value |
|--------|-------|
| **Total energy** | {env['total_wh']:.1f} Wh ({env['total_wh']/1000:.3f} kWh) |
| **Equivalent Google searches** | {env['total_wh'] / EQUIVALENCES['wh_per_google_search']:,.0f} |

### Carbon Footprint

| Metric | Value |
|--------|-------|
| **Total CO2e** | {env['total_carbon_g']:.1f}g ({env['total_carbon_g']/1000:.3f} kg) |
| **Confidence** | MEDIUM (see methodology below) |

### Equivalences

| Your usage equals... | Amount |
|---------------------|--------|
| Google searches | {env['total_carbon_g'] / EQUIVALENCES['g_co2_per_google_search']:,.0f} |
| Smartphone charges | {env['total_carbon_g'] / EQUIVALENCES['g_co2_per_smartphone_charge']:,.1f} |
| Miles driven | {env['total_carbon_g'] / EQUIVALENCES['g_co2_per_mile_driving']:,.2f} |
| Hours of Netflix | {env['total_carbon_g'] / EQUIVALENCES['g_co2_per_hour_netflix']:,.1f} |
| Cups of coffee (lifecycle) | {env['total_carbon_g'] / EQUIVALENCES['g_co2_per_cup_coffee']:,.1f} |

### Per-Model Breakdown

| Model | Est. Queries | Energy (Wh) | Carbon (g CO2e) |
|-------|-------------|-------------|-----------------|
"""

    for cls in ['opus', 'sonnet', 'haiku']:
        if cls in env['per_model']:
            m = env['per_model'][cls]
            report += (f"| {cls.title()} | {m['queries']:,.0f} | "
                       f"{m['wh']:.1f} | {m['carbon_g']:.1f} |\n")

    report += f"""
### Methodology & Sources

**How we calculate energy:**
```
Energy (Wh) = message_count * Wh_per_query * PUE
message_count = actual API round-trips (from session JSONL)
```

**How we calculate carbon:**
```
Carbon (g) = Energy (kWh) * grid_intensity (g/kWh)
```

**Constants used:**

| Constant | Value | Source | Confidence |
|----------|-------|--------|------------|
| Opus Wh/query | {ENERGY['wh_per_query']['opus']} Wh | arXiv:2505.09598 (1.0 base * 2x Code adj.) | MEDIUM |
| Sonnet Wh/query | {ENERGY['wh_per_query']['sonnet']} Wh | Epoch AI + Google (0.4 base * 2x Code adj.) | MEDIUM |
| Haiku Wh/query | {ENERGY['wh_per_query']['haiku']} Wh | Proportional to small models (0.1 * 2x) | LOW-MEDIUM |
| Grid intensity | {CARBON['grid_intensity_g_per_kwh'][CARBON['assumed_grid']]}g CO2e/kWh | Cloud Carbon Footprint (AWS us-east-1) | HIGH |
| PUE | {CARBON['pue']} | Cloud Carbon Footprint (AWS default) | HIGH |

**Validation:**
- Our Opus estimate: {ENERGY['wh_per_query']['opus']} Wh * {CARBON['pue']} PUE * {CARBON['grid_intensity_g_per_kwh'][CARBON['assumed_grid']]}/1000 kg/kWh = {ENERGY['wh_per_query']['opus'] * CARBON['pue'] * CARBON['grid_intensity_g_per_kwh'][CARBON['assumed_grid']] / 1000:.2f}g per query
- Research range: 0.3-2.6g per Claude query depending on length
- FOSS Force (Apr 2025) reported ~3.5g per query (likely based on older De Vries 2023 estimates)
- Our estimate is conservative for typical queries, may undercount for extended-thinking sessions

**What Anthropic has NOT published:**
- Per-token or per-query energy consumption
- Data center locations or grid mix
- Scope 1/2/3 emissions
- PUE for their specific infrastructure

**Full source list:**
1. "How Hungry is AI?" — arXiv:2505.09598 (May 2025)
2. Epoch AI — "The rising costs of training frontier AI models" (Feb 2025)
3. Google — arXiv:2508.15734, energy-efficient AI inference (Aug 2025)
4. Cloud Carbon Footprint (CCF) — AWS emission factors + PUE defaults
5. EPA eGRID — US regional grid emission factors (2023)
6. Hannah Ritchie — "What's the carbon footprint of using ChatGPT?" (Aug 2025)
7. FOSS Force — "What's Your Chatbot's Carbon Footprint?" (Apr 2025)
8. IEA — World Energy Outlook AI chapter (2024)
9. De Vries (2023) — "The growing energy footprint of AI" (Joule)
10. LiveScience — "Advanced AI models generate up to 50x more CO2" (2025)

---

## Session History (Last 20)

| Date | Duration | Tokens | API Value | Energy | Carbon | Model |
|------|----------|--------|-----------|--------|--------|-------|
"""

    for session in sessions[:20]:
        model = session['model'] or 'claude-sonnet-4-5-20250929'
        cls = get_model_class(model)

        # API equivalent for this session
        session_api = calculate_api_equivalent([session])

        # Energy for this session
        session_env = estimate_energy_and_carbon([session])

        date = (session['start_time'].strftime('%Y-%m-%d')
                if session['start_time'] else 'Unknown')
        duration = "?"
        if session['start_time'] and session['end_time']:
            delta = session['end_time'] - session['start_time']
            hours = delta.total_seconds() / 3600
            duration = f"{int(hours * 60)}m" if hours < 1 else f"{hours:.1f}h"

        # Only conversational tokens (input + output), not cache
        tokens = session['input_tokens'] + session['output_tokens']

        report += (f"| {date} | {duration} | {tokens:,} | "
                   f"${session_api:,.2f} | "
                   f"{session_env['total_wh']:.1f} Wh | "
                   f"{session_env['total_carbon_g']:.1f}g | "
                   f"{cls.title()} |\n")

    report += f"""
---

**Related:** [[MEMORY]] | [[ACTIVE-TASKS]] | [[RECURRING-TASKS]]
**Last Updated:** {now_str}
"""

    if output_path:
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"Report saved to: {output_path}")

    return report


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main():
    print("Scanning Claude Code sessions...")
    sessions = scan_all_sessions()
    print(f"Found {len(sessions)} sessions")

    output_path = Path.home() / 'Documents' / 'Obsidian' / 'process' / 'RESOURCE-TRACKER.md'
    report = generate_report(sessions, output_path)

    # Print summary to terminal
    five_hour = calculate_five_hour_window(sessions)
    api_equiv = calculate_api_equivalent(sessions)
    env = estimate_energy_and_carbon(sessions)
    alerts = generate_alerts(five_hour, calculate_weekly_usage(sessions))

    print(f"\n{'=' * 50}")
    print(f"  RESOURCE TRACKER v2 — PopChaos Labs")
    print(f"{'=' * 50}")

    # Always show alerts first
    if alerts:
        print()
        for a in alerts:
            print(f"  ⚠  {a}")

    print(f"\n  Budget:  {five_hour['percentage']:.0f}% of 5-hour window "
          f"({five_hour['tokens_used']:,} / {five_hour['budget']:,} tokens)")
    print(f"  Value:   ${api_equiv:,.2f} API-equivalent")
    print(f"  Energy:  {env['total_wh']:.1f} Wh "
          f"({env['total_carbon_g']:.1f}g CO₂e)")
    print(f"{'=' * 50}")
    print(f"  Full report: {output_path}")


if __name__ == '__main__':
    main()
