"""
Retrospective observational analysis of Gate 9 (Test-after-multi-file-edit).

Gate 9 (frozen text from CLAUDE.md):
    "Test Gate? finished a multi-file code change or completed a build/fix step
     → auto-detect test framework and run smoke tier"

Operational definition for retrospective analysis:
    PRE-CONDITION: session contains Edit/Write tool_use calls on ≥2 distinct files
    in code-dir paths matching CODE_DIR_PATTERN.
    FIRE: after the LAST such code-dir Edit/Write, a Bash tool_use appears whose
    command contains a test-runner signature (pytest, vitest, npm test, etc.).

Fire rate = (# sessions where test ran after multi-file edit) /
            (# sessions with multi-file edit)

Limitations (same as Gate 2 retrospective):
  - Gate 9 was present in all sessions (no counterfactual)
  - Confounded by task type (some projects don't have tests)
  - "Test ran" doesn't mean "test was appropriate for the change"
  - Bash commands that happen to mention test-runners but aren't actually
    invoking them would match — acknowledged, not filtered

No API calls. Zero cost.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUT_DIR = (
    Path(__file__).parent / "runs" / f"retrospective-gate9-{time.strftime('%Y-%m-%d')}"
)
EXCLUDE_FILENAME_PREFIXES = ("agent-",)

CODE_DIR_PATTERN = re.compile(
    r"/(src|lib|backend|frontend|app|scripts|tests|test|core|shared)/",
    re.IGNORECASE,
)
TEST_CMD_PATTERN = re.compile(
    r"\b(pytest|vitest|jest|mocha|rspec|go test|cargo test|npm (run )?test|"
    r"yarn (run )?test|pnpm (run )?test|ruff check|tsc --noEmit|"
    r"python -m pytest|npx vitest|npx jest)\b",
    re.IGNORECASE,
)


def analyze_session(jsonl_path: Path) -> dict:
    """Return session-level analysis for Gate 9."""
    code_file_edits: list[tuple[int, str]] = []  # (event_idx, file_path)
    bash_commands: list[tuple[int, str]] = []  # (event_idx, command)
    event_idx = 0
    model_seen: str | None = None

    with jsonl_path.open() as f:
        for line in f:
            event_idx += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
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
                if name in ("Edit", "Write"):
                    fp = inp.get("file_path")
                    if isinstance(fp, str) and CODE_DIR_PATTERN.search(fp):
                        code_file_edits.append((event_idx, fp))
                elif name == "Bash":
                    cmd = inp.get("command", "")
                    if isinstance(cmd, str):
                        bash_commands.append((event_idx, cmd))

    # Pre-condition: ≥2 DISTINCT code-dir files edited
    distinct_code_files = {fp for _, fp in code_file_edits}
    if len(distinct_code_files) < 2:
        return {
            "session_file": jsonl_path.name,
            "in_scope": False,
            "n_distinct_code_files": len(distinct_code_files),
            "fired": None,
            "model": model_seen,
        }

    # Fire: after LAST code-file Edit/Write, any Bash command matches test pattern?
    last_code_edit_idx = max(idx for idx, _ in code_file_edits)
    tests_after = [
        cmd
        for idx, cmd in bash_commands
        if idx > last_code_edit_idx and TEST_CMD_PATTERN.search(cmd)
    ]

    return {
        "session_file": jsonl_path.name,
        "in_scope": True,
        "n_distinct_code_files": len(distinct_code_files),
        "n_code_edits": len(code_file_edits),
        "n_bash_after_last_edit": sum(
            1 for i, _ in bash_commands if i > last_code_edit_idx
        ),
        "fired": bool(tests_after),
        "first_test_cmd_preview": tests_after[0][:120] if tests_after else None,
        "model": model_seen,
    }


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def main() -> int:
    log_paths = [
        p
        for p in PROJECTS_DIR.rglob("*.jsonl")
        if not any(p.name.startswith(pref) for pref in EXCLUDE_FILENAME_PREFIXES)
    ]
    print(f"Scanning {len(log_paths)} sessions for Gate 9 analysis...", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_session_path = OUT_DIR / "per_session.csv"

    in_scope_sessions: list[dict] = []
    with per_session_path.open("w") as scsv:
        scsv.write(
            "session_file,in_scope,n_distinct_code_files,fired,model,first_test_cmd\n"
        )
        for i, p in enumerate(log_paths):
            if i and i % 1000 == 0:
                print(
                    f"  scanned {i}/{len(log_paths)}; in-scope so far: {len(in_scope_sessions)}",
                    file=sys.stderr,
                )
            try:
                r = analyze_session(p)
            except Exception as exc:
                print(f"  err {p.name}: {exc}", file=sys.stderr)
                continue
            if r["in_scope"]:
                in_scope_sessions.append(r)
            fired_str = "" if r["fired"] is None else str(r["fired"])
            first_cmd = r.get("first_test_cmd_preview") or ""
            first_cmd = first_cmd.replace(",", "_").replace("\n", " ")[:80]
            scsv.write(
                f"{r['session_file']},{r['in_scope']},{r['n_distinct_code_files']},"
                f"{fired_str},{r['model'] or ''},{first_cmd}\n"
            )

    n_scope = len(in_scope_sessions)
    n_fired = sum(1 for r in in_scope_sessions if r["fired"])
    rate = n_fired / max(1, n_scope)
    ci = wilson_ci(n_fired, n_scope)

    # Compare with Gate 2 for sanity
    lines: list[str] = []
    lines.append("# Retrospective Gate 9 Analysis — Report")
    lines.append("")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(
        f"**Source:** `~/.claude/projects/**/*.jsonl` (agent-* excluded; {len(log_paths)} files)"
    )
    lines.append("")
    lines.append("## Gate 9 operational definition (for retrospective)")
    lines.append("")
    lines.append(
        "- **Pre-condition:** session contains Edit/Write tool_use on ≥2 distinct files "
        "matching `/(src|lib|backend|frontend|app|scripts|tests|test|core|shared)/`"
    )
    lines.append(
        "- **Fire:** after the LAST such code-dir Edit/Write, a Bash tool_use "
        "with a test-runner command (pytest, vitest, jest, npm/yarn/pnpm test, "
        "go test, cargo test, ruff check, tsc --noEmit) appears"
    )
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- Sessions scanned: **{len(log_paths):,}**")
    lines.append(
        f"- Sessions in scope (≥2 distinct code-dir files edited): **{n_scope:,}**"
    )
    lines.append(f"- Sessions where test ran after last code edit: **{n_fired:,}**")
    lines.append(f"- Pooled fire rate: **{rate:.4f}** ({100 * rate:.2f}%)")
    lines.append(f"- 95% CI (Wilson): [{ci[0]:.4f}, {ci[1]:.4f}]")
    lines.append("")
    if rate < 0.10:
        interpretation = (
            "**Very low fire rate.** Gate 9 is effectively ignored — either the rule "
            "isn't firing or it's firing and being skipped. "
            "Candidate for a causal pilot (high effect-size sensitivity) OR for "
            "redrafting (maybe the prose doesn't trigger the right behavior)."
        )
    elif rate < 0.30:
        interpretation = (
            "**Low fire rate.** Gate 9 is rarely triggering tests after multi-file edits. "
            "Reasons could include: (a) user doesn't expect tests in most workflows, "
            "(b) tests are run OUT-of-session manually, (c) the rule is being ignored. "
            "Ambiguous result — pilot would clarify."
        )
    elif rate < 0.70:
        interpretation = (
            "**Moderate fire rate.** Gate 9 fires sometimes. Variance-heavy. "
            "Could be task-type-dependent (some projects have tests, others don't)."
        )
    else:
        interpretation = (
            "**High fire rate.** Gate 9 reliably triggers tests after multi-file edits."
        )
    lines.append("## Interpretation")
    lines.append("")
    lines.append(interpretation)
    lines.append("")

    # Comparison with Gate 2
    lines.append("## Comparison with Gate 2 (from retrospective-2026-04-16)")
    lines.append("")
    lines.append("| Gate | In-scope n | Fire rate | 95% CI |")
    lines.append("|---|---|---|---|")
    lines.append(
        "| Gate 2 (Read-before-Edit, lenient) | 1,330 edits | 98.80% | [0.981, 0.993] |"
    )
    lines.append(
        f"| Gate 9 (Test-after-multi-file) | {n_scope} sessions | {100 * rate:.2f}% | [{100 * ci[0]:.2f}, {100 * ci[1]:.2f}] |"
    )
    lines.append("")
    if rate < 0.50 < 0.988:
        lines.append(
            "**The gap is load-bearing evidence for the project's core thesis.** "
            "If Gate 2 and Gate 9 have dramatically different compliance rates despite "
            "being the same FORMAT (CLAUDE.md prose), then prose-format alone doesn't "
            "determine compliance. Other factors (task affordance, pre-training priors, "
            "cost of compliance) likely dominate."
        )
    lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append("- **Not causal.** Gate 9 was present in all sessions.")
    lines.append(
        "- **CODE_DIR_PATTERN is coarse.** May miss valid code-edit patterns or include non-code."
    )
    lines.append(
        "- **Test command regex may match false positives** (Bash commands that mention pytest without running it)."
    )
    lines.append(
        "- **Session boundaries matter.** Tests run in a DIFFERENT session aren't counted as Gate 9 firing."
    )
    lines.append(
        "- **Some projects legitimately have no tests** — e.g., memory file edits in `.claude/`. Gate 9 may be incorrectly scoping these as in-scope."
    )
    lines.append("")

    report_path = OUT_DIR / "report.md"
    report_path.write_text("\n".join(lines))

    print(
        f"\nDone. In-scope: {n_scope}. Fire rate: {100 * rate:.2f}% [{100 * ci[0]:.2f}, {100 * ci[1]:.2f}]",
        file=sys.stderr,
    )
    print(f"Report: {report_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
