# Claude Code Multi-Agent / TeammateTool Guide

> Reference documentation for Claude Code's multi-agent capabilities: TeammateTool, agent teams, swarm orchestration.
> Covers: Official documentation, third-party frameworks, usage patterns, and best practices.
> Last updated: 2026-02-07

---

## Table of Contents

1. [Overview](#overview)
2. [Agent Teams (Official)](#agent-teams-official)
3. [Enabling Agent Teams](#enabling-agent-teams)
4. [Architecture](#architecture)
5. [TeammateTool Operations](#teammatetool-operations)
6. [Usage Patterns](#usage-patterns)
7. [Best Practices](#best-practices)
8. [Agent Teams vs Subagents](#agent-teams-vs-subagents)
9. [Claude-Flow (Third-Party)](#claude-flow-third-party)
10. [Other Multi-Agent Frameworks](#other-multi-agent-frameworks)
11. [Display Modes](#display-modes)
12. [Limitations](#limitations)
13. [Resources](#resources)

---

## Overview

### What Are Agent Teams?

Agent teams in Claude Code are a **research preview feature** that enables multiple AI agents to work simultaneously on different aspects of a coding project, coordinating autonomously.

- **Official Docs**: [code.claude.com/docs/en/agent-teams](https://code.claude.com/docs/en/agent-teams)
- **Launched**: February 2026 alongside Claude Opus 4.6
- **Status**: Experimental (disabled by default)

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Team Lead** | The main Claude Code session that creates and coordinates the team |
| **Teammates** | Separate Claude Code instances that work on assigned tasks |
| **Task List** | Shared work queue with dependencies that teammates claim and complete |
| **Mailbox** | Messaging system for inter-agent communication |
| **Subagents** | Lighter-weight helpers within a single session (different from teammates) |
| **Swarm Mode** | The pattern of one leader spawning multiple specialized workers |

### Market Context

- **Gartner**: 1,445% surge in multi-agent system inquiries from Q1 2024 to Q2 2025
- **Prediction**: By end of 2026, 40% of enterprise applications will include task-specific AI agents
- **Source**: [VentureBeat - Claude Code 2.1.0](https://venturebeat.com/orchestration/claude-code-2-1-0-arrives-with-smoother-workflows-and-smarter-agents/)

---

## Agent Teams (Official)

### How It Works

Agent teams let you coordinate multiple Claude Code instances working together:

1. **You describe a task** that benefits from parallel work
2. **Claude creates a team** based on your instructions
3. **Teammates are spawned** as independent Claude Code sessions
4. **Each teammate** works on their assigned portion independently
5. **Teammates communicate** via messages and shared task lists
6. **The lead synthesizes** findings and coordinates work
7. **You can interact** with any teammate directly

### Starting a Team

Tell Claude to create an agent team with natural language:

```
I'm designing a CLI tool that helps developers track TODO comments across
their codebase. Create an agent team to explore this from different angles: one
teammate on UX, one on technical architecture, one playing devil's advocate.
```

Claude will:
- Create a team with a shared task list
- Spawn teammates for each perspective
- Have them explore the problem independently
- Synthesize findings when they finish
- Clean up the team when done

### Controlling the Team

Everything is done via natural language to the lead:

```
# Specify teammates and models
Create a team with 4 teammates to refactor these modules in parallel.
Use Sonnet for each teammate.

# Require plan approval
Spawn an architect teammate to refactor the authentication module.
Require plan approval before they make any changes.

# Wait for completion
Wait for your teammates to complete their tasks before proceeding.

# Shut down a teammate
Ask the researcher teammate to shut down.

# Clean up
Clean up the team.
```

---

## Enabling Agent Teams

### Configuration

Agent teams are **disabled by default**. Enable them:

#### Option 1: settings.json

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

#### Option 2: Environment Variable

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

#### Option 3: Shell Prefix

```bash
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude
```

---

## Architecture

### Component Overview

```
+------------------+
|     You (User)   |
+--------+---------+
         |
         v
+--------+---------+     Spawn      +-------------------+
|    Team Lead     |--------------->| Teammate A        |
|                  |                | (own context)     |
|  Coordinates     |     Spawn      +-------------------+
|  Assigns tasks   |--------------->| Teammate B        |
|  Synthesizes     |                | (own context)     |
|                  |     Spawn      +-------------------+
|                  |--------------->| Teammate C        |
+--------+---------+                | (own context)     |
         |                          +-------------------+
         v                                  |
+--------+---------+                        |
|   Shared Task    |<-----------------------+
|   List           |  Claim / Complete
|                  |
|   Mailbox        |  Messages
+------------------+
```

### Storage Locations

| Component | Path |
|-----------|------|
| **Team config** | `~/.claude/teams/{team-name}/config.json` |
| **Task list** | `~/.claude/tasks/{team-name}/` |
| **Config contents** | `members` array with name, agent ID, agent type |

### Task System

Tasks have three states:
1. **Pending**: Waiting to be claimed
2. **In Progress**: A teammate is working on it
3. **Completed**: Work is done

Task features:
- **Dependencies**: A task can depend on other tasks (blocked until dependencies complete)
- **Auto-unblock**: When a dependency completes, blocked tasks automatically unblock
- **File locking**: Prevents race conditions when multiple teammates try to claim the same task
- **Self-claim**: After finishing a task, a teammate picks up the next available one

### Context and Communication

Each teammate:
- Has its **own context window** (independent from the lead)
- Loads **project context**: CLAUDE.md, MCP servers, skills
- Receives **spawn prompt** from the lead
- Does **NOT** inherit the lead's conversation history

Communication channels:
- **Message**: Send to one specific teammate
- **Broadcast**: Send to all teammates (use sparingly -- costs scale with team size)
- **Automatic delivery**: Messages arrive at recipients automatically
- **Idle notifications**: Teammates notify the lead when they finish
- **Shared task list**: All agents can see task status

### Permissions

- Teammates start with the **lead's permission settings**
- If lead uses `--dangerously-skip-permissions`, all teammates do too
- Can change individual teammate modes **after** spawning
- Cannot set per-teammate modes **at** spawn time

---

## TeammateTool Operations

### Overview

TeammateTool is the underlying tool interface with **13 defined operations** organized across three categories:

### Category 1: Team Lifecycle

| Operation | Purpose |
|-----------|---------|
| **Create Team** | Initialize a new team with config and task list |
| **Spawn Teammate** | Create a new teammate with a specific prompt and role |
| **Discover Team** | Read team config to find all current members |

### Category 2: Coordination

| Operation | Purpose |
|-----------|---------|
| **Create Task** | Add a task to the shared task list |
| **Claim Task** | Teammate claims an available (unblocked) task |
| **Complete Task** | Mark a claimed task as completed |
| **Update Task** | Modify task details or status |
| **List Tasks** | View all tasks and their states |
| **Send Message** | Send message to a specific teammate |
| **Broadcast** | Send message to all teammates |
| **Check Inbox** | Read messages received from other agents |

### Category 3: Shutdown

| Operation | Purpose |
|-----------|---------|
| **Request Shutdown** | Ask a teammate to shut down gracefully |
| **Cleanup** | Remove shared team resources (only run by lead) |

### Task Dependencies

```
Task A (no deps)     Task B (no deps)     Task C (depends on A, B)
    |                     |                        |
    v                     v                        | (blocked)
 In Progress          In Progress                  |
    |                     |                        |
    v                     v                        v
 Completed            Completed              Auto-unblocked
                                                   |
                                                   v
                                              In Progress
```

---

## Usage Patterns

### Pattern 1: Parallel Code Review

```
Create an agent team to review PR #142. Spawn three reviewers:
- One focused on security implications
- One checking performance impact
- One validating test coverage
Have them each review and report findings.
```

**Why it works**: Each reviewer applies a different lens independently. The lead synthesizes findings across all three.

### Pattern 2: Competing Hypotheses (Debugging)

```
Users report the app exits after one message instead of staying connected.
Spawn 5 agent teammates to investigate different hypotheses. Have them talk to
each other to try to disprove each other's theories, like a scientific
debate. Update the findings doc with whatever consensus emerges.
```

**Why it works**: Adversarial investigation avoids anchoring bias. The theory that survives debate is more likely correct.

### Pattern 3: Feature Development (Parallel Modules)

```
Create a team to build the authentication module:
- Teammate 1: Database schema and migrations
- Teammate 2: API endpoints and middleware
- Teammate 3: Frontend login/signup components
- Teammate 4: Test suite for all of the above
```

**Important**: Each teammate must own **different files** to avoid conflicts.

### Pattern 4: Research and Analysis

```
Create a team to research the best approach for our caching layer:
- Teammate 1: Research Redis integration patterns
- Teammate 2: Research in-memory caching with LRU
- Teammate 3: Research CDN edge caching
Have them share findings and debate trade-offs.
```

### Pattern 5: Cross-Layer Changes

```
We need to add a "dark mode" feature. Spawn teammates for:
- Frontend: CSS variables, theme toggle component
- Backend: User preference storage and API
- Tests: E2E tests for theme switching
Coordinate so backend teammate shares the API contract first.
```

---

## Best Practices

### Give Teammates Enough Context

Teammates load CLAUDE.md but don't inherit conversation history. Include task-specific details in spawn prompts:

```
Spawn a security reviewer teammate with the prompt: "Review the authentication module
at src/auth/ for security vulnerabilities. Focus on token handling, session
management, and input validation. The app uses JWT tokens stored in
httpOnly cookies. Report any issues with severity ratings."
```

### Size Tasks Appropriately

| Size | Problem | Sweet Spot |
|------|---------|-----------|
| **Too small** | Coordination overhead exceeds benefit | -- |
| **Too large** | Teammates work too long without check-ins | -- |
| **Just right** | Self-contained, clear deliverable | A function, test file, or review |

**Tip**: Aim for 5-6 tasks per teammate to keep everyone productive.

### Avoid File Conflicts

Two teammates editing the same file leads to overwrites. Break work so each teammate owns different files:

```
# GOOD: Each teammate owns different files
Teammate A: src/auth/login.ts, src/auth/register.ts
Teammate B: src/auth/middleware.ts, src/auth/tokens.ts
Teammate C: tests/auth/*.test.ts

# BAD: Multiple teammates editing the same file
Teammate A: src/auth/index.ts (adding login)
Teammate B: src/auth/index.ts (adding register)  # CONFLICT!
```

### Use Delegate Mode

When you want the lead to **only coordinate** (not implement):
- Press **Shift+Tab** to cycle into delegate mode
- Lead is restricted to: spawning, messaging, shutting down teammates, managing tasks
- Prevents the lead from doing work instead of delegating

### Require Plan Approval for Risky Work

```
Spawn an architect teammate to refactor the authentication module.
Require plan approval before they make any changes.
Only approve plans that include test coverage.
```

### Enforce Quality with Hooks

Use hooks to enforce rules:
- **TeammateIdle**: Runs when a teammate is about to go idle. Exit code 2 sends feedback and keeps them working.
- **TaskCompleted**: Runs when a task is being marked complete. Exit code 2 prevents completion.

### Monitor Token Usage

Agent teams use **significantly more tokens** than single sessions. Each teammate is a separate Claude instance with its own context window.

| Use Case | Token Multiplier | Worth It? |
|----------|-----------------|-----------|
| Research/review | 3-5x | Usually yes |
| Feature development | 3-8x | Yes for independent modules |
| Debugging | 2-5x | Yes for complex bugs |
| Simple refactoring | 2-3x | Usually no (single session is better) |

---

## Agent Teams vs Subagents

### Comparison Table

| Feature | Subagents | Agent Teams |
|---------|-----------|-------------|
| **Context** | Own context; results return to caller | Own context; fully independent |
| **Communication** | Report results back to main agent only | Teammates message each other directly |
| **Coordination** | Main agent manages all work | Shared task list with self-coordination |
| **Best for** | Focused tasks where only the result matters | Complex work requiring discussion |
| **Token cost** | Lower (results summarized back) | Higher (each teammate is separate Claude) |
| **Complexity** | Simple (spawn, wait, get result) | Complex (team management, messaging) |

### Decision Guide

```
Is the task parallelizable?
├── No → Use single session
└── Yes → Do workers need to talk to each other?
    ├── No → Use subagents (cheaper, simpler)
    └── Yes → Use agent teams
        └── Is the extra token cost worth it?
            ├── No → Use subagents with lead coordination
            └── Yes → Use agent teams
```

---

## Claude-Flow (Third-Party)

### Overview

**claude-flow** is a third-party agent orchestration platform for Claude. It existed before Anthropic's official TeammateTool and provides additional capabilities.

- **Source**: [github.com/ruvnet/claude-flow](https://github.com/ruvnet/claude-flow)
- **Description**: "The leading agent orchestration platform for Claude"
- **License**: Open source

### Features

| Feature | Description |
|---------|-------------|
| **Multi-agent swarms** | Deploy intelligent agent swarms |
| **Autonomous workflows** | Coordinate autonomous agent workflows |
| **Distributed intelligence** | Swarm intelligence patterns |
| **RAG integration** | Retrieval-augmented generation |
| **MCP protocol** | Native Claude Code support via MCP |
| **Enterprise architecture** | Production-grade design patterns |

### When to Use Claude-Flow vs Official Agent Teams

| Use Case | claude-flow | Official Agent Teams |
|----------|-------------|---------------------|
| Simple parallel tasks | Overkill | Recommended |
| Complex orchestration patterns | Good fit | Limited |
| Custom coordination logic | Full control | Limited to TeammateTool |
| Production deployment | Designed for it | Experimental |
| MCP integration | Native support | Not specifically designed |
| Ease of use | Requires setup | Built into Claude Code |

---

## Other Multi-Agent Frameworks

### Agents (wshobson)

- **Source**: [github.com/wshobson/agents](https://github.com/wshobson/agents)
- **Purpose**: Intelligent automation and multi-agent orchestration for Claude Code
- **Features**: Custom agent patterns, task automation

### Anthropic's Multi-Agent Research System

Anthropic published details about how they built their own multi-agent research system:

- **Blog**: [anthropic.com/engineering/multi-agent-research-system](https://www.anthropic.com/engineering/multi-agent-research-system)
- **Architecture**: Multiple specialized agents coordinating on research tasks
- **Key insight**: Task decomposition + parallel execution + synthesis

### Anthropic's C Compiler Case Study

Anthropic demonstrated building a C compiler with a team of parallel Claudes:

- **Blog**: [anthropic.com/engineering/building-c-compiler](https://www.anthropic.com/engineering/building-c-compiler)
- **Approach**: Team lead broke the compiler into modules, teammates each built one
- **Result**: Demonstrated real-world viability of agent teams for complex software

### Programmatic Tool Calling

Anthropic's advanced tool use feature enables Claude to orchestrate tools through code:

- **Blog**: [anthropic.com/engineering/advanced-tool-use](https://www.anthropic.com/engineering/advanced-tool-use)
- **What it does**: Claude writes code that calls multiple tools, processes outputs, and controls what enters context
- **Relevance**: Foundation for multi-agent coordination at the API level

---

## Display Modes

### In-Process Mode (Default)

All teammates run inside the main terminal:
- **Navigation**: Shift+Up/Down to select a teammate
- **Messaging**: Type to send message to selected teammate
- **View session**: Press Enter to view a teammate's output
- **Interrupt**: Press Escape to interrupt a teammate's current turn
- **Task list**: Press Ctrl+T to toggle the task list
- **Works in**: Any terminal

### Split-Pane Mode

Each teammate gets its own terminal pane:
- **Requirements**: tmux or iTerm2
- **Navigation**: Click into a teammate's pane to interact
- **Advantage**: See all teammates' output simultaneously
- **macOS recommended**: Use `tmux -CC` in iTerm2

### Configuration

```json
// settings.json
{
  "teammateMode": "in-process"   // or "tmux" or "auto"
}
```

```bash
# Command line override
claude --teammate-mode in-process
```

### Setting Up Split Panes

#### tmux

```bash
# Install tmux
brew install tmux  # macOS

# Verify installation
which tmux
```

#### iTerm2

1. Install the `it2` CLI: [github.com/mkusaka/it2](https://github.com/mkusaka/it2)
2. Enable Python API: iTerm2 > Settings > General > Magic > Enable Python API

**Note**: Split-pane mode is NOT supported in VS Code's integrated terminal, Windows Terminal, or Ghostty.

---

## Limitations

### Current Limitations (Experimental)

| Limitation | Details |
|-----------|---------|
| **No session resumption** | `/resume` and `/rewind` don't restore in-process teammates |
| **Task status lag** | Teammates sometimes fail to mark tasks complete (blocking dependents) |
| **Slow shutdown** | Teammates finish current request/tool call before shutting down |
| **One team per session** | Lead can only manage one team at a time |
| **No nested teams** | Teammates cannot spawn their own teams |
| **Fixed lead** | Cannot promote teammate to lead or transfer leadership |
| **Permissions at spawn** | All teammates start with lead's permissions |
| **Split panes limited** | Requires tmux or iTerm2 (not VS Code terminal) |

### Workarounds

| Problem | Workaround |
|---------|-----------|
| Teammate doesn't mark task complete | Tell the lead to nudge the teammate |
| Lead implements instead of delegating | Use delegate mode (Shift+Tab) |
| Orphaned tmux sessions | `tmux ls` and `tmux kill-session -t <name>` |
| Too many permission prompts | Pre-approve common operations in permission settings |
| Teammate stops on error | Give additional instructions directly or spawn replacement |

---

## Resources

### Official Documentation

- [Agent Teams (Claude Code Docs)](https://code.claude.com/docs/en/agent-teams) -- **Primary reference**
- [Subagents (Claude Code Docs)](https://code.claude.com/docs/en/sub-agents) -- Lighter alternative
- [Settings (Claude Code Docs)](https://code.claude.com/docs/en/settings) -- Configuration
- [Hooks (Claude Code Docs)](https://code.claude.com/docs/en/hooks) -- Quality enforcement
- [Permissions (Claude Code Docs)](https://code.claude.com/docs/en/permissions) -- Access control

### Anthropic Engineering Blog

- [Introducing Claude Opus 4.6](https://www.anthropic.com/news/claude-opus-4-6)
- [Building a C Compiler with Parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
- [How We Built Our Multi-Agent Research System](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

### Community Resources

- [Claude Code Swarm Orchestration Skill (GitHub Gist)](https://gist.github.com/kieranklaassen/4f2aba89594a4aea4ad64d753984b2ea) -- Complete guide
- [Claude Code Multi-Agent Orchestration System (GitHub Gist)](https://gist.github.com/kieranklaassen/d2b35569be2c7f1412c64861a219d51f)
- [Claude Code's Hidden Multi-Agent System (paddo.dev)](https://paddo.dev/blog/claude-code-hidden-swarm/) -- Discovery story
- [Agent Teams: The Switch Got Flipped (paddo.dev)](https://paddo.dev/blog/agent-teams-the-switch-got-flipped/)
- [Claude Code Swarms (Addy Osmani)](https://addyosmani.com/blog/claude-code-agent-teams/)
- [What Is Claude Code Swarm Feature (Cyrus)](https://www.atcyrus.com/stories/what-is-claude-code-swarm-feature)

### News Coverage

- [Anthropic Releases Opus 4.6 (TechCrunch)](https://techcrunch.com/2026/02/05/anthropic-releases-opus-4-6-with-new-agent-teams/)
- [Claude Opus 4.6: 1M Token Context and Agent Teams (VentureBeat)](https://venturebeat.com/technology/anthropics-claude-opus-4-6-brings-1m-token-context-and-agent-teams-to-take)
- [Claude Code Multiple Agent Systems: Complete 2026 Guide (eesel.ai)](https://www.eesel.ai/blog/claude-code-multiple-agent-systems-complete-2026-guide)
- [GitHub Adds Claude Code to Agent HQ (WinBuzzer)](https://winbuzzer.com/2026/02/05/github-agent-hq-claude-codex-multi-agent-platform-xcxwbn/)

### Third-Party Frameworks

- [claude-flow (GitHub)](https://github.com/ruvnet/claude-flow) -- Agent orchestration platform
- [agents (GitHub)](https://github.com/wshobson/agents) -- Multi-agent automation for Claude Code
