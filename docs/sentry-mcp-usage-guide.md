# Sentry MCP Usage Guide — PopChaos Labs

> **INSTRUCTIONS FOR NEXT USER:** If any tool name, workflow, or integration point
> listed here has changed, UPDATE THIS FILE. Cross-reference against Sentry docs
> at https://docs.sentry.io/product/sentry-mcp/
> Last verified: 2026-02-18

---

## What Is This?

Sentry MCP gives Claude Code direct access to **runtime execution data** — real error traces,
stack frames, span timings, and event searches. This closes the fundamental gap where LLMs
can read code but cannot observe what happens when it runs.

**Core insight:** Static code analysis guesses at problems. Trace data SHOWS the problem.

---

## Setup Status

| Component | Status | Location |
|-----------|--------|----------|
| MCP Config | DONE | `~/.claude/.mcp.json` → `https://mcp.sentry.dev/mcp` |
| Sentry SDK | DONE | `sentry-sdk==2.53.0` installed globally |
| Entropic init | DONE | `server.py` lines 20-26, reads `SENTRY_DSN` env var |
| OAuth Auth | **USER BLOCKER #27** | Run `/mcp` → Sentry → Authenticate after restart |
| SENTRY_DSN | **USER BLOCKER #27** | Create project at sentry.io → get DSN → `export SENTRY_DSN=...` |

---

## Available MCP Tools

Once authenticated, Claude Code can call these tools directly:

### Discovery Tools
| Tool | What It Does | When to Use |
|------|-------------|-------------|
| `find_organizations` | Lists your Sentry orgs | First call — discovers account |
| `find_projects` | Lists projects in an org | Finds the right project to query |

### Issue Investigation Tools
| Tool | What It Does | When to Use |
|------|-------------|-------------|
| `search_issues` | Natural-language issue search | "Find unresolved errors in last 24h" |
| `get_issue_details` | Full stack trace + context for one issue | Deep-dive into a specific error |
| `search_events` | Search raw events by query | Find specific error occurrences across time |

### Analysis Tools
| Tool | What It Does | When to Use |
|------|-------------|-------------|
| Seer (auto root-cause) | AI-powered root cause analysis | Production errors with complex traces |
| Span analysis | Performance timing data | Slow endpoints, timeout investigation |

---

## How To Use: Practical Workflows

### Workflow 1: "What's broken right now?"

Use at start of debugging session or after a deploy.

```
Prompt to Claude Code:
"Check Sentry for any new errors in Entropic in the last 24 hours."

What happens:
1. find_organizations → discovers PopChaos org
2. find_projects → finds entropic project
3. search_issues → returns unresolved issues
4. Claude summarizes: issue count, severity, affected endpoints
```

### Workflow 2: "Debug this specific error"

Use when you have an error message or user report.

```
Prompt to Claude Code:
"Look up this Sentry issue: [paste issue URL or ID].
What's the root cause? Show me the stack trace."

What happens:
1. get_issue_details → full stack trace, file:line, context
2. Claude reads the referenced source files
3. Claude proposes fix based on ACTUAL execution path (not guessing)
```

### Workflow 3: "Is this regression new?"

Use after deploying a fix to verify it worked.

```
Prompt to Claude Code:
"Search Sentry for the TypeError in apply_chain — is it still happening
after commit abc123?"

What happens:
1. search_events → filters by error type + time range
2. Claude compares event count before/after deploy
3. Reports: regression fixed (0 new events) or still happening (N events)
```

### Workflow 4: "Performance investigation"

Use when something is slow but not crashing.

```
Prompt to Claude Code:
"Check Sentry for slow API calls in Entropic's /api/preview endpoint.
What spans are taking the longest?"

What happens:
1. search_events → finds slow transactions
2. Span analysis → breaks down where time is spent
3. Claude identifies bottleneck (e.g., apply_chain taking 4s for 6 effects)
```

---

## Integration Points (Where Sentry Fits in Our System)

### In the SDLC Flywheel

