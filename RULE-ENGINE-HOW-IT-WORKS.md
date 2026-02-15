# Rule Engine v3 — How It Works

## The Problem
Claude sometimes forgets behavioral rules. Without enforcement, the same mistakes recur across sessions.

## The Solution: A Self-Regulating Flywheel
20 rules with adaptive spikes, decay, dormancy, and immune reactivation — modeled after biological immune systems.

## The Loop

```
violation detected
       |
       v
  SPIKE (+0.15)         Rule becomes more visible
       |
       v
  INJECTION              Top 3 rules injected into every prompt
       |
       v
  CORRECTION             Claude follows the reminder
       |
       v
  DECAY (-0.01/day)     Rule fades back to baseline
       |
       v
  DORMANCY (60+ days)   Unused rule goes to sleep
       |
       v
  IMMUNE REACTIVATION   Violation wakes dormant rule with extra spike (+0.20)
       |
       v
  (back to top)
```

## How Rules Score

Each rule scores on 4 axes:

| Axis | Range | What it means |
|------|-------|---------------|
| Domain match | 0.3-0.4 | Does the rule apply to this task? (code, audio, git, etc.) |
| Consequence | 0.1-0.3 | How critical is this rule? (value > principle > practice) |
| Tool trigger | 0.0-0.2 | Is the user about to use a relevant tool? (edit, bash, write) |
| Adaptive spike | 0.0-0.15 | Was this rule recently violated? |

**Threshold = 0.5** — only rules scoring above this get activated.
**Budget = 5** — at most 5 rules activate per prompt.
**Injection limit = 3** — at most 3 reminders shown to Claude.

## What You See

Every injected rule includes:
```
[Rule R4|P4 | code+edit+spiked] Read the file before editing — never Edit without prior Read
```

- `R4` = rule ID
- `P4` = principle ID (maps to behavioral-principles.md)
- `code+edit+spiked` = WHY this rule was selected (domain match + tool match + spike active)

## Key Mechanics

**Spike sources** (how violations are detected):
- `hook` (0.15) — pre-execution hook catches a violation
- `user` (0.15) — user corrects Claude directly
- `self_check` (0.08) — Claude catches its own mistake
- `audit` (0.06) — session-close review finds a violation

**Decay**: -0.01 per day. A max spike (0.15) takes 15 days to fully decay.

**Dormancy**: Rules unused for 60+ days go dormant (excluded from scoring). Pinned rules (R1, R4, R5, R9) never go dormant.

**Immune reactivation**: If a dormant rule is violated, it wakes up with a spike of 0.20 (higher than normal max of 0.15), ensuring it stays visible longer.

**Co-activation tracking**: Rules that always fire together are merge candidates (>90% co-activation over 10+ observations). This prevents rule bloat.

## Files

| File | Purpose |
|------|---------|
| `~/Development/tools/rule_engine.py` | Production engine (called by hook) |
| `~/Development/tools/rules.yaml` | 20 rules + classification keywords |
| `~/.claude/.locks/rule-engine-state.json` | Persistent state (spikes, counts, dormancy) |
| `~/.claude/hooks/learning_hook.py` | Hook that calls engine on every prompt |
| `~/Development/tools/rule_engine_flywheel_tests.py` | 121 tests across 15 phases |
| `~/Development/tools/rule_engine_test_suite.py` | 243 correctness tests across 9 phases |

## CLI

```bash
python3 ~/Development/tools/rule_engine.py test "edit some python code"
python3 ~/Development/tools/rule_engine.py lifecycle
python3 ~/Development/tools/rule_engine.py advance
python3 ~/Development/tools/rule_engine.py validate
python3 ~/Development/tools/rule_engine.py violation R4 hook
```

## Monitoring

- `/today` shows rule engine health in System Health section
- `/session-close` runs lifecycle report + advance_day
- Corrections count tracked as north star metric
