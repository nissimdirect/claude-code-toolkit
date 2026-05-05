"""Shared scaffolding for retrospective gate analyses.

Pattern: a gate detector walks every Claude Code session JSONL, identifies
TRIGGER events (situations the gate is supposed to govern), and for each
checks whether COMPLIANCE was achieved. The library handles:

- Session log discovery + 90-day window filter
- Per-event iteration with tool_use / user-prompt / assistant-text extractors
- Aggregation (pooled rate, per-session distribution, by-project breakdown)
- Report rendering with strict/lenient bands + caveats + ASCII histogram

Each detector implements two pure functions:
    triggers(turns) -> Iterator[trigger_dict]
    is_compliant_strict(trigger, turns) -> bool
    is_compliant_lenient(trigger, turns) -> bool

`turns` is a list of dicts with normalized shape (see iter_session_turns).

Per pre-registration discipline (lessons from prose-rule-observability v1
retractions): always report STRICT and LENIENT bands. Never publish a
single-number rate without sensitivity analysis.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, stdev
from typing import Any

PROJECTS_DIR = Path.home() / ".claude" / "projects"
DEFAULT_DAYS_BACK = 90
EXCLUDE_FILENAME_PREFIXES = ("agent-",)


# ---------------------------------------------------------------------------
# Session iteration
# ---------------------------------------------------------------------------


@dataclass
class Turn:
    """Normalized session-event shape.

    Each turn has ONE of: user_prompt (str), assistant_text (str), or
    tool_use (dict with name + input). tool_result is captured separately.
    """

    idx: int  # position in the session (0-based)
    role: str  # "user" | "assistant" | "tool_result"
    user_prompt: str | None = None  # user prompts only (free-text, not tool_result)
    assistant_text: str | None = None  # text blocks emitted by assistant
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_id: str | None = None
    tool_result_for: str | None = None  # tool_use_id this is a result for
    tool_result_text: str | None = None
    raw_event: dict[str, Any] = field(default_factory=dict)


def discover_session_logs(days_back: int = DEFAULT_DAYS_BACK) -> list[Path]:
    """Return all session JSONL paths within the window, agent-* excluded."""
    if not PROJECTS_DIR.exists():
        return []
    cutoff_ts = time.time() - (days_back * 86_400)
    return [
        p
        for p in PROJECTS_DIR.rglob("*.jsonl")
        if p.stat().st_mtime >= cutoff_ts
        and not any(p.name.startswith(pref) for pref in EXCLUDE_FILENAME_PREFIXES)
    ]


def iter_session_turns(jsonl_path: Path) -> tuple[list[Turn], dict[str, Any]]:
    """Parse one session log into a list of normalized turns + metadata.

    Each user prompt, assistant text block, and tool_use becomes its own Turn.
    tool_result blocks (which arrive as user-role events but contain results,
    not free-text user prompts) are captured as role="tool_result" turns.

    metadata: cwd (first non-null), model (first non-null assistant model)
    """
    turns: list[Turn] = []
    cwd_seen: str | None = None
    model_seen: str | None = None
    idx = 0

    try:
        with jsonl_path.open() as f:
            for line in f:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if cwd_seen is None:
                    cwd_seen = event.get("cwd")

                etype = event.get("type")
                msg = (
                    event.get("message", {})
                    if isinstance(event.get("message"), dict)
                    else {}
                )

                if etype == "assistant":
                    if model_seen is None:
                        model_seen = msg.get("model")
                    content = msg.get("content", [])
                    if isinstance(content, str):
                        turns.append(
                            Turn(
                                idx=idx,
                                role="assistant",
                                assistant_text=content,
                                raw_event=event,
                            )
                        )
                        idx += 1
                        continue
                    if not isinstance(content, list):
                        continue
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "text":
                            text = block.get("text", "")
                            if isinstance(text, str) and text:
                                turns.append(
                                    Turn(
                                        idx=idx,
                                        role="assistant",
                                        assistant_text=text,
                                        raw_event=event,
                                    )
                                )
                                idx += 1
                        elif btype == "tool_use":
                            turns.append(
                                Turn(
                                    idx=idx,
                                    role="assistant",
                                    tool_name=block.get("name"),
                                    tool_input=block.get("input") or {},
                                    tool_id=block.get("id"),
                                    raw_event=event,
                                )
                            )
                            idx += 1
                elif etype == "user":
                    content = msg.get("content", "")
                    # User prompts may be string or list of blocks
                    if isinstance(content, str):
                        if content.strip():
                            turns.append(
                                Turn(
                                    idx=idx,
                                    role="user",
                                    user_prompt=content,
                                    raw_event=event,
                                )
                            )
                            idx += 1
                    elif isinstance(content, list):
                        # Could be tool_result blocks or text blocks
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            btype = block.get("type")
                            if btype == "tool_result":
                                # Capture text result if string
                                rcontent = block.get("content", "")
                                if isinstance(rcontent, list):
                                    rcontent = " ".join(
                                        b.get("text", "")
                                        for b in rcontent
                                        if isinstance(b, dict)
                                        and b.get("type") == "text"
                                    )
                                turns.append(
                                    Turn(
                                        idx=idx,
                                        role="tool_result",
                                        tool_result_for=block.get("tool_use_id"),
                                        tool_result_text=str(rcontent)[:4000],
                                        raw_event=event,
                                    )
                                )
                                idx += 1
                            elif btype == "text":
                                text = block.get("text", "")
                                if isinstance(text, str) and text.strip():
                                    turns.append(
                                        Turn(
                                            idx=idx,
                                            role="user",
                                            user_prompt=text,
                                            raw_event=event,
                                        )
                                    )
                                    idx += 1
    except OSError:
        pass

    return turns, {
        "session_file": jsonl_path.name,
        "cwd": cwd_seen,
        "model": model_seen,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def cwd_to_project(cwd: str | None) -> str:
    """Map a working directory to a project name for grouping."""
    if not cwd:
        return "(unknown)"
    if "/Development/" in cwd:
        after = cwd.split("/Development/", 1)[1]
        return after.split("/", 1)[0]
    if cwd.endswith("/nissimagent") or cwd.endswith("/.claude"):
        return "(home)"
    return re.sub(r"^/Users/[^/]+/", "", cwd).split("/", 1)[0] or "(other)"


# Agent-invocation prompt detection. The session log dir contains both
# real user prompts AND queue-submitted automation prompts (PR-review jobs,
# subagent task specs, scheduled scrapes). The latter look like system prompts
# ("You are a strict code linter...") and should not be counted as real user
# requests when measuring user-facing gates.
_AGENT_INVOCATION_PATTERNS = [
    r"^You are an?\b",
    r"^Your task is\b",
    r"\bReview this (?:diff|PR|pull request|code|file|change)\b",
    r"^# (?:Task|Context|Mission|Role|Objective)\b",
    r"\b(?:strict|brutal|harsh|rigorous)(?:ly)?\s+(?:code\s+)?(?:linter|reviewer|critic|auditor)\b",
    r"\bOutput exactly\b",  # rigid-format machine-task signal
    r"\bFor each (?:file|issue|item):\s+\w+:\w+\b",  # FILENAME:LINE - DESC pattern
]
_AGENT_INVOCATION_RE = re.compile(
    "|".join(_AGENT_INVOCATION_PATTERNS), re.IGNORECASE | re.MULTILINE
)


def is_agent_invocation_prompt(text: str | None) -> bool:
    """Heuristic: does this 'user prompt' look like an automated task spec?

    Used to filter queue-driven sessions (PR-review jobs, scheduled scrapes,
    subagent invocations) from gate measurements that should only count real
    user requests.

    Returns True for clear automation; False for normal interactive prompts.
    Conservative — false negatives (real user prompts misclassified) are worse
    than false positives (automation prompts counted as real).
    """
    if not text:
        return False
    snippet = text.lstrip()[:1500]
    return bool(_AGENT_INVOCATION_RE.search(snippet))


def is_real_user_prompt(turn: "Turn") -> bool:
    """True if turn is a user prompt that looks interactive, not automated."""
    if turn.role != "user" or not turn.user_prompt:
        return False
    return not is_agent_invocation_prompt(turn.user_prompt)


def histogram_ascii(rates: list[float], width: int = 40) -> list[str]:
    """Render an ASCII histogram of rates [0..1] in 10pp bins."""
    bins = [0] * 10
    for r in rates:
        idx = min(9, int(r * 10))
        bins[idx] += 1
    max_bin = max(bins) or 1
    lines = []
    for i, count in enumerate(bins):
        bar = "█" * int(width * count / max_bin)
        lines.append(f"[{i * 10:>3}-{(i + 1) * 10:>3}%]  {count:>6}  {bar}")
    return lines


# ---------------------------------------------------------------------------
# Detector spec + runner
# ---------------------------------------------------------------------------


@dataclass
class GateSpec:
    """Configuration for one retrospective gate analysis."""

    gate_id: str  # e.g. "Gate 6"
    title: str  # e.g. "Reproduce-First (bug-fix → Bash before Edit)"
    strict_definition: str  # short description shown in report
    lenient_definition: str
    triggers: Callable[[list[Turn]], Iterator[dict[str, Any]]]
    is_compliant_strict: Callable[[dict[str, Any], list[Turn]], bool]
    is_compliant_lenient: Callable[[dict[str, Any], list[Turn]], bool]
    caveats: list[str] = field(default_factory=list)


def run_gate_analysis(
    spec: GateSpec,
    out_dir: Path,
    days_back: int = DEFAULT_DAYS_BACK,
    max_sessions: int | None = None,
) -> dict[str, Any]:
    """Walk all sessions, apply spec, write report + CSV, return summary."""
    log_paths = discover_session_logs(days_back)
    if max_sessions:
        log_paths = log_paths[:max_sessions]

    out_dir.mkdir(parents=True, exist_ok=True)
    per_session_csv = out_dir / "per_session.csv"
    per_trigger_jsonl = out_dir / "per_trigger.jsonl"

    total_triggers = 0
    total_compliant_strict = 0
    total_compliant_lenient = 0
    by_project_rates_strict: dict[str, list[float]] = defaultdict(list)
    by_project_sessions: dict[str, int] = defaultdict(int)
    session_rates_strict: list[float] = []
    session_rates_lenient: list[float] = []
    sessions_with_triggers = 0

    with per_session_csv.open("w") as scsv, per_trigger_jsonl.open("w") as tjsonl:
        scsv.write(
            "session_file,cwd,project,model,n_triggers,n_compliant_strict,"
            "n_compliant_lenient,strict_rate,lenient_rate\n"
        )
        for i, p in enumerate(log_paths):
            if i and i % 500 == 0:
                print(
                    f"  scanned {i}/{len(log_paths)}; triggers so far: {total_triggers}"
                )
            try:
                turns, meta = iter_session_turns(p)
            except Exception as exc:
                print(f"  parse error {p.name}: {exc}")
                continue

            triggers = list(spec.triggers(turns))
            if not triggers:
                continue

            sessions_with_triggers += 1
            n_strict = sum(1 for t in triggers if spec.is_compliant_strict(t, turns))
            n_lenient = sum(1 for t in triggers if spec.is_compliant_lenient(t, turns))
            n_trig = len(triggers)
            total_triggers += n_trig
            total_compliant_strict += n_strict
            total_compliant_lenient += n_lenient

            project = cwd_to_project(meta["cwd"])
            strict_rate = n_strict / n_trig
            lenient_rate = n_lenient / n_trig
            session_rates_strict.append(strict_rate)
            session_rates_lenient.append(lenient_rate)
            by_project_rates_strict[project].append(strict_rate)
            by_project_sessions[project] += 1

            scsv.write(
                f"{meta['session_file']},"
                f"{(meta['cwd'] or '').replace(',', '_')},"
                f"{project},{meta['model'] or ''},"
                f"{n_trig},{n_strict},{n_lenient},"
                f"{strict_rate:.4f},{lenient_rate:.4f}\n"
            )
            for t in triggers:
                tjsonl.write(
                    json.dumps({**t, "session": meta["session_file"]}, default=str)
                    + "\n"
                )

    pool_strict = total_compliant_strict / max(1, total_triggers)
    pool_lenient = total_compliant_lenient / max(1, total_triggers)

    summary = {
        "gate_id": spec.gate_id,
        "title": spec.title,
        "n_sessions_scanned": len(log_paths),
        "n_sessions_with_triggers": sessions_with_triggers,
        "n_triggers": total_triggers,
        "n_compliant_strict": total_compliant_strict,
        "n_compliant_lenient": total_compliant_lenient,
        "pool_strict": pool_strict,
        "pool_lenient": pool_lenient,
        "session_rates_strict": session_rates_strict,
        "session_rates_lenient": session_rates_lenient,
        "by_project_rates_strict": dict(by_project_rates_strict),
        "by_project_sessions": dict(by_project_sessions),
    }

    report_path = out_dir / "report.md"
    report_path.write_text(render_report(spec, summary))
    print(f"\nReport: {report_path}")
    print(f"Per-session CSV: {per_session_csv}")
    print(f"Per-trigger JSONL: {per_trigger_jsonl}")
    return summary


def render_report(spec: GateSpec, s: dict[str, Any]) -> str:
    """Render the markdown report from a summary dict."""
    lines: list[str] = []
    lines.append(f"# Retrospective {spec.gate_id} Analysis — {spec.title}")
    lines.append("")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Window:** last {DEFAULT_DAYS_BACK} days")
    lines.append("**Source:** `~/.claude/projects/**/*.jsonl` (agent-* excluded)")
    lines.append("")
    lines.append("## Detector definitions")
    lines.append("")
    lines.append(f"- **Strict:** {spec.strict_definition}")
    lines.append(f"- **Lenient:** {spec.lenient_definition}")
    lines.append("")
    lines.append("## Headline numbers")
    lines.append("")
    lines.append(f"- Session logs scanned: **{s['n_sessions_scanned']:,}**")
    lines.append(f"- Sessions with ≥1 trigger: **{s['n_sessions_with_triggers']:,}**")
    lines.append(f"- Total triggers: **{s['n_triggers']:,}**")
    lines.append("")
    lines.append(
        f"## Pooled compliance — **strict: {100 * s['pool_strict']:.2f}%** "
        f"| **lenient: {100 * s['pool_lenient']:.2f}%**"
    )
    lines.append("")
    spread = 100 * (s["pool_lenient"] - s["pool_strict"])
    lines.append(
        f"- Strict/lenient spread: **{spread:+.2f} percentage points** "
        f"({_band_quality(spread)})"
    )
    lines.append("")

    rates = s["session_rates_strict"]
    if rates:
        lines.append("## Per-session strict-rate distribution")
        lines.append("")
        lines.append(f"- Sessions with triggers: {len(rates):,}")
        lines.append(f"- Mean: {mean(rates):.4f}  Median: {median(rates):.4f}")
        if len(rates) > 1:
            lines.append(f"- Std dev: {stdev(rates):.4f}")
        lines.append(
            f"- Sessions with 100% compliance: {sum(1 for r in rates if r == 1.0)}"
            f" ({100 * sum(1 for r in rates if r == 1.0) / len(rates):.1f}%)"
        )
        lines.append(
            f"- Sessions with 0% compliance: {sum(1 for r in rates if r == 0.0)}"
            f" ({100 * sum(1 for r in rates if r == 0.0) / len(rates):.1f}%)"
        )
        lines.append("")
        lines.append("### Rate histogram (sessions per 10pp bin, strict)")
        lines.append("")
        lines.append("```")
        lines.extend(histogram_ascii(rates))
        lines.append("```")
        lines.append("")

    by_proj = s["by_project_rates_strict"]
    if by_proj:
        lines.append("## By project (top 15 by session count)")
        lines.append("")
        lines.append("| Project | Sessions | Mean strict rate |")
        lines.append("|---|---|---|")
        for project in sorted(by_proj, key=lambda k: -s["by_project_sessions"][k])[:15]:
            r = by_proj[project]
            lines.append(
                f"| {project} | {s['by_project_sessions'][project]} | {mean(r):.4f} |"
            )
        lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- **Not causal.** Gate was present in every session — this is a "
        "descriptive baseline, not an effect estimate."
    )
    lines.append(
        "- **Detector choice matters.** The strict/lenient spread is the "
        "sensitivity range; pick the band that matches your enforcement intent."
    )
    for c in spec.caveats:
        lines.append(f"- {c}")
    lines.append("")
    return "\n".join(lines)


def _band_quality(spread_pp: float) -> str:
    if abs(spread_pp) < 5:
        return "robust — definition stable"
    if abs(spread_pp) < 20:
        return "moderate — minor definition sensitivity"
    if abs(spread_pp) < 50:
        return "wide — meaningful definition sensitivity"
    return "very wide — interpretation-dependent, treat single number as misleading"
