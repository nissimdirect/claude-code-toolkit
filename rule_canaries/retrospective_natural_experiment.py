"""
Natural-experiment analysis: compliance rate across three eras of CLAUDE.md.

Era A (baseline):       before 2026-02-14 16:17 CT — neither Gate 2 nor Core Rule 1
Era B (Gate 2 only):    2026-02-14 16:17 → 2026-02-22 01:20 CT — Gate 2 added
Era C (both rules):     after 2026-02-22 01:20 CT — Core Rule 1 added too

Source dates verified from git log on ~/.claude/CLAUDE.md:
  b8fca39 2026-02-14 16:17:18 -0600 — "about to edit a file" (Gate 2) introduced
  8c70253 2026-02-22 01:20:55 -0600 — "Read before Edit" (Core Rule 1) introduced

For each session log, read the FIRST event's timestamp to determine era.
Compute compliance rate per era with Wilson 95% CIs. Compare Era A vs B,
B vs C, A vs C.

CAVEATS (acknowledged, not fully controlled):
  - Other CLAUDE.md changes in the windows
  - Possible model-version shifts
  - Task/project distribution may shift over time
  - Era B is only 8 days — small sample
  - Log retention may not extend back to Era A depending on system
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

PROJECTS_DIR = Path.home() / ".claude" / "projects"
EXCLUDE_FILENAME_PREFIXES = ("agent-",)
OUT_DIR = (
    Path(__file__).parent / "runs" / f"natural-experiment-{time.strftime('%Y-%m-%d')}"
)

# From git log — ISO 8601 with TZ offset, converted to UTC
GATE_2_ADDED_UTC = datetime(
    2026, 2, 14, 22, 17, 18, tzinfo=timezone.utc
)  # 16:17 CT = 22:17 UTC
CORE_RULE_1_ADDED_UTC = datetime(
    2026, 2, 22, 7, 20, 55, tzinfo=timezone.utc
)  # 01:20 CT = 07:20 UTC


def classify_era(session_start_iso: str) -> str | None:
    try:
        ts = datetime.fromisoformat(session_start_iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if ts < GATE_2_ADDED_UTC:
        return "A_baseline"
    if ts < CORE_RULE_1_ADDED_UTC:
        return "B_gate2_only"
    return "C_both"


def analyze_session(jsonl_path: Path) -> dict | None:
    reads_by_file: set[str] = set()
    writes_by_file: set[str] = set()
    edits: list[dict] = []
    session_start_iso: str | None = None
    model_seen: str | None = None

    with jsonl_path.open() as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if session_start_iso is None:
                ts = event.get("timestamp")
                if isinstance(ts, str):
                    session_start_iso = ts

            if event.get("type") != "assistant":
                continue
            msg = event.get("message", {})
            if model_seen is None:
                model_seen = msg.get("model")
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name")
                inp = block.get("input", {})
                if name == "Read":
                    fp = inp.get("file_path")
                    if isinstance(fp, str):
                        reads_by_file.add(fp)
                elif name == "Write":
                    fp = inp.get("file_path")
                    if isinstance(fp, str):
                        writes_by_file.add(fp)
                elif name == "Edit":
                    fp = inp.get("file_path")
                    if not isinstance(fp, str):
                        continue
                    edits.append(
                        {
                            "file_path": fp,
                            "prior_read": fp in reads_by_file,
                            "prior_write": fp in writes_by_file,
                        }
                    )

    if not edits:
        return None

    era = classify_era(session_start_iso) if session_start_iso else None
    return {
        "session_file": jsonl_path.name,
        "session_start": session_start_iso,
        "era": era,
        "model": model_seen,
        "n_edits": len(edits),
        "n_strict_fired": sum(1 for e in edits if e["prior_read"]),
        "n_lenient_fired": sum(1 for e in edits if e["prior_read"] or e["prior_write"]),
    }


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def two_proportion_test(k1: int, n1: int, k2: int, n2: int) -> dict:
    import math

    if n1 == 0 or n2 == 0:
        return {"delta": None, "z": None, "p": None, "ci_low": None, "ci_high": None}
    p1, p2 = k1 / n1, k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    se_pool = (p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)) ** 0.5
    z = (p1 - p2) / se_pool if se_pool > 0 else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    se = (p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2) ** 0.5
    return {
        "delta": p1 - p2,
        "z": z,
        "p": p,
        "ci_low": (p1 - p2) - 1.96 * se,
        "ci_high": (p1 - p2) + 1.96 * se,
    }


def main() -> int:
    log_paths = [
        p
        for p in PROJECTS_DIR.rglob("*.jsonl")
        if not any(p.name.startswith(pref) for pref in EXCLUDE_FILENAME_PREFIXES)
    ]
    # Note: we do NOT apply 90-day mtime filter here — we want full history
    print(
        f"Scanning {len(log_paths)} session logs (all history, agent-* excluded)",
        file=sys.stderr,
    )

    by_era_edits: dict[str, int] = {"A_baseline": 0, "B_gate2_only": 0, "C_both": 0}
    by_era_strict: dict[str, int] = {"A_baseline": 0, "B_gate2_only": 0, "C_both": 0}
    by_era_lenient: dict[str, int] = {"A_baseline": 0, "B_gate2_only": 0, "C_both": 0}
    by_era_sessions: dict[str, int] = {"A_baseline": 0, "B_gate2_only": 0, "C_both": 0}
    unknown_era = 0
    total_scanned = 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_session_path = OUT_DIR / "per_session.csv"
    with per_session_path.open("w") as scsv:
        scsv.write("session_file,session_start,era,model,n_edits,n_strict,n_lenient\n")
        for i, p in enumerate(log_paths):
            total_scanned += 1
            if i and i % 1000 == 0:
                print(
                    f"  scanned {i}; sessions-with-edits: {sum(by_era_sessions.values())}",
                    file=sys.stderr,
                )
            try:
                r = analyze_session(p)
            except Exception as exc:
                print(f"  err {p.name}: {exc}", file=sys.stderr)
                continue
            if r is None:
                continue
            era = r["era"]
            if era is None:
                unknown_era += 1
                continue
            by_era_edits[era] += r["n_edits"]
            by_era_strict[era] += r["n_strict_fired"]
            by_era_lenient[era] += r["n_lenient_fired"]
            by_era_sessions[era] += 1
            scsv.write(
                f"{r['session_file']},{r['session_start']},{era},{r['model'] or ''},"
                f"{r['n_edits']},{r['n_strict_fired']},{r['n_lenient_fired']}\n"
            )

    # Report
    lines: list[str] = []
    lines.append("# Natural-Experiment Analysis — Gate 2 + Core Rule 1")
    lines.append("")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(
        f"**Source:** all `~/.claude/projects/**/*.jsonl` "
        f"(agent-* excluded; {total_scanned:,} files scanned)"
    )
    lines.append("")
    lines.append("## Era definitions (from CLAUDE.md git log)")
    lines.append("")
    lines.append("| Era | Window | CLAUDE.md rules present |")
    lines.append("|---|---|---|")
    lines.append(
        f"| A_baseline | before {GATE_2_ADDED_UTC.isoformat()} UTC | Neither Gate 2 nor Core Rule 1 |"
    )
    lines.append(
        f"| B_gate2_only | {GATE_2_ADDED_UTC.isoformat()} → {CORE_RULE_1_ADDED_UTC.isoformat()} UTC | Gate 2 only (~8 days) |"
    )
    lines.append(
        f"| C_both | after {CORE_RULE_1_ADDED_UTC.isoformat()} UTC | Gate 2 + Core Rule 1 + examples (current) |"
    )
    lines.append("")
    lines.append("## Per-era compliance")
    lines.append("")
    lines.append(
        "| Era | Sessions w/ edits | Edits | Strict (Read) | Lenient (Read OR Write) |"
    )
    lines.append("|---|---|---|---|---|")
    era_data = {}
    for era in ("A_baseline", "B_gate2_only", "C_both"):
        n = by_era_edits[era]
        k_s = by_era_strict[era]
        k_l = by_era_lenient[era]
        if n > 0:
            s_rate = k_s / n
            l_rate = k_l / n
            s_ci = wilson_ci(k_s, n)
            l_ci = wilson_ci(k_l, n)
            era_data[era] = {
                "n": n,
                "k_strict": k_s,
                "k_lenient": k_l,
                "strict_rate": s_rate,
                "lenient_rate": l_rate,
                "strict_ci": s_ci,
                "lenient_ci": l_ci,
            }
            lines.append(
                f"| {era} | {by_era_sessions[era]} | {n} | "
                f"{s_rate:.4f} [{s_ci[0]:.3f}, {s_ci[1]:.3f}] | "
                f"{l_rate:.4f} [{l_ci[0]:.3f}, {l_ci[1]:.3f}] |"
            )
        else:
            era_data[era] = None
            lines.append(f"| {era} | {by_era_sessions[era]} | 0 | — | — |")
    lines.append("")
    if unknown_era:
        lines.append(
            f"_Sessions with unknown era (bad/missing timestamp, skipped): {unknown_era}_"
        )
        lines.append("")

    # Pairwise tests
    lines.append("## Pairwise causal contrasts (strict rate)")
    lines.append("")
    pairs = [
        ("A_baseline", "B_gate2_only", "B − A (effect of adding Gate 2)"),
        ("B_gate2_only", "C_both", "C − B (effect of adding Core Rule 1 on top)"),
        ("A_baseline", "C_both", "C − A (combined effect)"),
    ]
    lines.append("| Contrast | Δ strict | 95% CI | z | p |")
    lines.append("|---|---|---|---|---|")
    for a, b, label in pairs:
        ea = era_data[a]
        eb = era_data[b]
        if not (ea and eb):
            lines.append(f"| {label} | — | (insufficient data) | — | — |")
            continue
        t = two_proportion_test(eb["k_strict"], eb["n"], ea["k_strict"], ea["n"])
        if t["delta"] is None:
            lines.append(f"| {label} | — | (insufficient data) | — | — |")
            continue
        lines.append(
            f"| {label} | {t['delta']:+.4f} | "
            f"[{t['ci_low']:+.3f}, {t['ci_high']:+.3f}] | "
            f"{t['z']:.2f} | {t['p']:.4f} |"
        )
    lines.append("")

    # Interpretation
    lines.append("## Interpretation")
    lines.append("")
    a = era_data.get("A_baseline")
    b = era_data.get("B_gate2_only")
    c = era_data.get("C_both")
    if a and b and c:
        lines.append(
            "This is a **quasi-experimental pre-post analysis**, not a randomized "
            "controlled trial. Confounders are not held fixed between eras (other "
            "CLAUDE.md edits, model version drift, task distribution changes)."
        )
        lines.append("")
        b_a_delta = b["strict_rate"] - a["strict_rate"]
        c_b_delta = c["strict_rate"] - b["strict_rate"]
        c_a_delta = c["strict_rate"] - a["strict_rate"]
        lines.append(
            f"- Baseline compliance (no rules): **{a['strict_rate']:.4f}** on n={a['n']}"
        )
        lines.append(
            f"- With Gate 2 alone: **{b['strict_rate']:.4f}** on n={b['n']} (Δ vs baseline: {b_a_delta:+.4f})"
        )
        lines.append(
            f"- With both rules (current): **{c['strict_rate']:.4f}** on n={c['n']} (Δ vs baseline: {c_a_delta:+.4f})"
        )
        lines.append("")
        lines.append("### Key causal reads")
        if abs(b_a_delta) < 0.02:
            lines.append(
                "- **Gate 2 alone had ≤2pp effect on compliance.** "
                "The rule's mere presence didn't meaningfully change behavior."
            )
        elif b_a_delta > 0.02:
            lines.append(
                f"- **Gate 2 alone lifted compliance by {b_a_delta:+.1%}.** "
                "Consistent with Gate 2 doing causal work."
            )
        else:
            lines.append(
                f"- **Gate 2 alone may have lowered compliance by {abs(b_a_delta):.1%}.** "
                "Unexpected — likely noise from small Era B sample."
            )
        if abs(c_b_delta) < 0.02:
            lines.append(
                "- **Core Rule 1 addition on top of Gate 2: ≤2pp effect.** Both rules may be redundant with each other and with pre-training."
            )
        elif c_b_delta > 0.02:
            lines.append(
                f"- **Core Rule 1 addition lifted compliance further by {c_b_delta:+.1%}.** Suggests Core Rule 1 does additional work beyond Gate 2."
            )
        else:
            lines.append(
                f"- **Core Rule 1 addition correlates with {c_b_delta:+.1%} change.** Unexpected — inspect."
            )
    elif not a:
        lines.append(
            "Insufficient data in Era A (baseline) — logs may not extend back far enough. "
            "Cannot compute pre-post contrast."
        )
    else:
        lines.append("Partial data — some eras empty. See per-era table above.")
    lines.append("")

    lines.append("## Caveats (pre-registered)")
    lines.append("")
    lines.append(
        "- **Not an RCT.** Eras are temporally ordered, not randomly assigned. Confounders not held fixed."
    )
    lines.append(
        "- **Other CLAUDE.md edits** happened in all 3 windows. Hard to isolate Gate 2 or Core Rule 1 specifically."
    )
    lines.append(
        "- **Model version may have shifted** between eras (Opus 4 → 4.6, etc.)."
    )
    lines.append("- **Task mix changes** — user's project focus varies over time.")
    lines.append("- **Era B is only 8 days** — sample may be small, CI wide.")
    lines.append(
        "- **Log retention** — if the log system only keeps last N sessions, Era A may be under-represented."
    )
    lines.append("")

    report_path = OUT_DIR / "report.md"
    report_path.write_text("\n".join(lines))

    print("\nDone.", file=sys.stderr)
    print(f"Report: {report_path}", file=sys.stderr)
    print(f"Per-session: {per_session_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
