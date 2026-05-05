"""Gate 6 (Reproduce-First) retrospective analysis.

Trigger: user prompt contains a bug-fix phrase (same regex used by the runtime
hook reproduce_first_check.py).

Strict: the FIRST tool_use in the next assistant turn after the trigger is Bash.
Lenient: any Bash tool_use occurs after the trigger AND before the first
Edit/Write/MultiEdit in the same session window.

The session window for compliance: from the trigger to the next user prompt
(or end of session). This bounds the check to the assistant's response to the
specific bug-fix request.

Per pre-registration discipline (lessons from prose-rule v1 retractions):
both bands are reported. Single-number rates are misleading.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from retrospective_lib import GateSpec, Turn, is_real_user_prompt, run_gate_analysis

OUT_DIR = (
    Path(__file__).parent / "runs" / f"retrospective-gate6-{time.strftime('%Y-%m-%d')}"
)

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# Bug-fix trigger patterns — same as runtime hook.
BUG_FIX_TRIGGERS = [
    r"\bfix\s+(?:the|this|a|that)\s+bug\b",
    r"\bfix\s+(?:the|this|a|that)\s+error\b",
    r"\bdebug\s+(?:this|that|the)\b",
    r"\bwhy\s+(?:is|does|isn't|doesn't)\s+\w+\s+(?:broken|failing|crashing|erroring)\b",
    r"\b(?:it|this|that)['\s]+(?:not\s+working|broken|crashing|failing)\b",
    r"\b(?:can you|please)\s+fix\b",
    r"\b\w+\s+is\s+(?:broken|crashing|throwing|erroring)\b",
    r"\bgetting\s+(?:an?\s+)?(?:error|exception|crash)\b",
    r"\bsegfault\b",
    r"\btraceback\b",
]
TRIGGER_RE = re.compile("|".join(BUG_FIX_TRIGGERS), re.IGNORECASE)


def _window_after_trigger(trigger_idx: int, turns: list[Turn]) -> list[Turn]:
    """Return turns from after the trigger up to the next user prompt."""
    out: list[Turn] = []
    for t in turns:
        if t.idx <= trigger_idx:
            continue
        if t.role == "user" and t.user_prompt:
            break
        out.append(t)
    return out


def triggers(turns: list[Turn]) -> Iterator[dict[str, Any]]:
    for t in turns:
        if not is_real_user_prompt(t):
            continue
        m = TRIGGER_RE.search(t.user_prompt or "")
        if m:
            yield {
                "trigger_idx": t.idx,
                "trigger_phrase": m.group(0)[:80],
                "prompt_snippet": (t.user_prompt or "")[:160].replace("\n", " "),
            }


def is_compliant_strict(trigger: dict[str, Any], turns: list[Turn]) -> bool:
    """First tool_use after trigger must be Bash."""
    window = _window_after_trigger(trigger["trigger_idx"], turns)
    for t in window:
        if t.tool_name:
            return t.tool_name == "Bash"
    return False  # no tool use at all → not compliant


def is_compliant_lenient(trigger: dict[str, Any], turns: list[Turn]) -> bool:
    """Some Bash call must occur before any Edit/Write in the window."""
    window = _window_after_trigger(trigger["trigger_idx"], turns)
    for t in window:
        if t.tool_name == "Bash":
            return True
        if t.tool_name in EDIT_TOOLS:
            return False
    return False


SPEC = GateSpec(
    gate_id="Gate 6",
    title="Reproduce-First (bug-fix prompt → Bash before Edit)",
    strict_definition=(
        "The FIRST tool_use after a bug-fix prompt is Bash. "
        "Window: until next user prompt."
    ),
    lenient_definition=(
        "Any Bash call occurs before any Edit/Write/MultiEdit in the window."
    ),
    triggers=triggers,
    is_compliant_strict=is_compliant_strict,
    is_compliant_lenient=is_compliant_lenient,
    caveats=[
        "Trigger regex matches the runtime hook — same precision/recall envelope. "
        "False positives possible on metaphorical 'broken' / 'fix' usage.",
        "Sessions where the bug fix doesn't require running code (pure prose / docs / "
        "obvious typo) will count as non-compliant under strict but the rule arguably "
        "doesn't apply — interpret with judgment.",
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
