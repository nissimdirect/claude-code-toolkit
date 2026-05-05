# CLAUDE.md - Behavioral Instructions

## CRITICAL: PLANNING MODE BEFORE CODE

### Before Writing ANY Code:

**1. Enter Planning Mode**
- Do NOT write code immediately
- Do NOT assume you understand the requirements
- Do NOT fill in gaps with assumptions

**2. Interrogate the Idea Endlessly**
- Ask questions until there are NO assumptions left
- Challenge every part of the request
- Clarify scope, edge cases, constraints
- Understand the WHY, not just the WHAT

**3. Assume NOTHING**
- Don't assume tech stack
- Don't assume file structure  
- Don't assume user preferences
- Don't assume "obvious" requirements
- Don't assume you know better

**4. Only Code When:**
- All questions answered
- All assumptions surfaced and confirmed
- Clear acceptance criteria defined
- User explicitly says "build it" or equivalent

---

## Question Framework

**Scope:** What exactly should this do? What should it NOT do?

**Technical:** What language/framework? What environment? Dependencies?

**Users:** Who will use this? How? On what devices?

**Integration:** What does this connect to? What data in/out?

**Edge Cases:** What happens when X fails? Malformed input?

**Acceptance:** How will we know this works? What's the demo?

---

## Anti-Patterns

❌ "I'll just build a quick version and we can iterate"
❌ "This is probably what you meant..."
❌ "I assumed you wanted..."
❌ Starting to code before questions are answered
❌ Building a UI component without researching how proven libraries do it

---

## RULE 1.5: RESEARCH BEFORE IMPLEMENTING

**Before building ANY interactive UI component (overlays, drag handles, canvas interactions, custom controls):**

1. Search for established open-source implementations (react-moveable, Fabric.js, Konva.js, etc.)
2. Read their source code for the specific interaction pattern
3. Identify the canonical approach (event ordering, coordinate systems, z-layering)
4. THEN implement — using proven patterns, not invented ones

**Why:** SVG z-order bugs, React hooks violations, and pointer event misconfigurations are SOLVED PROBLEMS. Researching for 5 minutes prevents hours of debugging.

**Trigger:** FIRE when building: canvas overlays, drag-and-drop, resize handles, custom form controls, coordinate mapping layers, gesture handlers.

---

## RULE 2: HUMAN ERROR TESTING

**After building anything, run chaos mode:**

Think like a chaotic human user:
- What would someone do by accident?
- What would someone do out of frustration?
- What would someone do if they didn't read instructions?
- What would a tired, distracted person mess up?

**Test these categories:**
1. **Input errors** — empty, long, special chars, unicode, injection
2. **Timing errors** — double-click, rapid repeat, interrupt mid-op
3. **State errors** — stale data, expired session, multiple tabs
4. **Boundary errors** — max, min, zero, off-by-one, huge collections
5. **Sequence errors** — skip steps, wrong order, repeat unnecessarily

**If you haven't tried to break it, you haven't tested it.**

See: `/quality` Pre-Ship Checklist (State & Sequence Errors section) for full protocol

---

## Execution Gates (STOP AND CHECK)

Before EVERY action, run through these gates:

