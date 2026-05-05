"""
Retrospective observational analysis of Gates 12 (Ship Gate) and 17 (Infra-change).

Gate 12 (Ship Gate):
    Pre-condition: session contains ≥5 distinct file Edits/Writes AND a test-runner
    Bash command ran at some point (proxy for "tests pass").
    Fire: at least 2 of 4 shipping skills invoked after last edit: /quality, /uat,
    /qa-redteam, /review.
    Skill invocation detection: user messages with "/<skill>" slash-command OR
    assistant Task tool calls with one of those skill names.

Gate 17 (Infra-change):
    Pre-condition: Edit or Write on a path matching infra regex
    (.mcp.json, settings.json, cron.json, safeBins, hooks/, *.env, /config/).
    Fire: after such edit, a Grep tool call OR a Bash command containing `grep`
    or `rg` appears within the session — proxy for "map all callers."

Same caveats as prior retrospectives.
No API calls.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUT_DIR = (
    Path(__file__).parent
    / "runs"
    / f"retrospective-gates-12-17-{time.strftime('%Y-%m-%d')}"
)
EXCLUDE_FILENAME_PREFIXES = ("agent-",)

# Gate 17 infra patterns
INFRA_PATH_PATTERN = re.compile(
    r"(\.mcp\.json$|settings\.json$|cron\.json$|safeBins|/hooks/|\.env$|/config\.json$|AGENTS\.md$)",
    re.IGNORECASE,
)

# Gate 12 shipping skills
SHIP_SKILLS = {"quality", "uat", "qa-redteam", "review"}
SLASH_CMD_PATTERN = re.compile(r"/(quality|uat|qa-redteam|review)\b")


def analyze_session(jsonl_path: Path) -> dict:
    """Apply Gate 12 + Gate 17 detectors."""
    edits_writes: list[tuple[int, str]] = []  # (idx, path)
    bash_cmds: list[tuple[int, str]] = []
    infra_edits: list[tuple[int, str]] = []
    grep_calls: list[tuple[int, str]] = []
    slash_invocations: list[tuple[int, str]] = []
    skill_invocations: list[tuple[int, str]] = []  # via Task or Skill tool
    test_cmd_appeared = False

    event_idx = 0
    model_seen: str | None = None

    with jsonl_path.open() as f:
        for line in f:
            event_idx += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")

            if etype == "user":
                msg = event.get("message", {})
                content = msg.get("content")
                if isinstance(content, str):
                    for m in SLASH_CMD_PATTERN.finditer(content):
                        slash_invocations.append((event_idx, m.group(1)))

            elif etype == "assistant":
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
                        if isinstance(fp, str):
                            edits_writes.append((event_idx, fp))
                            if INFRA_PATH_PATTERN.search(fp):
                                infra_edits.append((event_idx, fp))
                    elif name == "Bash":
                        cmd = inp.get("command", "")
                        if isinstance(cmd, str):
                            bash_cmds.append((event_idx, cmd))
                            if re.search(
                                r"\b(pytest|vitest|jest|mocha|npm (run )?test|"
                                r"yarn (run )?test|go test|cargo test)\b",
                                cmd,
                                re.IGNORECASE,
                            ):
                                test_cmd_appeared = True
                    elif name == "Grep":
                        pat = inp.get("pattern", "")
                        if isinstance(pat, str):
                            grep_calls.append((event_idx, pat))
                    elif name in ("Task", "Skill"):
                        # Task tool calls may invoke subagents; Skill tool invokes skills
                        # input.subagent_type (Task) or input.skill (Skill)
                        target = inp.get("subagent_type") or inp.get("skill")
                        if isinstance(target, str) and target in SHIP_SKILLS:
                            skill_invocations.append((event_idx, target))

    distinct_files = {fp for _, fp in edits_writes}

    # Gate 12 analysis
    gate12 = {
        "in_scope": len(distinct_files) >= 5 and test_cmd_appeared,
        "n_distinct_files": len(distinct_files),
        "test_cmd_appeared": test_cmd_appeared,
    }
    if gate12["in_scope"]:
        last_edit_idx = max((i for i, _ in edits_writes), default=0)
        ship_skill_names_after = set()
        for idx, skill in slash_invocations + skill_invocations:
            if idx >= last_edit_idx:
                ship_skill_names_after.add(skill)
        gate12["n_ship_skills_after"] = len(ship_skill_names_after)
        gate12["fired"] = len(ship_skill_names_after) >= 2
        gate12["ship_skills_seen"] = sorted(ship_skill_names_after)
    else:
        gate12["fired"] = None
        gate12["n_ship_skills_after"] = 0
        gate12["ship_skills_seen"] = []

    # Gate 17 analysis
    gate17 = {
        "in_scope": bool(infra_edits),
        "n_infra_edits": len(infra_edits),
        "infra_files": sorted({fp for _, fp in infra_edits}),
    }
    if gate17["in_scope"]:
        first_infra_idx = min(i for i, _ in infra_edits)
        greps_after = [g for i, g in grep_calls if i >= first_infra_idx]
        bash_greps_after = [
            c
            for i, c in bash_cmds
            if i >= first_infra_idx and re.search(r"\b(grep|rg|ripgrep)\b", c)
        ]
        gate17["n_grep_or_rg_after"] = len(greps_after) + len(bash_greps_after)
        gate17["fired"] = bool(greps_after or bash_greps_after)
    else:
        gate17["fired"] = None
        gate17["n_grep_or_rg_after"] = 0

    return {
        "session_file": jsonl_path.name,
        "model": model_seen,
        "gate12": gate12,
        "gate17": gate17,
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
    print(f"Scanning {len(log_paths)} sessions for Gates 12 + 17...", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    g12_path = OUT_DIR / "gate12_per_session.csv"
    g17_path = OUT_DIR / "gate17_per_session.csv"

    g12_scope, g12_fired = 0, 0
    g17_scope, g17_fired = 0, 0

    with g12_path.open("w") as g12f, g17_path.open("w") as g17f:
        g12f.write(
            "session,model,in_scope,n_distinct_files,test_cmd,n_ship_skills,fired,ship_skills\n"
        )
        g17f.write(
            "session,model,in_scope,n_infra_edits,n_greps_after,fired,infra_files\n"
        )
        for i, p in enumerate(log_paths):
            if i and i % 1000 == 0:
                print(
                    f"  scanned {i}; scope g12={g12_scope} g17={g17_scope}",
                    file=sys.stderr,
                )
            try:
                r = analyze_session(p)
            except Exception as exc:
                print(f"  err {p.name}: {exc}", file=sys.stderr)
                continue
            g12 = r["gate12"]
            g17 = r["gate17"]
            if g12["in_scope"]:
                g12_scope += 1
                if g12["fired"]:
                    g12_fired += 1
            if g17["in_scope"]:
                g17_scope += 1
                if g17["fired"]:
                    g17_fired += 1
            g12f.write(
                f"{r['session_file']},{r['model'] or ''},{g12['in_scope']},"
                f"{g12['n_distinct_files']},{g12['test_cmd_appeared']},"
                f"{g12['n_ship_skills_after']},{g12['fired']},"
                f'"{";".join(g12["ship_skills_seen"])}"\n'
            )
            g17f.write(
                f"{r['session_file']},{r['model'] or ''},{g17['in_scope']},"
                f"{g17['n_infra_edits']},{g17['n_grep_or_rg_after']},"
                f"{g17['fired']},"
                f'"{";".join(g17["infra_files"][:3])}"\n'
            )

    g12_rate = g12_fired / max(1, g12_scope)
    g12_ci = wilson_ci(g12_fired, g12_scope)
    g17_rate = g17_fired / max(1, g17_scope)
    g17_ci = wilson_ci(g17_fired, g17_scope)

    lines: list[str] = []
    lines.append("# Retrospective: Gate 12 (Ship Gate) + Gate 17 (Infra-change)")
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(
        f"Source: `~/.claude/projects/**/*.jsonl` (agent-* excluded; {len(log_paths)} files)"
    )
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Gate | In-scope n | Fired | Rate | 95% CI |")
    lines.append("|---|---|---|---|---|")
    lines.append(
        f"| Gate 12 (Ship Gate: ≥5 files + tests → 4 skills) | "
        f"{g12_scope} | {g12_fired} | {100 * g12_rate:.2f}% | "
        f"[{100 * g12_ci[0]:.2f}, {100 * g12_ci[1]:.2f}] |"
    )
    lines.append(
        f"| Gate 17 (Infra-change: mcp/settings/etc → grep/rg after) | "
        f"{g17_scope} | {g17_fired} | {100 * g17_rate:.2f}% | "
        f"[{100 * g17_ci[0]:.2f}, {100 * g17_ci[1]:.2f}] |"
    )
    lines.append("")
    lines.append("## Operational definitions (for audit)")
    lines.append("")
    lines.append("**Gate 12 Ship Gate:**")
    lines.append(
        "- Pre-condition: session contains ≥5 distinct file Edits/Writes AND at least one Bash test-runner command (pytest, vitest, npm test, etc.) appeared"
    )
    lines.append(
        "- Fire: at least 2 of 4 shipping skills invoked after last edit via slash-command (`/quality`, `/uat`, `/qa-redteam`, `/review`) OR via Task/Skill tool calls"
    )
    lines.append("")
    lines.append("**Gate 17 Infra-change:**")
    lines.append(
        "- Pre-condition: Edit/Write on a path matching `.mcp.json | settings.json | cron.json | safeBins | /hooks/ | .env | /config.json | AGENTS.md`"
    )
    lines.append(
        "- Fire: after the first such edit, either a Grep tool_use OR a Bash command containing `grep`/`rg`/`ripgrep` appears"
    )
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append("- Observational only; no counterfactual")
    lines.append(
        "- Gate 17 fire-detector is coarse — any subsequent grep is counted, not specifically grepping for callers of the changed config key"
    )
    lines.append(
        '- Gate 12\'s "tests pass" proxy is "any test command ran" — doesn\'t check exit status'
    )
    lines.append(
        '- Gate 12\'s "4 skills invoked" is relaxed to ≥2 of 4 to be charitable to sessions that only needed subset'
    )
    lines.append("")

    (OUT_DIR / "report.md").write_text("\n".join(lines))
    print("\nDone.", file=sys.stderr)
    print(
        f"  Gate 12: {g12_fired}/{g12_scope} = {100 * g12_rate:.2f}% [{100 * g12_ci[0]:.2f}, {100 * g12_ci[1]:.2f}]",
        file=sys.stderr,
    )
    print(
        f"  Gate 17: {g17_fired}/{g17_scope} = {100 * g17_rate:.2f}% [{100 * g17_ci[0]:.2f}, {100 * g17_ci[1]:.2f}]",
        file=sys.stderr,
    )
    print(f"Report: {OUT_DIR / 'report.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
