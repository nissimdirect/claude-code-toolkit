# Claude Cost Monitoring - Implementation Guide

**Date:** 2026-02-09
**Status:** Ready to implement
**Priority:** Medium (we're already under budget, this is optimization)

---

## Current State

**What We Have:**
- ✓ Resource tracker (`~/Development/tools/track_resources.py`)
- ✓ Budget automation hooks (`~/.claude/hooks/budget_check.py`)
- ✓ Context DB (`~/Development/tools/context_db.py`)
- ✓ Monthly budget target: <$50/month
- ✓ Current plan: $100/month Max (5x usage)

**What We're Missing:**
- Local JSONL file parsing (can't compare API vs monthly cost)
- Real-time quota monitoring (don't know how close to 5-hour limit)
- Historical cost trends (no month-over-month analysis)

---

## Implementation Options

### Option 1: ccusage (RECOMMENDED)

**Why:**
- Lightweight CLI tool
- Parses local JSONL files directly
- Daily/monthly/session views built-in
- Maintained by active developer

**Installation:**
```bash
# macOS via Homebrew
brew install ryoppippi/tap/ccusage

# OR via Cargo
cargo install ccusage

# OR via npm
npm install -g ccusage
```

**Usage:**
```bash
# View monthly usage
ccusage --view monthly

# View session usage
ccusage --view session

# Compare to plan
ccusage --plan max-5
```

**Integration:**
```bash
# Add to daily review (~/Documents/Obsidian/Templates/START-OF-SESSION.md)
echo "Run: ccusage --view monthly" >> ~/Documents/Obsidian/Templates/START-OF-SESSION.md

# Add to weekly review
echo "Review: ccusage --view monthly --plan max-5" >> ~/Documents/Obsidian/process/WEEKLY-REVIEW-TEMPLATE.md
```

**Pros:**
- No code to write
- Maintained by someone else
- Rich output formatting

**Cons:**
- External dependency
- Less control over data format
- May not integrate with existing tools

---

### Option 2: Custom Script (MAXIMUM CONTROL)

**Why:**
- Full control over data processing
- Can integrate with existing resource tracker
- No external dependencies
- Learn JSONL format for future tools

**Implementation:**

```python
#!/usr/bin/env python3
"""
Parse Claude Code local JSONL files and calculate costs.
Location: ~/Development/tools/parse_claude_local_costs.py
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Current API pricing (update when changed)
PRICING = {
    'opus-4.6': {'input': 5.0 / 1_000_000, 'output': 25.0 / 1_000_000},
    'sonnet-4.5': {'input': 3.0 / 1_000_000, 'output': 15.0 / 1_000_000},
    'haiku-4.5': {'input': 1.0 / 1_000_000, 'output': 5.0 / 1_000_000},
}

def parse_jsonl(file_path):
    """Parse a JSONL file and return list of messages."""
    messages = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # Skip malformed lines
    return messages

def calculate_message_cost(message):
    """Calculate cost for a single message."""
    model = message.get('model', 'sonnet-4.5')  # Default to Sonnet
    input_tokens = message.get('input_tokens', 0)
    output_tokens = message.get('output_tokens', 0)

    # Normalize model name
    if 'opus' in model.lower():
        pricing = PRICING['opus-4.6']
    elif 'haiku' in model.lower():
        pricing = PRICING['haiku-4.5']
    else:
        pricing = PRICING['sonnet-4.5']

    input_cost = input_tokens * pricing['input']
    output_cost = output_tokens * pricing['output']

    return input_cost + output_cost, input_tokens, output_tokens

def analyze_session(file_path):
    """Analyze a single session file."""
    messages = parse_jsonl(file_path)

    total_cost = 0
    total_input = 0
    total_output = 0

    for message in messages:
        cost, input_tok, output_tok = calculate_message_cost(message)
        total_cost += cost
        total_input += input_tok
        total_output += output_tok

    return {
        'file': file_path.name,
        'message_count': len(messages),
        'total_cost': total_cost,
        'input_tokens': total_input,
        'output_tokens': total_output,
        'total_tokens': total_input + total_output,
    }

def analyze_all_sessions(days_back=30):
    """Analyze all sessions in the past N days."""
    projects_dir = Path.home() / '.claude' / 'projects'

    if not projects_dir.exists():
        print(f"Error: {projects_dir} does not exist")
        return

    # Find all JSONL files
    files = list(projects_dir.glob('*.jsonl'))

    if not files:
        print(f"No JSONL files found in {projects_dir}")
        return

    print(f"Found {len(files)} session files\n")

    # Filter by date if possible (check file modification time)
    cutoff = datetime.now() - timedelta(days=days_back)
    recent_files = [f for f in files if datetime.fromtimestamp(f.stat().st_mtime) > cutoff]

    print(f"Analyzing {len(recent_files)} sessions from past {days_back} days\n")

    # Analyze each session
    sessions = []
    total_cost = 0
    total_tokens = 0

    for file_path in recent_files:
        session = analyze_session(file_path)
        sessions.append(session)
        total_cost += session['total_cost']
        total_tokens += session['total_tokens']

    # Print summary
    print("=" * 80)
    print(f"CLAUDE CODE COST ANALYSIS - Past {days_back} Days")
    print("=" * 80)
    print()
    print(f"Total Sessions: {len(sessions)}")
    print(f"Total Messages: {sum(s['message_count'] for s in sessions)}")
    print(f"Total Tokens: {total_tokens:,}")
    print(f"Total Cost (API equivalent): ${total_cost:.2f}")
    print()

    # Compare to plans
    monthly_cost = total_cost * (30 / days_back)  # Extrapolate to full month

    print(f"Projected Monthly Cost: ${monthly_cost:.2f}")
    print()
    print("Plan Comparison:")
    print(f"  Pro ($20/month):       {'✓ CHEAPER' if monthly_cost < 20 else '✗ MORE EXPENSIVE'}")
    print(f"  Max-5 ($100/month):    {'✓ CHEAPER' if monthly_cost < 100 else '✗ MORE EXPENSIVE'}")
    print(f"  Max-20 ($200/month):   {'✓ CHEAPER' if monthly_cost < 200 else '✗ MORE EXPENSIVE'}")
    print()

    if monthly_cost < 100:
        savings = 100 - monthly_cost
        print(f"💰 You could save ${savings:.2f}/month by switching to API pricing")
    elif monthly_cost > 100:
        overage = monthly_cost - 100
        print(f"⚠️  You would pay ${overage:.2f}/month MORE on API pricing")
    else:
        print("📊 Your usage exactly matches $100/month plan cost")

    print()
    print("=" * 80)

    # Top 10 most expensive sessions
    print()
    print("Top 10 Most Expensive Sessions:")
    print()
    sorted_sessions = sorted(sessions, key=lambda s: s['total_cost'], reverse=True)
    for i, session in enumerate(sorted_sessions[:10], 1):
        print(f"{i:2d}. {session['file'][:40]:40s} ${session['total_cost']:6.2f}  ({session['message_count']:3d} messages, {session['total_tokens']:,} tokens)")
    print()

if __name__ == '__main__':
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    analyze_all_sessions(days_back=days)
```

**Usage:**
```bash
# Analyze past 30 days (default)
python ~/Development/tools/parse_claude_local_costs.py

# Analyze past 7 days
python ~/Development/tools/parse_claude_local_costs.py 7

# Analyze entire history
python ~/Development/tools/parse_claude_local_costs.py 365
```

**Pros:**
- Full control
- Can extend with custom features
- Integrates with existing tools
- No external dependencies

**Cons:**
- Need to maintain code
- More initial work
- May miss edge cases

---

### Option 3: Claude Code Usage Monitor (OVERKILL)

**Why:**
- Real-time monitoring with Rich UI
- ML predictions for quota limits
- Most feature-rich

**Installation:**
```bash
pipx install git+https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor
```

**Pros:**
- Beautiful terminal UI
- Predictive analytics
- Active development

**Cons:**
- Heavier dependency
- May be overkill for our needs
- More complexity

---

## Recommended Implementation Plan

### Phase 1: Immediate (This Week)

**Step 1: Try ccusage** (30 minutes)
```bash
brew install ryoppippi/tap/ccusage
ccusage --view monthly
ccusage --plan max-5
```

**If it works:**
- Add to daily workflow
- Document in CLAUDE.md
- Done

**If it doesn't work:**
- Proceed to Step 2

**Step 2: Build Custom Script** (2 hours)
```bash
# Copy implementation code above
vim ~/Development/tools/parse_claude_local_costs.py
chmod +x ~/Development/tools/parse_claude_local_costs.py
python ~/Development/tools/parse_claude_local_costs.py
```

**Step 3: Validate Output** (30 minutes)
- Compare to resource tracker
- Check against known sessions
- Verify cost calculations

### Phase 2: Integration (Next Week)

**Add to RECURRING-TASKS.md:**
```markdown
## Monthly (1st of month)
- [ ] Run cost analysis: `python ~/Development/tools/parse_claude_local_costs.py 30`
- [ ] Compare to $100/month plan
- [ ] Decision: keep plan or switch to API
- [ ] Update budget forecast
```

**Add to START-OF-SESSION.md:**
```markdown
## Cost Check (Weekly)
- Run: `ccusage --view session` OR `python ~/Development/tools/parse_claude_local_costs.py 7`
- Check: Are we on track for <$50/month budget?
```

**Add to WEEKLY-REVIEW-TEMPLATE.md:**
```markdown
## Cost Review
- [ ] Weekly usage: `ccusage --view weekly` (or custom script)
- [ ] Projected monthly: extrapolate from 7-day average
- [ ] On budget? <$50/month target
```

### Phase 3: Optimization (Ongoing)

**If consistently <$70/month:**
- Consider switching to API pricing
- Save $30-40/month
- Need to monitor closely

**If consistently $70-100/month:**
- Keep $100/month plan
- Good value for predictability

**If consistently >$100/month:**
- We're power users
- Optimize token usage:
  - Use /compact more aggressively
  - Check context_db before reads
  - Limit MCP tool usage
  - Shorter sessions

---

## Testing Checklist

Before deploying, verify:

- [ ] ~/.claude/projects/ directory exists
- [ ] JSONL files are readable
- [ ] Sample file has `input_tokens` and `output_tokens` fields
- [ ] Cost calculations match expected API pricing
- [ ] Output is readable and actionable
- [ ] Script handles edge cases (empty files, malformed JSON)
- [ ] Projections are reasonable (not wildly off)

---

## Rollback Plan

If anything breaks:

1. Stop using new tools
2. Revert to existing resource tracker
3. Document what went wrong
4. Fix or abandon

Our existing system works fine. This is optimization, not critical infrastructure.

---

## Success Metrics

**Week 1:**
- [ ] Tool installed and running
- [ ] Output matches expectations
- [ ] Cost comparison clear

**Week 2:**
- [ ] Integrated into daily workflow
- [ ] Historical data analyzed
- [ ] Decision made: keep plan or switch

**Month 1:**
- [ ] Monthly review completed
- [ ] Cost optimization strategy validated
- [ ] Budget tracking accurate

**Month 3:**
- [ ] Pattern established
- [ ] Fully automated
- [ ] No surprises

---

## Notes

**Why this matters:**
- We're on $100/month plan
- Budget is <$50/month
- If we're using <$70 API-equivalent, we could save $30+/month
- That's $360/year

**Why this doesn't matter:**
- We're already under budget
- Current plan works fine
- Predictable costs are valuable
- Time spent optimizing could be spent building

**Recommended stance:**
- Implement Phase 1 (try ccusage or build script)
- Run monthly analysis
- Make data-driven decision
- Don't overthink it