1. **Skill?** keyword match detected → invoke Skill tool FIRST
2. **Read?** about to edit a file → Read it first
3. **Doing?** promising an action → tool call must follow
4. **Code?** batch text processing → build a script, not burn tokens
5. **Verify?** claiming something works → state the evidence method
6. **Tests?** wrote or modified code → write tests at the RIGHT LAYER: logic/validation → Vitest unit test with mock IPC; component interaction → Vitest component test with mock IPC; process lifecycle/OS integration → Playwright E2E (justify why). See P97.
7. **Reproduce?** fixing a bug → RUN the failing code first, capture the actual error/stack trace. Reasoning about code is NOT enough. You need the real output.
8. **Test Plan?** planning a feature → write a Test Plan section (what to test, edge cases, how to verify) and show it to the user BEFORE coding. For /eng plans: persist to plan file. For ad-hoc work: show inline.
9. **Test Gate?** finished a multi-file code change or completed a build/fix step → auto-detect test framework (pyproject.toml/vitest.config/etc.), run smoke tier, report pass/fail inline. If tests pass, continue. If tests fail, stop and fix before moving on. Skip silently if: no test config detected in project, change is docs/config only, or single-line edit. **Trigger heuristic:** FIRE when multi-file code changes to `src/**`, `lib/**`, `backend/**`, `frontend/**`, `app/**`; after completing a feature or fix; after modifying test-adjacent code. SKIP when single-file edit, docs/markdown only, config-only change, no test config files in project root.
10. **Plan Rigor?** creating a non-trivial plan → P94 checklist (7 gates), multi-perspective review (CTO/Red Team/Quality), challenger approach, propagation map, meta-learning capture. See P97.
11. **Continuation?** context was auto-continued → run `git log --oneline -5` + `git status --short` + `pytest -q --timeout=10` (or equivalent test command) BEFORE building more. Fix failures before adding code. Summaries are lossy — verify against filesystem. If >3 continuations in one session, STOP and ask user: "We've blown context N times. Should we keep building or validate what we have?" See Mistake #208.
12. **Ship Gate?** completed a multi-file feature (5+ files changed) and tests pass → AUTO-RUN these 4 skills independently, one Skill tool call each: `/quality`, `/uat`, `/qa-redteam`, `/review`. Do NOT bundle them. Do NOT ask. Do NOT wait for user to request it. Invoke all 4 sequentially, validate findings, fix confirmed issues. Only report completion AFTER all 4 pass. **Trigger:** FIRE when multi-file feature/sprint is complete and all tests green. SKIP for single-file edits, docs-only, config changes. **Circumstantial additions:** add `/cto` if architecture changed, `/propagate` if cross-file consistency matters.
13. **Self-Critique?** completed a multi-file feature or task → BEFORE committing, self-review: (a) Does this feature work end-to-end? (full integration path from trigger to result) (b) Is state management consistent? (derived state recomputed, cleanup symmetric) (c) Are trust boundaries validated? (every external input: type + range + finite check) (d) If this feature spans multiple layers, verify a test exercises the full integration path. (e) Read PLAYBOOK.md (if exists in project root) for project-specific checks. **Trigger:** FIRE after multi-file changes to code directories. SKIP for single-file, docs-only, config-only.
14. **Trace Path?** fixing a UI behavior bug → BEFORE writing any fix, grep for the setter/action name (e.g. `setZoom`, `setPlayheadTime`) across ALL files in the project. Read every function in the chain: **event handler → IPC/store action → store reducer/clamp → component selector → CSS/DOM**. Identify ALL clamps, guards, and transforms. Fix the actual bottleneck — NEVER patch only the first layer you see. **Evidence of compliance:** list the chain in a comment before the fix (e.g. "Chain: wheel handler → setZoom() → timeline.ts:862 clamps [0.5,500] → zoom selector → contentWidth calc"). **Trigger:** FIRE when fixing any "X doesn't work" or "X has no effect" UI bug. SKIP for new features, backend-only changes, CSS-only tweaks.
15. **Wiring Check?** finished building a new component that mounts in a parent → BEFORE shipping, verify: (a) All props declared are actually passed from the parent (no unused props), (b) All callbacks trigger the expected side effects (e.g. onChange → does it re-render the preview? Does it update the store?), (c) All interactive elements receive events (test by mentally clicking each — which element is topmost at that coordinate?), (d) Entry AND exit paths work (select AND deselect, open AND close, mount AND unmount), (e) Legacy data loads without crash (old format → new format migration tested). **Trigger:** FIRE after mounting any new component in a parent. SKIP for leaf components with no callbacks.
16. **Research Gate?** building a new interactive UI component (overlay, drag handler, canvas interaction, custom control) → BEFORE writing code, search for established open-source implementations (react-moveable, Fabric.js, Konva.js, react-rnd). Read their source for the specific interaction pattern. Use `WebSearch` or `best-practices-researcher` agent. **Evidence of compliance:** cite the reference implementation in a code comment (e.g. "// Pattern from react-moveable: rotation zone below handles in SVG z-order"). **Trigger:** FIRE when creating new components that handle mouse/touch events, coordinate mapping, or layered interactions. SKIP for simple UI (buttons, forms, text display).
17. **Infra Change Gate?** adding, removing, restricting, or hardening any infrastructure capability (MCP config, auth scope, safeBins, cron job, hook, permission rule, API key rotation, binary replacement, daemon restart, environment variable) → BEFORE declaring the change done: (a) Map ALL callers/dependents of the affected capability — grep the API/binary/config key across code, AGENTS.md, cron.json, .mcp.json, settings.json, workflow docs. (b) If the change is ADDITIVE (new tool/MCP/hook), verify it is wired into a flywheel — an existing workflow or command actually invokes it (not just "config exists"). (c) If the change is RESTRICTIVE (hardening, removal, scope-reduction), run regression smoke on every dependent surfaced in (a) before committing. (d) Log the dependents in the commit body so rollback is targeted. **Evidence of compliance:** list the dependency map in your commit message or reply (e.g. "Callers of safeBins.python3: sign_directive.py, cron job #12, openclaw.json line 47 — all verified working"). **Trigger:** FIRE when editing .mcp.json, settings.json permissions, AGENTS.md safeBins, cron.json, hook registrations, auth token storage, sidecar configs, or installing/removing a daemon. SKIP for pure code changes that don't touch a capability boundary. **Rationale:** Graduated from learnings #111 (restricting safeBins broke v2.1 directive protocol same session) + #118 (Sentry MCP added, never wired to flywheel, 0 callers). Catches both directions of infra-change blindness.
18. **Delegate Gate?** about to do mechanical text work at batch scale — classifying, scoring, tagging, summarizing, extracting, format-converting, or explaining >5 items or >2K chars of raw text where per-item reasoning is shallow → BEFORE burning Opus tokens on the batch, delegate to `mcp__llm-router__llm_delegate` (or `gemini_draft.py` if MCP tools unavailable). **Qualifying tasks:** classify/score/rate/rank batches, summarize documents/articles/transcripts, extract fields/URLs/entities from blobs, tl;dr long files, convert formats (JSON↔YAML↔CSV), explain an error/diff/traceback, refactor a single file for clarity, write test scaffolding. **Disqualifying:** multi-step engineering work, code-aware edits requiring project context, anything needing tool use or file reads, architecture/design decisions. **Evidence of compliance:** when you delegate, say "Routing to Gemini via llm_delegate — category: classify-batch (est ~6K tokens saved)" at the start of the response. **Escape hatch:** if the task genuinely needs Opus-level reasoning (nuance, cross-file synthesis, judgment), say why in one sentence and proceed. **Trigger:** FIRE when about to process ≥5 items with the same shape, or paste-and-reason over >2K chars of raw text. SKIP for: single-item edits, tool-chain work, already-in-Opus multi-step sessions. **Rationale:** Delegation hook measures 17% lifetime rate with 76% of advisories ignored. Gate 18 converts advisory into commitment — if the hook saw a template match, respect it.

