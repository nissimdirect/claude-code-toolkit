# LLM Delegation Schema
# Which model for which task — routing rules for OpenClaw + Claude Code

> **Based on:** RouteLLM, FrugalGPT, Cascade Routing, Task-Based Routing research.
> **Goal:** Use the cheapest model that can do the job well. Save Claude for what only Claude can do.
> **Updated:** 2026-02-15 (v2 — 8 fixes from CTO/RedTeam/Quality review)

---

## The Stack (What We Have)

| Tier | Model | Provider | Params | Context | RPM | Cost | Strengths |
|------|-------|----------|--------|---------|-----|------|-----------|
| **T1** | Claude Opus | Anthropic | ~1T+ | 200K | API | $$$ | Best reasoning, strategy, security, taste |
| **T1** | Claude Sonnet | Anthropic | ~300B+ | 200K | API | $$ | Strong code gen, analysis, extended thinking |
| **T2** | Gemini Flash | Google | ~100B+ | **1M** | 15 | Free | Massive context, research, summarization |
| **T2** | Groq (Llama 70B) | Groq | 70B | 128K | 30 | Free | Fast inference, strong reasoning |
| **T3** | Qwen Code | Alibaba | ~32B | 128K | CLI | Free | Code generation, batch transforms |
| **T3** | Ollama (Qwen 8B) | Local | 8B | 8K | **Unlimited** | Free | Simple tasks, offline, private, instant |
| **T4** | DeepSeek V3 | DeepSeek | 671B MoE | 64K | No limit | Free* | Research fallback (*China-hosted) |

---

## Task Routing Table

### Tier 1: Claude Only (No Delegation)

These tasks require taste, judgment, security awareness, or deep multi-step reasoning.
**Never delegate these to external LLMs.**

| Task | Why Claude | Example |
|------|-----------|---------|
| Strategic decisions | Taste, context, user knowledge | "Should we build X or Y?" |
| Architecture design | Security + sustainability tradeoffs | "Design the plugin architecture" |
| Security review | Must be trusted, not just capable | "Review this for vulnerabilities" |
| User-facing writing | Brand voice, tone, personality | Commit messages, PR descriptions |
| Multi-file code changes | Needs tool access + codebase context | "Refactor the auth system" |
| Skill/workflow execution | Needs Claude's tool ecosystem | /cto, /label, /quality, etc. |
| Sensitive data handling | Keys, configs, credentials | Anything touching .env, tokens |
| Creative direction | Artistic judgment | "Which design direction?" |
| Error diagnosis | Needs to run tools, test, iterate | "Why is this failing?" |
| Plan approval | Accountability, user trust | Final sign-off on any plan |

### Tier 2: Gemini Flash (Primary Delegatee)

Best for: large-context research, summarization, cross-referencing.
**The 1M token context window is unmatched.**

| Task | Why Gemini | Example |
|------|-----------|---------|
| KB article summarization | 1M context, reads everything at once | "Summarize reverb articles" |
| Codebase analysis | Can ingest entire repos | "What patterns does this codebase use?" |
| Cross-document search | Finds connections across 50+ files | "Find contradictions in these docs" |
| Research synthesis | Good at extracting + organizing | "What do these 20 articles say about X?" |
| Long document reading | 1M context handles entire PDFs | "Summarize this 200-page PDF" |
| Fact extraction | Accurate for structured data | "Extract all dates from these articles" |
| Comparison analysis | Side-by-side across many sources | "Compare these 5 frameworks" |

**Rate limit:** 15 RPM → batch prompts, don't rapid-fire.
**Fallback:** Groq → Ollama

### Tier 2: Groq (First Cloud Fallback)

Best for: fast answers with strong reasoning, when Gemini is rate-limited.
**70B model = real reasoning capability, fastest inference.**

