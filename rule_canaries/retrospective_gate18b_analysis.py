"""Gate 18b (Branch HEAD Check) retrospective analysis.

Trigger: assistant text contains a "ready to merge" / "session close" /
"all green" / "open a PR" / "pushed" / "ready to ship" declaration.

Strict: a `git branch --show-current` (or `git log -1` against origin) Bash
call appeared in the last N=5 tool calls before the trigger.
Lenient: any branch-state-checking Bash call (git branch / git log / git
status) appeared anywhere earlier in the same session.

Only sessions that include a multi-session-eligible repo (i.e. some commit /
push activity) are counted — this is the population the rule is supposed
to govern.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from retrospective_lib import GateSpec, Turn, run_gate_analysis

OUT_DIR = (
    Path(__file__).parent
    / "runs"
    / f"retrospective-gate18b-{time.strftime('%Y-%m-%d')}"
)

# "Ready" claim patterns — assistant declarations where Gate 18b applies.
READY_TRIGGERS = [
    r"\bready\s+to\s+merge\b",
    r"\bready\s+to\s+ship\b",
    r"\bready\s+to\s+test\b",
    r"\ball\s+green\b",
    r"\bopen(?:ed)?\s+(?:a\s+)?PR\b",
    r"\bpushed\b",
    r"\bsession[-\s]close\b",
    r"\bmerge[-\s]ready\b",
]
TRIGGER_RE = re.compile("|".join(READY_TRIGGERS), re.IGNORECASE)

# Strict: branch-show-current
STRICT_BASH_PATTERNS = [
    r"git\s+branch\s+--show-current",
    r"git\s+log\s+.*origin/",
]
STRICT_BASH_RE = re.compile("|".join(STRICT_BASH_PATTERNS), re.IGNORECASE)

# Lenient: any branch-state inquiry
LENIENT_BASH_PATTERNS = [
    r"git\s+branch\b",
    r"git\s+log\b",
    r"git\s+status\b",
    r"git\s+rev-parse\b",
    r"git\s+show-ref\b",
]
LENIENT_BASH_RE = re.compile("|".join(LENIENT_BASH_PATTERNS), re.IGNORECASE)

STRICT_LOOKBACK = 5  # Look back at last N tool calls before trigger


def _bash_command(t: Turn) -> str:
    if t.tool_name != "Bash":
        return ""
    inp = t.tool_input or {}
    return str(inp.get("command", ""))


def triggers(turns: list[Turn]) -> Iterator[dict[str, Any]]:
    # Only fire if the session has any git activity at all (otherwise
    # Gate 18b doesn't apply — there's no branch state to verify).
    has_git = any(
        "git" in _bash_command(t).lower() for t in turns if t.tool_name == "Bash"
    )
    if not has_git:
        return

    for t in turns:
        if t.role != "assistant" or not t.assistant_text:
            continue
        m = TRIGGER_RE.search(t.assistant_text)
        if m:
            yield {
                "trigger_idx": t.idx,
                "trigger_phrase": m.group(0)[:80],
                "text_snippet": t.assistant_text[:160].replace("\n", " "),
            }


def is_compliant_strict(trigger: dict[str, Any], turns: list[Turn]) -> bool:
    """A strict branch-check Bash call within the last STRICT_LOOKBACK tool uses."""
    bash_calls_before: list[str] = []
    for t in turns:
        if t.idx >= trigger["trigger_idx"]:
            break
        if t.tool_name:
            cmd = _bash_command(t)
            if cmd:
                bash_calls_before.append(cmd)
            else:
                bash_calls_before.append("")  # non-bash tool — counts toward lookback
    recent = bash_calls_before[-STRICT_LOOKBACK:]
    return any(STRICT_BASH_RE.search(c) for c in recent if c)


def is_compliant_lenient(trigger: dict[str, Any], turns: list[Turn]) -> bool:
    """Any branch-state-checking bash call earlier in session."""
    for t in turns:
        if t.idx >= trigger["trigger_idx"]:
            break
        cmd = _bash_command(t)
        if cmd and LENIENT_BASH_RE.search(cmd):
            return True
    return False


SPEC = GateSpec(
    gate_id="Gate 18b",
    title="Branch HEAD Check (before declaring 'ready')",
    strict_definition=(
        "A `git branch --show-current` or `git log origin/...` Bash call "
        f"appears in the last {STRICT_LOOKBACK} tool calls before a 'ready' declaration."
    ),
    lenient_definition=(
        "Any branch-state-inquiry Bash call (git branch / log / status / "
        "rev-parse / show-ref) appears anywhere earlier in the session."
    ),
    triggers=triggers,
    is_compliant_strict=is_compliant_strict,
    is_compliant_lenient=is_compliant_lenient,
    caveats=[
        "Population restricted to sessions with any git activity — sessions with "
        "no git involvement are excluded since the gate has no purchase there.",
        "'pushed' may catch innocuous mentions ('I pushed earlier in this session') "
        "outside merge-ready context. Strict band tightens this; lenient overcounts.",
        "Single-session repos don't need this gate per CLAUDE.md — but we count them "
        "anyway because we can't easily detect parallel-session-active repos retrospectively.",
    ],
)


if __name__ == "__main__":
    summary = run_gate_analysis(SPEC, OUT_DIR)
    print(
        f"\n{SPEC.gate_id}: strict={100 * summary['pool_strict']:.2f}%  "
        f"lenient={100 * summary['pool_lenient']:.2f}%  "
        f"(n={summary['n_triggers']})"
    )
    sys.exit(0)
