"""
Retrospective observational analysis of Gate 2 (Read-before-Edit) firing rate
from Claude Code session logs. Zero API cost.

Per SAP pilot addendum 003 — descriptive only, not causal.

For every Edit tool_use in every session log (90-day window, excluding
agent-*.jsonl), check whether a Read tool_use with matching file_path
appeared earlier in the same session. Report fire rate + distributions.

Output:
    runs/retrospective-<date>/report.md        — human-readable findings
    runs/retrospective-<date>/per_session.csv  — one row per session
    runs/retrospective-<date>/per_edit.jsonl   — one row per Edit call
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, stdev

PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUT_DIR = Path(__file__).parent / "runs" / f"retrospective-{time.strftime('%Y-%m-%d')}"
DAYS_BACK = 90
EXCLUDE_FILENAME_PREFIXES = ("agent-",)


def analyze_session(jsonl_path: Path) -> dict:
    """Scan one session log. Returns counts + per-edit records.

    Per-edit record: {file_path, prior_read: bool, replace_all: bool,
                      session_file, cwd, model}
    """
    reads_by_file: set[str] = set()
    writes_by_file: set[str] = set()
    edits: list[dict] = []
    cwd_seen: str | None = None
    model_seen: str | None = None

    with jsonl_path.open() as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if cwd_seen is None:
                cwd_seen = event.get("cwd")

            etype = event.get("type")

            if etype == "assistant":
                msg = event.get("message", {})
                if model_seen is None:
                    model_seen = msg.get("model")
                content = msg.get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
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
                                "replace_all": bool(inp.get("replace_all", False)),
                            }
                        )

    return {
        "session_file": jsonl_path.name,
        "cwd": cwd_seen,
        "model": model_seen,
        "n_edits": len(edits),
        "n_edits_with_prior_read": sum(1 for e in edits if e["prior_read"]),
        "n_edits_with_prior_read_or_write": sum(
            1 for e in edits if e["prior_read"] or e["prior_write"]
        ),
        "n_edits_with_prior_write_only": sum(
            1 for e in edits if e["prior_write"] and not e["prior_read"]
        ),
        "n_reads_unique_files": len(reads_by_file),
        "n_writes_unique_files": len(writes_by_file),
        "edits": edits,
    }


def cwd_to_project(cwd: str | None) -> str:
    if not cwd:
        return "(unknown)"
    if "/Development/" in cwd:
        after = cwd.split("/Development/", 1)[1]
        return after.split("/", 1)[0]
    if cwd.endswith("/nissimagent") or cwd.endswith("/.claude"):
        return "(home)"
    return re.sub(r"^/Users/[^/]+/", "", cwd).split("/", 1)[0] or "(other)"


def main() -> int:
    if not PROJECTS_DIR.exists():
        sys.exit(f"projects dir not found: {PROJECTS_DIR}")

    cutoff_ts = time.time() - (DAYS_BACK * 86_400)
    log_paths = [
        p
        for p in PROJECTS_DIR.rglob("*.jsonl")
        if p.stat().st_mtime >= cutoff_ts
        and not any(p.name.startswith(pref) for pref in EXCLUDE_FILENAME_PREFIXES)
    ]
    print(
        f"Scanning {len(log_paths)} session logs (90-day window, agent-* excluded)",
        file=sys.stderr,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_session_path = OUT_DIR / "per_session.csv"
    per_edit_path = OUT_DIR / "per_edit.jsonl"

    total_edits = 0
    total_edits_with_prior_read = 0
    total_edits_with_prior_read_or_write = 0
    total_edits_with_prior_write_only = 0
    by_project: dict[str, list[int]] = defaultdict(list)
    by_project_sessions: dict[str, int] = defaultdict(int)
    session_rates: list[float] = []
    replace_all_fired = replace_all_not = 0
    single_fired = single_not = 0
    sessions_with_any_edit = 0

    with per_session_path.open("w") as scsv, per_edit_path.open("w") as ejsonl:
        scsv.write("session_file,cwd,project,model,n_edits,n_fired,fire_rate\n")
        for i, p in enumerate(log_paths):
            if i and i % 500 == 0:
                print(
                    f"  scanned {i}/{len(log_paths)}; edits so far: {total_edits}",
                    file=sys.stderr,
                )
            try:
                result = analyze_session(p)
            except Exception as exc:
                print(f"  parse error {p.name}: {exc}", file=sys.stderr)
                continue

            n_edits = result["n_edits"]
            n_fired = result["n_edits_with_prior_read"]
            total_edits += n_edits
            total_edits_with_prior_read += n_fired
            total_edits_with_prior_read_or_write += result[
                "n_edits_with_prior_read_or_write"
            ]
            total_edits_with_prior_write_only += result["n_edits_with_prior_write_only"]
            if n_edits == 0:
                continue
            sessions_with_any_edit += 1
            rate = n_fired / n_edits
            session_rates.append(rate)

            project = cwd_to_project(result["cwd"])
            by_project[project].append(rate)
            by_project_sessions[project] += 1
            scsv.write(
                f"{result['session_file']},{(result['cwd'] or '').replace(',', '_')},"
                f"{project},{result['model'] or ''},{n_edits},{n_fired},{rate:.4f}\n"
            )
            for edit in result["edits"]:
                ejsonl.write(
                    json.dumps({**edit, "session": result["session_file"]}) + "\n"
                )
                if edit["replace_all"]:
                    if edit["prior_read"]:
                        replace_all_fired += 1
                    else:
                        replace_all_not += 1
                else:
                    if edit["prior_read"]:
                        single_fired += 1
                    else:
                        single_not += 1

    print(f"\nTotal sessions scanned: {len(log_paths)}", file=sys.stderr)
    print(f"Sessions with ≥1 Edit: {sessions_with_any_edit}", file=sys.stderr)
    print(f"Total Edit calls: {total_edits}", file=sys.stderr)
    print(
        f"Edits with prior Read of same file: "
        f"{total_edits_with_prior_read} ({100 * total_edits_with_prior_read / max(1, total_edits):.2f}%)",
        file=sys.stderr,
    )

    # Render report
    lines: list[str] = []
    lines.append("# Retrospective Gate 2 Analysis — Report")
    lines.append("")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Window:** last {DAYS_BACK} days")
    lines.append("**Source:** `~/.claude/projects/**/*.jsonl` (agent-* excluded)")
    lines.append("")
    lines.append("## Headline numbers")
    lines.append("")
    pool_rate = total_edits_with_prior_read / max(1, total_edits)
    lines.append(f"- Session logs scanned: **{len(log_paths):,}**")
    lines.append(f"- Sessions with ≥1 Edit: **{sessions_with_any_edit:,}**")
    lines.append(f"- Total Edit calls: **{total_edits:,}**")
    lines.append(
        f"- Edits with prior Read of same file: **{total_edits_with_prior_read:,}**"
    )
    lines.append("")
    lines.append(
        f"## Pooled historical Gate 2 fire rate (strict, Read-only): **{pool_rate:.4f}** ({100 * pool_rate:.2f}%)"
    )
    lines.append("")
    lenient_rate = total_edits_with_prior_read_or_write / max(1, total_edits)
    write_only_rate = total_edits_with_prior_write_only / max(1, total_edits)
    lines.append(
        f"## Pooled lenient rate (Read OR Write of same file before Edit): **{lenient_rate:.4f}** ({100 * lenient_rate:.2f}%)"
    )
    lines.append("")
    lines.append(
        f"- Edits preceded by Write-but-NOT-Read (Write-then-Edit pattern, arguably not a Gate 2 violation): "
        f"**{total_edits_with_prior_write_only:,}** ({100 * write_only_rate:.2f}%)"
    )
    lines.append(
        f'- True "no prior knowledge of file" violations: '
        f"**{total_edits - total_edits_with_prior_read_or_write:,}** "
        f"({100 * (1 - lenient_rate):.2f}%)"
    )
    lines.append("")
    lines.append(
        "> Caveat: Gate 2 was present in every session — this is NOT a causal estimate."
    )
    lines.append(
        "> The **lenient** rate is a better proxy for actual Gate 2 compliance, since Write-then-Edit"
    )
    lines.append("> means Claude already knows the file's content (it just wrote it).")
    lines.append("")

    # Session-rate distribution
    if session_rates:
        lines.append("## Per-session fire rate distribution")
        lines.append("")
        lines.append(f"- Sessions: {len(session_rates):,}")
        lines.append(f"- Mean rate per session: {mean(session_rates):.4f}")
        lines.append(f"- Median rate per session: {median(session_rates):.4f}")
        if len(session_rates) > 1:
            lines.append(f"- Std dev: {stdev(session_rates):.4f}")
        lines.append(
            f"- Sessions where ALL edits were preceded by Read: "
            f"{sum(1 for r in session_rates if r == 1.0)} "
            f"({100 * sum(1 for r in session_rates if r == 1.0) / len(session_rates):.1f}%)"
        )
        lines.append(
            f"- Sessions where NO edits had prior Read: "
            f"{sum(1 for r in session_rates if r == 0.0)} "
            f"({100 * sum(1 for r in session_rates if r == 0.0) / len(session_rates):.1f}%)"
        )

        # Histogram in ASCII
        bins = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        for r in session_rates:
            idx = min(9, int(r * 10))
            bins[idx] += 1
        lines.append("")
        lines.append("### Rate histogram (sessions per 10pp bin)")
        lines.append("")
        lines.append("```")
        max_bin = max(bins) or 1
        for i, count in enumerate(bins):
            bar = "█" * int(40 * count / max_bin)
            lines.append(f"[{i * 10:>3}-{(i + 1) * 10:>3}%]  {count:>6}  {bar}")
        lines.append("```")
        lines.append("")

    # Per-project
    lines.append("## By project")
    lines.append("")
    lines.append("| Project | Sessions | Mean rate |")
    lines.append("|---|---|---|")
    for project in sorted(by_project, key=lambda k: -by_project_sessions[k])[:15]:
        rates = by_project[project]
        lines.append(
            f"| {project} | {by_project_sessions[project]} | {mean(rates):.4f} |"
        )
    lines.append("")

    # replace_all vs single
    lines.append("## replace_all vs single-occurrence edits")
    lines.append("")
    ra_total = replace_all_fired + replace_all_not
    s_total = single_fired + single_not
    ra_rate = replace_all_fired / max(1, ra_total)
    s_rate = single_fired / max(1, s_total)
    lines.append(
        f"- `replace_all=True` edits: {ra_total} total; fire rate {ra_rate:.4f}"
    )
    lines.append(f"- Single-occurrence edits: {s_total} total; fire rate {s_rate:.4f}")
    lines.append(
        f"- Delta: {(ra_rate - s_rate):+.4f} "
        f"(positive = replace_all more likely to have prior Read)"
    )
    lines.append("")

    # Interpretation guide
    lines.append("## Interpretation")
    lines.append("")
    if pool_rate < 0.50:
        lines.append(
            f"- Pooled rate **{100 * pool_rate:.1f}% is below 50%** — "
            "Gate 2 isn't reliably producing Read-before-Edit even when present. "
            "Pilot's causal test likely to find small effects (both arms near baseline)."
        )
    elif pool_rate < 0.90:
        lines.append(
            f"- Pooled rate **{100 * pool_rate:.1f}%** is in the mid-band. "
            "Pilot is well-positioned to detect effects in either direction."
        )
    else:
        lines.append(
            f"- Pooled rate **{100 * pool_rate:.1f}% is near ceiling**. "
            "Pilot may struggle to detect marginal effects; "
            "consider sensitivity analysis for floor effects."
        )
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append("- **Not causal.** All sessions had Gate 2 present.")
    lines.append(
        "- **Confounded by Core Rule 1 + Good/Bad Examples** (still present in all sessions)."
    )
    lines.append("- **Model version varies.** Not controlled.")
    lines.append(
        "- **Task distribution varies.** Edit-heavy sessions (refactors) overrepresented."
    )
    lines.append(
        "- **Same-session Reads only.** Reads in prior sessions don't count — intentional."
    )
    lines.append(
        "- **No Edits-without-Reads on new files excluded by design** — Edits on files never Read in that session ARE counted as non-firing (correct per Gate 2 verifier spec)."
    )
    lines.append("")

    report_path = OUT_DIR / "report.md"
    report_path.write_text("\n".join(lines))
    print(f"\nReport: {report_path}", file=sys.stderr)
    print(f"Per-session CSV: {per_session_path}", file=sys.stderr)
    print(f"Per-edit JSONL: {per_edit_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