| Task | Why Groq | Example |
|------|---------|---------|
| Complex Q&A | 70B model handles nuance | "Explain WDF vs nodal analysis" |
| Code review (read-only) | Strong enough for analysis | "What's wrong with this function?" |
| Technical writing | Good structured output | "Write docs for this API" |
| Multi-step reasoning | 70B handles chains well | "Walk through this algorithm" |
| Gemini fallback | When rate-limited | Same tasks as Gemini, smaller context |

**Rate limit:** 30 RPM → more headroom than Gemini.
**Context limit:** 128K → can't do full codebase analysis like Gemini.
**Fallback:** Ollama → DeepSeek

### Tier 3: Qwen Code (Code Specialist)

Best for: generating boilerplate, scaffolding, batch transforms.
**Optimized for code, not general reasoning.**

| Task | Why Qwen | Example |
|------|---------|---------|
| Boilerplate generation | Fast, accurate for templates | "Generate a JUCE plugin skeleton" |
| Test file creation | Pattern-based generation | "Write unit tests for this class" |
| Code translation | Language-to-language | "Convert this Python to C++" |
| Regex from English | Specialized skill | "Match email addresses" |
| CMakeLists/CI configs | Structured, template-heavy | "Write GitHub Actions workflow" |
| Batch transforms | Repetitive code changes | "Rename all methods to snake_case" |
| Scaffolding | Project structure generation | "Create Express.js project structure" |

**Don't use for:** DSP algorithms (precision matters), security-critical code, architecture decisions.
**Fallback:** Groq → Claude

### Tier 3: Ollama (Local Fallback)

Best for: simple tasks, offline, privacy, unlimited queries.
**8B model = good for simple tasks, bad for complex reasoning.**

| Task | Why Ollama | Example |
|------|-----------|---------|
| Simple Q&A | Fast, free, instant | "What's the Python syntax for X?" |
| Classification | Small models are fine | "Is this a bug report or feature request?" |
| Quick lookups | Don't waste cloud RPM | "What HTTP status code means X?" |
| Privacy-sensitive | Nothing leaves the Mac | "Summarize this private document" |
| Offline work | No internet needed | "Help me while traveling" |
| Formatting/conversion | Pattern-based, simple | "Convert this JSON to YAML" |
| Spell/grammar check | Basic language tasks | "Fix typos in this text" |
| Brainstorm seed | Quick idea generation | "Give me 5 names for X" |

**Don't use for:** Multi-step reasoning, research, code review, anything requiring nuance.
**Context limit:** ~8K tokens → short prompts only.
**Advantage:** Zero rate limits, zero cost, zero latency.

### Tier 4: DeepSeek (Last Cloud Resort)

Best for: non-sensitive research when all others are rate-limited.
**671B MoE = strong reasoning, but data goes to China.**

| Task | Why DeepSeek | Example |
|------|-------------|---------|
| Non-sensitive research | Large model, free tokens | "Explain reverb algorithms" |
| Math/reasoning | R1 model is strong at math | "Solve this DSP equation" |
| Long analysis | No per-minute rate limit | "Analyze this dataset" |

**NEVER use for:** Anything with API keys, credentials, personal data, business strategy, or proprietary code.
**Fallback:** This IS the last fallback. If DeepSeek fails, queue for Claude.

#### DeepSeek Blocklist (proprietary terms that SKIP DeepSeek in fallback)

Any message containing these terms bypasses DeepSeek entirely:
- Brand/identity: `popchaos`, `nissim`, `gone missin`, `openclaw`, `entropy bot`
- Business: `revenue`, `cost`, `budget`, `customer`, `pricing`, `strategy`, `roadmap`
- Architecture: `system design`, `our plugin`, `our architecture`, `proprietary`
- Personal: email addresses, phone numbers, physical addresses

**Definition of "non-sensitive":** No credentials, no PII, no proprietary business logic, no brand strategy. Generic technical questions only (e.g., "Explain reverb algorithms" = OK. "Explain our reverb plugin architecture" = NOT OK).

---

## Complexity Router (Decision Tree)