| Phase | How Sentry Helps |
|-------|-----------------|
| **Phase 2: BUILD** | Instrument new endpoints with `sentry_sdk.init()` |
| **Phase 3: TEST** | After UAT, check Sentry for errors the tests missed |
| **Phase 4: DEBUG** | Primary tool — fetch traces instead of guessing at root cause |
| **Phase 5: SHIP** | Post-deploy verification — "any new errors in last hour?" |
| **Phase 6: MONITOR** | Daily health check — add to `/today` startup |
| **Phase 7: LEARN** | Error patterns → learnings.md, compound docs |

### In Skills

| Skill | Sentry Integration |
|-------|-------------------|
| `/cto` | Architecture-level diagnosis using trace data |
| `/quality` | Post-deploy verification — "0 new Sentry errors = PASS" |
| `/qa-redteam` | Security audit — check for leaked error info in Sentry events |
| `/ship` | Ship checklist: "Check Sentry after deploy" |
| `/session-close` | Report: "Sentry: N new errors this session" |
| `/today` | Morning check: "Any overnight errors?" |
| `debug-session` (WF#35) | Step 3: Fetch Sentry traces before adding logging |

### In Compound Engineering Loops

**Loop 9: Observe → Debug → Fix → Verify (Sentry Loop)**
```
Sentry captures runtime error → search_issues finds it
→ get_issue_details shows stack trace → Claude reads source
→ Fix applied + test written → Deploy → search_events confirms fix
→ 0 recurrence = verified → /workflows:compound documents solution
→ learning_hook.py injects pattern next time similar error appears
```

**Enhancement to Loop 8 (Debug → Document → Prevent):**
```
Bug found → Check Sentry FIRST (trace data > guessing)
→ If Sentry has trace: use it as primary evidence
→ If no trace: fall back to Iterative Logging Loop
→ Root cause documented with Sentry event link as proof
```

---

## Entropic-Specific Setup

### Environment Variables

Add to `~/.zshrc` or `~/.zshenv`:
```bash
export SENTRY_DSN="https://your-key@o123456.ingest.sentry.io/project-id"
export SENTRY_ENV="development"  # or "production"
```

### What Gets Traced

With `traces_sample_rate=1.0` (current setting), Sentry captures:
- Every FastAPI request (auto-instrumented by sentry-sdk[fastapi])
- Request duration, status code, URL
- Spans for DB queries, subprocess calls, file I/O (if instrumented)
- Unhandled exceptions with full stack traces

### Reducing Noise

For development, you may want to filter:
```python
sentry_sdk.init(
    dsn=os.environ["SENTRY_DSN"],
    traces_sample_rate=0.1,  # 10% of requests
    profiles_sample_rate=0.01,  # 1% profiling
    before_send=lambda event, hint: None if "test" in event.get("server_name", "") else event,
)
```

---

## When NOT to Use Sentry

- **Local-only debugging** — if the error is reproducible locally, iterative logging is faster
- **No SENTRY_DSN set** — SDK silently no-ops, no traces collected
- **Pre-authentication** — until OAuth is done (User Blocker #27), tools won't work
- **Budget crunch** — Sentry MCP calls cost tokens; at >85% budget, use manual logging

---

## Quick Reference Card

```
┌────────────────────────────────────────────────────┐
│  SENTRY MCP QUICK REFERENCE                        │
├────────────────────────────────────────────────────┤
│  "Check Sentry for errors"     → search_issues     │
│  "Show me this error"          → get_issue_details  │
│  "Is this still happening?"    → search_events      │
│  "What projects do I have?"    → find_projects      │
│  "What's slow?"                → search_events      │
│  "/mcp → Sentry → Authenticate" → re-auth           │
├────────────────────────────────────────────────────┤
│  ENTROPIC: SENTRY_DSN in ~/.zshrc                  │
│  CHAOS VIZ: Add sentry_sdk.init() when ready       │
│  Traces: 100% dev / 10% prod recommended           │
└────────────────────────────────────────────────────┘
```

---

*Created: 2026-02-18 | Source: Sentry MCP docs + VIBE-CODING-DEBUGGING-GUIDE.md*
*References: https://docs.sentry.io/product/sentry-mcp/ | https://github.com/getsentry/sentry-mcp*
