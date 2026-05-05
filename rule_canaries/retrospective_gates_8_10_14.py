"""
Retrospective observational analysis of three more gates:

Gate 8 (Test Plan?):
    Pre-condition: a plan file exists at ~/.claude/plans/*.md
    Fire: the plan contains a "Test Plan" section/heading.
    Per-artifact analysis (not per-session — plans are durable).

Gate 10 (Plan Rigor?):
    Pre-condition: a non-trivial plan file exists (>100 lines).
    Fire: the plan contains P94/multi-perspective/propagation/challenger
    signatures per the rule's evidence-of-compliance requirement.
    Per-artifact.

Gate 14 (Trace Path?):
    Pre-condition: a session's user prompt contains bug-phrasing
    ("bug", "broken", "doesn't work", "no effect", "has no") AND the session
    later Edits a TS/JS/TSX/JSX file.
    Fire: a Grep tool_use appears BEFORE the first such Edit.
    Per-session.

No API calls.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
PLANS_DIR = Path.home() / ".claude" / "plans"
OUT_DIR = (
    Path(__file__).parent
    / "runs"
    / f"retrospective-gates-8-10-14-{time.strftime('%Y-%m-%d')}"
)
EXCLUDE_FILENAME_PREFIXES = ("agent-",)


# ─── Gate 8 + Gate 10 (per-artifact) ──────────────────────────────────────

TEST_PLAN_PATTERNS = [
    re.compile(r"^#{1,3}\s*Test Plan\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\*\*Test Plan\*\*", re.MULTILINE),
    re.compile(r"^Test Plan:", re.IGNORECASE | re.MULTILINE),
]

# Gate 10 "P94 / Plan Rigor" signatures
PLAN_RIGOR_PATTERNS = [
    re.compile(r"\bP94\b"),
    re.compile(r"multi-perspective review", re.IGNORECASE),
    re.compile(
        r"^#{1,3}\s*(CTO|Red Team|Quality|Architect)", re.IGNORECASE | re.MULTILINE
    ),
    re.compile(r"propagation map", re.IGNORECASE),
    re.compile(r"challenger", re.IGNORECASE),
    re.compile(r"meta-learning", re.IGNORECASE),
]


def analyze_plans() -> dict:
    """Gate 8 + Gate 10 per-artifact."""
    if not PLANS_DIR.exists():
        return {"error": f"{PLANS_DIR} not found"}

    plans = [p for p in PLANS_DIR.glob("*.md") if p.is_file()]
    n_plans = len(plans)
    non_trivial = [p for p in plans if p.stat().st_size > 3000]  # ~100+ lines

    gate8_fired = 0
    gate10_fired_count_dist: list[int] = []  # how many rigor signatures each plan has
    gate10_fired = 0

    for p in plans:
        try:
            text = p.read_text()
        except Exception:
            continue
        if any(rx.search(text) for rx in TEST_PLAN_PATTERNS):
            gate8_fired += 1
        hits = sum(1 for rx in PLAN_RIGOR_PATTERNS if rx.search(text))
        gate10_fired_count_dist.append(hits)
        if hits >= 2:  # at least 2 of 6 rigor signatures → "fired"
            gate10_fired += 1

    return {
        "n_plans_total": n_plans,
        "n_plans_non_trivial": len(non_trivial),
        "gate8_fired": gate8_fired,
        "gate10_fired": gate10_fired,
        "gate10_signature_dist": sorted(gate10_fired_count_dist, reverse=True),
    }


# ─── Gate 14 (per-session) ────────────────────────────────────────────────

BUG_PHRASE_PATTERN = re.compile(
    r"\b(bug|broken|doesn'?t work|has no effect|doesn'?t fire|not working|"
    r"no effect|stuck|doesn'?t do|why doesn'?t|nothing happens)\b",
    re.IGNORECASE,
)
UI_FILE_PATTERN = re.compile(r"\.(tsx|jsx|ts|js|css|scss)$", re.IGNORECASE)


def analyze_gate_14(jsonl_path: Path) -> dict:
    user_msgs_with_bug: list[int] = []  # event idx of bug prompts
    ui_edits: list[tuple[int, str]] = []
    greps: list[int] = []  # event idx of Grep tool uses
    event_idx = 0

    with jsonl_path.open() as f:
        for line in f:
            event_idx += 1
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = ev.get("type")
            if etype == "user":
                msg = ev.get("message", {})
                content = msg.get("content")
                text = content if isinstance(content, str) else ""
                if isinstance(content, list):
                    text = " ".join(
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                if BUG_PHRASE_PATTERN.search(text):
                    user_msgs_with_bug.append(event_idx)
            elif etype == "assistant":
                content = ev.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name")
                    inp = block.get("input", {})
                    if name in ("Edit", "Write"):
                        fp = inp.get("file_path")
                        if isinstance(fp, str) and UI_FILE_PATTERN.search(fp):
                            ui_edits.append((event_idx, fp))
                    elif name == "Grep":
                        greps.append(event_idx)

    # In scope: at least one bug prompt AND at least one UI-file edit
    if not user_msgs_with_bug or not ui_edits:
        return {"in_scope": False}

    # Fire: at least one Grep between the last bug prompt and the first UI edit
    last_bug = max(user_msgs_with_bug)
    first_edit = min(i for i, _ in ui_edits)
    # Alternate: at least one Grep anywhere between earliest bug prompt and first edit
    earliest_bug = min(user_msgs_with_bug)
    greps_in_window = [g for g in greps if earliest_bug <= g <= first_edit]
    return {
        "in_scope": True,
        "fired": bool(greps_in_window),
        "n_bug_prompts": len(user_msgs_with_bug),
        "n_ui_edits": len(ui_edits),
        "n_greps_in_window": len(greps_in_window),
    }


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# ─── Main ─────────────────────────────────────────────────────────────────


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Gates 8 and 10: per-artifact plan-file scan
    plan_stats = analyze_plans()
    if "error" in plan_stats:
        print(f"Gate 8/10: {plan_stats['error']}", file=sys.stderr)
        g8_rate = g10_rate = None
        g8_ci = g10_ci = (None, None)
        g8_k = g10_k = 0
        g8_n = g10_n = 0
    else:
        g8_k = plan_stats["gate8_fired"]
        g8_n = plan_stats["n_plans_total"]
        g8_rate = g8_k / max(1, g8_n)
        g8_ci = wilson_ci(g8_k, g8_n)
        g10_k = plan_stats["gate10_fired"]
        g10_n = plan_stats["n_plans_non_trivial"]
        g10_rate = g10_k / max(1, g10_n)
        g10_ci = wilson_ci(g10_k, g10_n)
        print(
            f"Gate 8 (Test Plan): {g8_k}/{g8_n} = {100 * g8_rate:.2f}% "
            f"[{100 * g8_ci[0]:.2f}, {100 * g8_ci[1]:.2f}]",
            file=sys.stderr,
        )
        print(
            f"Gate 10 (Plan Rigor): {g10_k}/{g10_n} = {100 * g10_rate:.2f}% "
            f"[{100 * g10_ci[0]:.2f}, {100 * g10_ci[1]:.2f}]",
            file=sys.stderr,
        )

    # Gate 14: per-session scan
    log_paths = [
        p
        for p in PROJECTS_DIR.rglob("*.jsonl")
        if not any(p.name.startswith(pref) for pref in EXCLUDE_FILENAME_PREFIXES)
    ]
    print(f"Gate 14: scanning {len(log_paths)} sessions...", file=sys.stderr)

    g14_scope = g14_fired = 0
    g14_per_session_path = OUT_DIR / "gate14_per_session.csv"
    with g14_per_session_path.open("w") as f:
        f.write("session,in_scope,fired,n_bug_prompts,n_ui_edits,n_greps\n")
        for i, p in enumerate(log_paths):
            if i and i % 1000 == 0:
                print(f"  scanned {i}; scope={g14_scope}", file=sys.stderr)
            try:
                r = analyze_gate_14(p)
            except Exception as exc:
                print(f"  err {p.name}: {exc}", file=sys.stderr)
                continue
            if r["in_scope"]:
                g14_scope += 1
                if r["fired"]:
                    g14_fired += 1
                f.write(
                    f"{p.name},True,{r['fired']},{r.get('n_bug_prompts', 0)},"
                    f"{r.get('n_ui_edits', 0)},{r.get('n_greps_in_window', 0)}\n"
                )

    g14_rate = g14_fired / max(1, g14_scope)
    g14_ci = wilson_ci(g14_fired, g14_scope)
    print(
        f"Gate 14 (Trace Path): {g14_fired}/{g14_scope} = {100 * g14_rate:.2f}% "
        f"[{100 * g14_ci[0]:.2f}, {100 * g14_ci[1]:.2f}]",
        file=sys.stderr,
    )

    # Report
    lines: list[str] = []
    lines.append(
        "# Retrospective: Gates 8 (Test Plan) + 10 (Plan Rigor) + 14 (Trace Path)"
    )
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Gate | Scope | Fired | Rate | 95% CI |")
    lines.append("|---|---|---|---|---|")
    if g8_rate is not None:
        lines.append(
            f"| Gate 8 (Test Plan section in plan files) | {g8_n} plans | {g8_k} | {100 * g8_rate:.2f}% | [{100 * g8_ci[0]:.2f}, {100 * g8_ci[1]:.2f}] |"
        )
        lines.append(
            f"| Gate 10 (P94 rigor markers, ≥2 of 6) | {g10_n} non-trivial plans | {g10_k} | {100 * g10_rate:.2f}% | [{100 * g10_ci[0]:.2f}, {100 * g10_ci[1]:.2f}] |"
        )
    lines.append(
        f"| Gate 14 (Grep before UI Edit after bug prompt) | {g14_scope} sessions | {g14_fired} | {100 * g14_rate:.2f}% | [{100 * g14_ci[0]:.2f}, {100 * g14_ci[1]:.2f}] |"
    )
    lines.append("")
    lines.append("## Operational definitions")
    lines.append("")
    lines.append(
        "**Gate 8:** scans every `*.md` file under `~/.claude/plans/`. Fires if file contains a Test Plan section (`# Test Plan`, `**Test Plan**`, or `Test Plan:`)."
    )
    lines.append("")
    lines.append(
        "**Gate 10:** scans non-trivial (>3 KB) plan files. Fires if ≥2 of these markers present: `P94`, 'multi-perspective review', a CTO/Red Team/Quality/Architect section heading, 'propagation map', 'challenger', 'meta-learning'."
    )
    lines.append("")
    lines.append(
        "**Gate 14:** per-session. In scope if user prompt contains bug-phrase (`bug`, `broken`, `doesn't work`, `no effect`, `not working`) AND session later Edits a `.ts/.tsx/.js/.jsx/.css` file. Fires if a `Grep` tool_use appears between the earliest bug prompt and the first UI-file Edit."
    )
    lines.append("")
    if plan_stats and "gate10_signature_dist" in plan_stats:
        dist = plan_stats["gate10_signature_dist"]
        lines.append("## Plan rigor signature distribution (all non-trivial plans)")
        lines.append("")
        lines.append("```")
        from collections import Counter

        for count, freq in sorted(Counter(dist).items()):
            lines.append(f"  {count} markers: {freq} plans")
        lines.append("```")
        lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- Gate 8 per-artifact: plan files accumulated over time; rate = fraction of all plans ever written that included a Test Plan section"
    )
    lines.append(
        "- Gate 10 ≥2-of-6 threshold is arbitrary; higher thresholds would lower rate"
    )
    lines.append(
        "- Gate 14 bug-phrase regex may false-positive (`buggy` mentioned in passing)"
    )
    lines.append(
        "- Gate 14 grep-between-window is strict — a Grep just after the first Edit wouldn't count"
    )
    lines.append("")

    (OUT_DIR / "report.md").write_text("\n".join(lines))
    print(f"\nReport: {OUT_DIR / 'report.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