```
INCOMING TASK
    │
    │  ┌─────────────────────────────────────────────────┐
    │  │ STEP 0: SAFETY GATES (run BEFORE all routing)   │
    │  └─────────────────────────────────────────────────┘
    │
    ├─ [GATE 0a] Contains secrets/credentials/API keys/PII?
    │   Pattern match: sk-*, gsk_*, ntn_*, -----BEGIN, password=, token=,
    │   export KEY=, .env contents, email addresses, phone numbers
    │   └─ YES → Claude ONLY (Tier 1). NEVER delegate.
    │
    ├─ [GATE 0b] Message is empty or >500K characters?
    │   └─ EMPTY → Reject with "Please provide a task"
    │   └─ >500K → Gemini ONLY (1M context) or reject
    │
    │  ┌─────────────────────────────────────────────────┐
    │  │ STEP 1: CONTEXT CHECK                           │
    │  └─────────────────────────────────────────────────┘
    │
    ├─ [CTX 1] Is this a follow-up to a previous delegated task?
    │   Signals: starts with "now", "also", "then", "and", "what about",
    │   "compare that", "expand on", references previous answer
    │   └─ YES → Route to SAME model as previous task
    │       └─ Previous model unavailable? → Escalate to next tier
    │
    ├─ [CTX 2] Is intent ambiguous? (can't classify with >70% confidence)
    │   Signals: "help me", "fix this", vague single words, no verb
    │   └─ YES → Ask user for clarification OR default to Claude (safe)
    │
    │  ┌─────────────────────────────────────────────────┐
    │  │ STEP 2: MODEL HEALTH + RATE LIMIT CHECK         │
    │  └─────────────────────────────────────────────────┘
    │
    ├─ [HEALTH] Before routing to any model, check:
    │   1. Is model process/service running? (ping with 1-token test)
    │   2. Is model within rate limits? (check .llm-rate-limits.json)
    │      Gemini: skip if <3 RPM remaining (leave headroom)
    │      Groq: skip if <5 RPM remaining
    │   3. Is Claude budget >10%? (check .budget-state.json before queueing)
    │   └─ Model unavailable → Skip to next in fallback chain
    │   └─ All models unavailable → Queue with diagnostic message
    │
    │  ┌─────────────────────────────────────────────────┐
    │  │ STEP 3: TASK ROUTING (keyword + complexity)      │
    │  └─────────────────────────────────────────────────┘
    │
    ├─ Requires tool access (file edit, git, deploy)?
    │   └─ YES → Claude ONLY (Tier 1)
    │
    ├─ Requires taste/judgment/strategy?
    │   └─ YES → Claude ONLY (Tier 1)
    │
    ├─ Requires reading >50K tokens of context?
    │   └─ YES → Gemini Flash (Tier 2)
    │       └─ Rate limited? → Groq (if <128K) → Queue for Claude
    │
    ├─ Is it code generation/scaffolding?
    │   └─ YES → Qwen Code (Tier 3)
    │       └─ Complex/DSP? → Claude (Tier 1)
    │
    ├─ Is it a simple lookup/classification/format conversion?
    │   └─ YES → Ollama (Tier 3, local)
    │
    ├─ Is it research/analysis?
    │   ├─ Contains DeepSeek blocklist terms? → Skip DeepSeek in chain
    │   └─ YES → Gemini Flash (Tier 2)
    │       └─ Rate limited? → Groq → DeepSeek (if non-sensitive) → Queue
    │
    │  ┌─────────────────────────────────────────────────┐
    │  │ STEP 4: FALLBACK + ERROR HANDLING                │
    │  └─────────────────────────────────────────────────┘
    │
    ├─ Default (no match) → Gemini Flash (Tier 2)
    │   └─ Rate limited? → Groq → Ollama → DeepSeek → Queue
    │
    ├─ Model returned error/empty/timeout?
    │   └─ Re-validate original input (catch cascade poisoning)
    │   └─ Route to next fallback in chain
    │
    └─ All fallbacks exhausted?
        └─ Queue for Claude with error context + model failure log
        └─ If Claude budget <10% → Warn user: "All models unavailable,
           Claude budget low. Task queued for next session."
```