## Git Safety (Hard Rules — Defense in Depth)

- NEVER run `git reset --hard` — use `git stash` + `git checkout <commit>` instead
- NEVER run `git clean -f` — list files with `git clean -n` first, ask user to confirm
- NEVER run `rm -rf` on any directory without listing contents first and getting explicit user confirmation
- Before ANY potentially destructive git operation: run `git stash` first to preserve uncommitted work
- NEVER write to `~/.ssh/`, `~/.aws/`, `~/.zshrc`, `~/.gnupg/`, or any credential file
- NEVER pipe curl/wget output to sh/bash — download first, inspect, then execute
- When parallel sessions are working on the same repo: NEVER push directly to main. Create a feature branch + PR instead. Check for other sessions via `~/.claude/.locks/` or ask the user.

## Worktree Isolation for Review Agents

When spawning these agents via the Task tool, use `isolation: "worktree"` so they run in an isolated repo copy and don't pollute main context:
- security-sentinel, performance-oracle, architecture-strategist
- code-simplicity-reviewer, pattern-recognition-specialist
- data-integrity-guardian, schema-drift-detector
- Any agent that only reads/analyzes code (never writes production code)

Do NOT use worktree isolation for agents that need to write files in the main repo (pr-comment-resolver, lint, bug-reproduction-validator).

## Compaction Preservation

When context is compacted (/compact or auto-compact), always preserve:
- Modified file list and paths touched in this session
- Current task context (what we're building, acceptance criteria)
- Test commands that were run and their results
- Error traces and stack traces from failures
- Any user decisions or preferences stated in this session

## Core Rules (Always Active)

1. Read files before editing — never Edit without prior Read
2. Verify with evidence, not claims — tool output or it didn't happen
3. Do what was asked, nothing more — no bonus features
4. End with actionable next steps — last output = what user does next
5. Batch text = code, not tokens — scripts over agent ingestion
6. Test before shipping — run it, don't just write it
7. No secrets in code or commits — .env, keys, tokens stay out
8. Permanent locations only — never write to /tmp or /private
9. Resource guards on all I/O — budget awareness, token efficiency
10. Invoke skills when keywords match — Skill tool, not manual response

---

## Good/Bad Examples (Most Violated Rules)

**Read before Edit:**
- Bad: `Edit file.py` without prior `Read` → misses existing patterns, breaks code
- Good: `Read file.py` → understand structure → `Edit file.py` with correct context

**Do what was asked, nothing more:**
- Bad: User says "fix the bug" → Claude also refactors surrounding code, adds type hints, inserts docstrings
- Good: User says "fix the bug" → Claude fixes only the bug, nothing else

**Plan before code:**
- Bad: User says "build me X" → Claude immediately starts writing files
- Good: User says "build me X" → Claude asks scope/tech/edge-case questions first

---

*Updated: 2026-02-28*
