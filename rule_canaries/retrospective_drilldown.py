"""
Drill-down on the retrospective Gate 2 analysis:
 - Re-bucket by edited file path (not cwd — which was always $HOME)
 - Surface the sessions with <90% fire rate (Gate 2 "failures") for inspection
 - Look at what files/projects drove the failures

Reads runs/retrospective-<date>/per_edit.jsonl + per_session.csv.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

RUN_DIR = sorted(
    (Path(__file__).parent / "runs").glob("retrospective-*"),
    key=lambda p: p.stat().st_mtime,
)[-1]
PER_EDIT = RUN_DIR / "per_edit.jsonl"
PER_SESSION = RUN_DIR / "per_session.csv"
OUT = RUN_DIR / "drilldown.md"


def project_of(path: str) -> str:
    """Extract project name from a file path."""
    if "/Development/" in path:
        return path.split("/Development/", 1)[1].split("/", 1)[0]
    if "/.claude/" in path:
        return ".claude"
    if "/Documents/Obsidian/" in path:
        return "Obsidian"
    m = re.match(r"^/Users/[^/]+/([^/]+)", path)
    return m.group(1) if m else "(other)"


def main() -> int:
    if not PER_EDIT.exists():
        sys.exit(f"Missing {PER_EDIT} — run retrospective_gate2_analysis.py first")

    # Per-project: count edits + fires
    proj_edits: dict[str, int] = defaultdict(int)
    proj_fires: dict[str, int] = defaultdict(int)
    with PER_EDIT.open() as f:
        for line in f:
            edit = json.loads(line)
            p = project_of(edit["file_path"])
            proj_edits[p] += 1
            if edit["prior_read"]:
                proj_fires[p] += 1

    # Per-session: find failures
    failing_sessions: list[dict] = []
    with PER_SESSION.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            rate = float(row["fire_rate"])
            n_edits = int(row["n_edits"])
            if rate < 0.90 and n_edits >= 3:  # drop tiny-n outliers
                failing_sessions.append(
                    {
                        "session": row["session_file"],
                        "model": row["model"],
                        "n_edits": n_edits,
                        "n_fired": int(row["n_fired"]),
                        "rate": rate,
                    }
                )

    # Failures: load edits from those sessions to see what went wrong
    failing_ids = {f["session"] for f in failing_sessions}
    failures_by_session: dict[str, list[dict]] = defaultdict(list)
    with PER_EDIT.open() as f:
        for line in f:
            edit = json.loads(line)
            if edit["session"] in failing_ids:
                failures_by_session[edit["session"]].append(edit)

    lines: list[str] = []
    lines.append("# Retrospective Gate 2 Drilldown")
    lines.append("")
    lines.append(f"Source: {PER_EDIT}")
    lines.append("")

    # Project breakdown (real this time)
    lines.append("## By project (from file_path, not cwd)")
    lines.append("")
    lines.append("| Project | Edits | Fired | Rate |")
    lines.append("|---|---|---|---|")
    for p in sorted(proj_edits, key=lambda k: -proj_edits[k]):
        n = proj_edits[p]
        f = proj_fires[p]
        lines.append(f"| `{p}` | {n} | {f} | {f / n:.4f} |")
    lines.append("")

    # Failing sessions
    lines.append("## Sessions below 90% fire rate (n_edits ≥ 3)")
    lines.append("")
    failing_sessions.sort(key=lambda s: s["rate"])
    lines.append(f"Found {len(failing_sessions)} such sessions.")
    lines.append("")
    lines.append("| Session | Model | Edits | Fired | Rate |")
    lines.append("|---|---|---|---|---|")
    for s in failing_sessions:
        lines.append(
            f"| `{s['session'][:30]}…` | `{s['model']}` | "
            f"{s['n_edits']} | {s['n_fired']} | {s['rate']:.4f} |"
        )
    lines.append("")

    # Drill into each failure: which files were edited without prior Read?
    lines.append("## What went wrong in failing sessions")
    lines.append("")
    for s in failing_sessions:
        sid = s["session"]
        edits = failures_by_session[sid]
        missed = [e for e in edits if not e["prior_read"]]
        lines.append(f"### `{sid[:40]}…` — {s['rate']:.2%} rate, model={s['model']}")
        lines.append("")
        lines.append(f"- Total edits: {len(edits)}")
        lines.append("- Missed Gate 2 on these files:")
        for e in missed[:10]:
            project = project_of(e["file_path"])
            lines.append(f"  - `[{project}]` {e['file_path']}")
        if len(missed) > 10:
            lines.append(f"  - (and {len(missed) - 10} more)")
        lines.append("")

    # Model breakdown
    lines.append("## By model (all sessions)")
    lines.append("")
    model_fires: dict[str, int] = defaultdict(int)
    model_edits: dict[str, int] = defaultdict(int)
    with PER_SESSION.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            m = row["model"] or "(unknown)"
            model_edits[m] += int(row["n_edits"])
            model_fires[m] += int(row["n_fired"])
    lines.append("| Model | Edits | Fired | Rate |")
    lines.append("|---|---|---|---|")
    for m in sorted(model_edits, key=lambda k: -model_edits[k]):
        n = model_edits[m]
        f = model_fires[m]
        lines.append(f"| `{m}` | {n} | {f} | {f / n:.4f} |")
    lines.append("")

    OUT.write_text("\n".join(lines))
    print(f"Wrote: {OUT}")
    print("")
    # Quick summary to stdout
    print(f"Projects: {len(proj_edits)}")
    print(f"Failing sessions (rate<90%, n_edits>=3): {len(failing_sessions)}")
    if failing_sessions:
        print(
            f"  worst rate: {failing_sessions[0]['rate']:.2%} "
            f"({failing_sessions[0]['n_edits']} edits)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