---

## Cascade Fallback Chains

Each task type has its own fallback chain:

| Task Type | Primary | Fallback 1 | Fallback 2 | Fallback 3 | Last Resort |
|-----------|---------|-----------|-----------|-----------|-------------|
| **Research/summarization** | Gemini Flash | Groq | DeepSeek | Ollama | Queue for Claude |
| **Code generation** | Qwen Code | Groq | Ollama (coder) | Claude | — |
| **Complex reasoning** | Gemini Flash | Groq | DeepSeek | Queue for Claude | — |
| **Simple Q&A** | Ollama | Groq | Gemini Flash | — | — |
| **Large context (>50K)** | Gemini Flash | Groq (if <128K) | Queue for Claude | — | — |
| **Privacy-sensitive** | Ollama | Claude | — | — | — |
| **Security/credentials** | Claude ONLY | — | — | — | — |
| **Strategic/creative** | Claude ONLY | — | — | — | — |
| **Image/vision analysis** | Gemini Flash | Claude | — | — | — |
| **Structured data extraction** | Qwen Code | Gemini Flash | Ollama | — | — |
| **Sentiment/classification** | Ollama | Groq | Gemini Flash | — | — |
| **Human language translation** | Gemini Flash | Groq | DeepSeek | — | — |
| **Brainstorming (seed ideas)** | Ollama | Groq | Gemini Flash | — | — |
| **Debugging (with logs/tools)** | Claude ONLY | — | — | — | — |
| **Regex generation** | Qwen Code | Ollama (coder) | Groq | — | — |
| **API design** | Claude ONLY | — | — | — | — |
| **Performance profiling** | Gemini Flash (ingest) | Claude (analyze) | — | — | — |
| **Proprietary research** | Gemini Flash | Groq | Claude | — | (skip DeepSeek) |

---

## Cost Savings Estimate

Based on research: **60-70% of delegatee queries can be handled by Tier 3 models.**

| Scenario | Before (Claude only) | After (routed) | Savings |
|----------|---------------------|----------------|---------|
| KB summarization (10 articles) | ~50K tokens Claude | 0 tokens (Gemini) | 100% |
| Code scaffolding | ~20K tokens Claude | 0 tokens (Qwen) | 100% |
| Simple lookups (20/day) | ~40K tokens Claude | 0 tokens (Ollama) | 100% |
| Research synthesis | ~80K tokens Claude | 0 tokens (Gemini) | 100% |
| Complex architecture | Claude (no change) | Claude (no change) | 0% |

**Projected:** 50-70% reduction in Claude token usage for delegatable tasks.

---

## Implementation: OpenClaw Integration

OpenClaw should use this schema when processing Telegram messages:

```
User message → Intent classification → Route to model
                                       ├─ "Summarize X" → gemini-safe.sh
                                       ├─ "Generate code for X" → qwen-safe.sh
                                       ├─ "What is X?" (simple) → ollama-safe.sh
                                       ├─ "Review X" (complex) → groq-safe.sh
                                       └─ "Decide X" → Claude (native)
```

### Keyword Hints for OpenClaw Routing

| Keywords in message | Route to |
|--------------------|----------|
| summarize, summarise, recap, overview, what do...say about | Gemini |
| generate, scaffold, boilerplate, template, write code for | Qwen |
| what is, define, syntax, how to (simple), convert, format | Ollama |
| review, analyze, compare, explain (complex), why does | Groq |
| decide, should we, strategy, plan, approve, security | Claude |
| read this file, read this codebase, find in, search across | Gemini |
| translate (code), rename, batch, regex | Qwen |

---

## Quality Gates

Every delegated response passes through before use:

