# Claude Usage Dashboard - Specification

**Purpose:** Always-on display of system status, eliminating need to ask Claude for updates

---

## Dashboard 1: Background Tasks & System Status

**Display (refreshes every 5s):**

```
┌─ CLAUDE SYSTEM STATUS ────────────────────────────────────┐
│ Session: 83209                    Uptime: 2h 14m           │
│ Responses: 15                     Avg: 6.8 resp/hr         │
└────────────────────────────────────────────────────────────┘

┌─ BACKGROUND SERVICES ─────────────────────────────────────┐
│ ✅ scrape-all          Running    Last: 3h ago             │
│ ✅ resource-tracker    Running    Last: 30s ago            │
└────────────────────────────────────────────────────────────┘

┌─ ACTIVE TASKS ────────────────────────────────────────────┐
│ #37  [████████░░] 80%  Grant site scraping                │
│ #42  [███░░░░░░░] 30%  Don Norman corpus                  │
│ #43  [██░░░░░░░░] 20%  Art critics corpus                 │
└────────────────────────────────────────────────────────────┘

┌─ RECENT SCRAPING ─────────────────────────────────────────┐
│ ✅ Plugin docs        29/30 companies    COMPLETE          │
│ 🔄 Grant sites        7/10 sites         IN PROGRESS       │
└────────────────────────────────────────────────────────────┘
```

**Data sources:**
- `~/.claude/.locks/.resource-tracker.json` (sessions, responses)
- `launchctl list | grep popchaos` (services)
- Task JSON (if we create one, or parse from TaskList output)
- Scraping logs/status files

---

## Dashboard 2: Token Usage & Environmental Impact

**Display (refreshes every 10s):**

```
┌─ RESOURCE USAGE ──────────────────────────────────────────┐
│ TODAY          WEEK           MONTH          BUDGET        │
│ $4.23          $18.67         $31.45         $50.00        │
│ 78.5K tokens   346K tokens    583K tokens    ██████░░ 63%  │
└────────────────────────────────────────────────────────────┘

┌─ SESSION BREAKDOWN ───────────────────────────────────────┐
│ Session    Responses    Est. Tokens    Est. Cost          │
│ 83209      15           45,000         $2.43 (Sonnet)     │
│ 14221      3            9,000          $0.49              │
│ 29658      1            3,000          $0.16              │
│ 29528      1            3,000          $0.16              │
└────────────────────────────────────────────────────────────┘

┌─ ENVIRONMENTAL IMPACT ────────────────────────────────────┐
│ Carbon footprint (today):    2.8g CO₂                     │
│ Carbon footprint (month):    12.1g CO₂                    │
│                                                            │
│ Equivalent to:                                             │
│ 🚗 0.03 miles driven                                       │
│ 🌳 0.0006 trees needed for offset                         │
└────────────────────────────────────────────────────────────┘

┌─ ALERTS ──────────────────────────────────────────────────┐
│ ⚠️  Approaching budget (63% of $50/month)                 │
│ ℹ️  15 responses this session (consider /clear)           │
└────────────────────────────────────────────────────────────┘
```

**Calculations:**
- Tokens: 3,000 avg per response (conservative estimate)
- Cost: Sonnet = $3/M in + $15/M out (~$0.054/response)
- Carbon: ~0.036g CO₂ per 1000 tokens (based on research)

**Data sources:**
- `~/.claude/.locks/.resource-tracker.json`
- Model pricing (hardcoded, updated when pricing changes)
- Carbon estimates from AI carbon footprint research

---

## Technical Implementation

### Tech Stack
- **Language:** Python 3.14
- **UI:** `rich` library (terminal dashboard)
- **Data:** JSON files + launchctl queries
- **Refresh:** asyncio event loop

### File Structure
```
~/Development/tools/
├── dashboard_tasks.py       # Background tasks viewer
├── dashboard_usage.py       # Token/carbon tracker
├── dashboard_combined.py    # Both in split view
└── dashboard_data.py        # Shared data fetching
```

### Launch
```bash
# Individual dashboards
python ~/Development/tools/dashboard_tasks.py
python ~/Development/tools/dashboard_usage.py

# Combined view (split screen)
python ~/Development/tools/dashboard_combined.py
```

### Keep Running
Option 1: Terminal tab dedicated to dashboard
Option 2: tmux/screen session
Option 3: Later: Web dashboard (Flask + auto-refresh)

---

## Data Collection Enhancement

**Currently missing:** Task progress tracking

**Solution:** Create task status JSON
```json
{
  "tasks": {
    "37": {"status": "in_progress", "progress": 0.8, "name": "Grant scraping"},
    "42": {"status": "in_progress", "progress": 0.3, "name": "Don Norman"},
    "43": {"status": "in_progress", "progress": 0.2, "name": "Art critics"}
  }
}
```

Location: `~/.claude/.locks/.task-progress.json`

Tasks update this when they make progress. Dashboard reads it.

---

## Future Enhancements

**Phase 2: Web Dashboard**
- Flask/FastAPI backend
- Real-time updates via WebSockets
- Accessible from browser
- Charts/graphs for trends

**Phase 3: Notifications**
- macOS notifications when budget thresholds hit
- Alert when background services fail
- Notify when scraping jobs complete

**Phase 4: Historical Tracking**
- SQLite database for trends over time
- Weekly/monthly reports
- Optimization recommendations based on patterns

---

## Success Criteria

✅ User can glance at terminal and see:
- All background processes status
- Current session usage
- Budget remaining
- Task progress
- Environmental impact

✅ No need to ask Claude "what's running?" ever again

✅ Cost: $0 tokens (pure Python reading JSON files)