1. **delegation_validator.py** — injection detection, size check, task-specific validation
2. **Confidence scoring** (deterministic — not subjective):
   ```
   Hedging signals (-20 each): "I'm not sure", "I think", "probably",
     "might be", "could be", "unclear", "ambiguous"
   Refusal signals (-30 each): "I can't", "I don't have enough",
     "beyond my capability", asks clarifying questions back
   Contradiction signals (-40): provides multiple conflicting answers

   Score starts at 100. If <60 → escalate to next tier.
   ```
3. **Escalation re-validation** — when falling back to a higher tier, re-run
   delegation_validator.py on the ORIGINAL input (prevents cascade poisoning
   where injection passes a weak model and activates on a stronger one)
4. **Claude review** — Claude validates delegated output before acting on it.
   Delegated code is NEVER auto-executed. User sees the validated response.

---

## Anti-Patterns (Don't Do This)

| Anti-Pattern | Why It's Bad | Do This Instead |
|-------------|-------------|-----------------|
| Send everything to Claude | Wastes budget on simple tasks | Route simple tasks to Ollama/Gemini |
| Send everything to Ollama | 8B model fails on complex tasks | Use complexity router |
| Rapid-fire Gemini calls | Hits 15 RPM limit | Batch prompts, use 1M context |
| Send secrets to DeepSeek | Data stored in China | Claude only for sensitive data |
| Auto-execute delegated code | Injection risk | Always validate + review |
| Skip fallback chain | Single point of failure | Always have cascade |
| Use Groq for large context | 128K limit | Use Gemini (1M) for large reads |

---

## Rate Limit Tracking

The router needs real-time awareness of each model's remaining capacity.

**State file:** `~/.openclaw/llm-rate-limits.json`

```json
{
  "gemini": {
    "rpm_limit": 15,
    "window_seconds": 60,
    "calls": ["2026-02-15T14:30:01Z", "2026-02-15T14:30:05Z"],
    "headroom": 3
  },
  "groq": {
    "rpm_limit": 30,
    "window_seconds": 60,
    "calls": [],
    "headroom": 5
  },
  "ollama": {
    "rpm_limit": null,
    "calls": []
  },
  "deepseek": {
    "rpm_limit": null,
    "calls": []
  }
}
```

**Logic:** Before routing to a model, count calls in last 60 seconds.
If `(rpm_limit - count) < headroom` → skip to next fallback.
After each call, append timestamp. Prune timestamps older than 60s.

---

## Glossary

| Term | Definition |
|------|-----------|
| **Simple Q&A** | Single-fact lookup, no reasoning chain. "What's the syntax for X?" |
| **Complex reasoning** | Multi-step logic, requires inference or comparison. "Why does X cause Y?" |
| **Non-sensitive** | No credentials, no PII, no proprietary business logic, no brand strategy. Generic technical questions only. |
| **Cascade poisoning** | An attack where injection passes a weak model (Ollama 8B) but activates when escalated to a stronger model (Groq 70B). |
| **Hedging** | When a model expresses uncertainty: "I think", "probably", "might be". Signal to escalate. |
| **RPM** | Requests Per Minute — how many API calls a model allows in a rolling 60-second window. |
| **Escalation** | Moving a task from a cheaper model to a more capable one when the cheaper model fails or is uncertain. |
| **Claude review** | Claude validates delegated output before the user sees it. Delegated code is never auto-executed. |
| **Queue for Claude** | When no external model can handle a task, it's saved to `~/Documents/Obsidian/process/CLAUDE-QUEUE.md` for Claude's next session. |

---

## Metrics to Track (Future)

When we build the router:
1. **Delegation rate** — % of tasks routed away from Claude
2. **Escalation rate** — % that needed to fall back to higher tier
3. **Claude tokens saved** — direct budget impact
4. **Quality score** — user satisfaction with delegated responses
5. **Latency** — time-to-first-response per model

---

*Reference: Research patterns from RouteLLM (LMSYS), FrugalGPT, AWS Bedrock routing,
Cascade AI, Anthropic execution modes. See Obsidian for full research notes.*
