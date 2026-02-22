#!/usr/bin/env python3
"""
Context Budget Monitor for Claude Code.

Measures token usage in auto-loaded files (CLAUDE.md, MEMORY.md),
breaks down by section, flags bloat, and suggests compaction targets.

Usage:
  python3 context_budget.py              # Full report
  python3 context_budget.py --check      # Exit 1 if over budget (for hooks)
  python3 context_budget.py --json       # Machine-readable output
  python3 context_budget.py --compact    # Show compaction recommendations
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- Config ---
TOKEN_BUDGET_PER_FILE = 5000  # 5K tokens per file
TOKEN_BUDGET_COMBINED = 8000  # Combined budget
WARN_THRESHOLD = 0.70  # Warn at 70% of budget
SECTION_WARN_TOKENS = 500  # Flag sections over this size
CHARS_PER_TOKEN = 3.8  # Conservative estimate for markdown

MONITORED_FILES = {
    "CLAUDE.md": Path.home() / ".claude" / "CLAUDE.md",
    "MEMORY.md": Path.home()
    / ".claude"
    / "projects"
    / "-Users-nissimagent"
    / "memory"
    / "MEMORY.md",
}


@dataclass
class Section:
    heading: str
    level: int
    line_start: int
    line_end: int
    text: str
    tokens: int = 0


@dataclass
class FileReport:
    name: str
    path: str
    total_chars: int = 0
    total_tokens: int = 0
    total_lines: int = 0
    sections: list = field(default_factory=list)
    budget: int = TOKEN_BUDGET_PER_FILE
    over_budget: bool = False
    pct_used: float = 0.0


def estimate_tokens(text: str) -> int:
    """Estimate token count from character count."""
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def parse_sections(text: str) -> list[Section]:
    """Parse markdown into sections by ## headings."""
    lines = text.split("\n")
    sections = []
    current_heading = "(preamble)"
    current_level = 0
    current_start = 0
    current_lines = []

    for i, line in enumerate(lines):
        match = re.match(r"^(#{1,4})\s+(.+)", line)
        if match:
            # Save previous section
            if current_lines or current_heading == "(preamble)":
                section_text = "\n".join(current_lines)
                sections.append(
                    Section(
                        heading=current_heading,
                        level=current_level,
                        line_start=current_start + 1,
                        line_end=i,
                        text=section_text,
                        tokens=estimate_tokens(section_text),
                    )
                )
            current_heading = match.group(2).strip()
            current_level = len(match.group(1))
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

    # Final section
    if current_lines:
        section_text = "\n".join(current_lines)
        sections.append(
            Section(
                heading=current_heading,
                level=current_level,
                line_start=current_start + 1,
                line_end=len(lines),
                text=section_text,
                tokens=estimate_tokens(section_text),
            )
        )

    return sections


def analyze_file(name: str, path: Path) -> FileReport | None:
    """Analyze a single file for token usage."""
    if not path.exists():
        return None

    text = path.read_text()
    sections = parse_sections(text)
    total_tokens = estimate_tokens(text)

    report = FileReport(
        name=name,
        path=str(path),
        total_chars=len(text),
        total_tokens=total_tokens,
        total_lines=text.count("\n") + 1,
        sections=sections,
        over_budget=total_tokens > TOKEN_BUDGET_PER_FILE,
        pct_used=round(total_tokens / TOKEN_BUDGET_PER_FILE * 100, 1),
    )
    return report


def format_bar(pct: float, width: int = 20) -> str:
    """Create a simple progress bar."""
    filled = int(width * min(pct, 100) / 100)
    bar = "█" * filled + "░" * (width - filled)
    if pct >= 100:
        return f"[{bar}] {pct:.0f}% OVER"
    elif pct >= WARN_THRESHOLD * 100:
        return f"[{bar}] {pct:.0f}% WARN"
    else:
        return f"[{bar}] {pct:.0f}%"


def print_report(reports: list[FileReport], compact_mode: bool = False):
    """Print human-readable report."""
    combined_tokens = sum(r.total_tokens for r in reports)
    combined_pct = round(combined_tokens / TOKEN_BUDGET_COMBINED * 100, 1)

    print("=" * 60)
    print("CONTEXT BUDGET REPORT")
    print("=" * 60)
    print()

    for r in reports:
        print(f"  {r.name}: {r.total_tokens:,} tokens / {r.budget:,} budget")
        print(f"  {format_bar(r.pct_used)}")
        print(f"  ({r.total_lines} lines, {r.total_chars:,} chars)")
        print()

    print(f"  Combined: {combined_tokens:,} / {TOKEN_BUDGET_COMBINED:,}")
    print(f"  {format_bar(combined_pct)}")
    print()

    # Section breakdown (top consumers)
    all_sections = []
    for r in reports:
        for s in r.sections:
            all_sections.append((r.name, s))

    all_sections.sort(key=lambda x: x[1].tokens, reverse=True)

    print("-" * 60)
    print("TOP SECTIONS BY TOKEN USAGE")
    print("-" * 60)
    print(f"  {'File':<12} {'Section':<30} {'Tokens':>7} {'Lines':>8}")
    print(f"  {'─' * 12} {'─' * 30} {'─' * 7} {'─' * 8}")

    for file_name, s in all_sections[:15]:
        heading = s.heading[:29]
        flag = " !" if s.tokens > SECTION_WARN_TOKENS else "  "
        lines_range = f"{s.line_start}-{s.line_end}"
        print(f"{flag}{file_name:<12} {heading:<30} {s.tokens:>7} {lines_range:>8}")

    if compact_mode:
        print()
        print_compaction_recommendations(reports, all_sections)


def print_compaction_recommendations(reports: list[FileReport], all_sections: list):
    """Print actionable compaction recommendations."""
    print("=" * 60)
    print("COMPACTION RECOMMENDATIONS")
    print("=" * 60)
    print()

    combined_tokens = sum(r.total_tokens for r in reports)

    if combined_tokens <= TOKEN_BUDGET_COMBINED * WARN_THRESHOLD:
        print("  You're within budget. No compaction needed.")
        return

    # Find sections that could be moved to skills/topic files
    movable = []
    for file_name, s in all_sections:
        if s.tokens > SECTION_WARN_TOKENS and s.heading != "(preamble)":
            movable.append((file_name, s))

    if movable:
        print("  MOVE TO SKILLS (load on-demand, not every message):")
        savings = 0
        for file_name, s in movable:
            print(
                f"    - [{file_name}] '{s.heading}' ({s.tokens} tokens, lines {s.line_start}-{s.line_end})"
            )
            savings += s.tokens
        print(f"    Potential savings: ~{savings} tokens")
        print()

    # Check for patterns suggesting bloat
    for r in reports:
        text = Path(r.path).read_text() if Path(r.path).exists() else ""

        # Long lines (likely detailed descriptions)
        long_lines = [
            i + 1 for i, line in enumerate(text.split("\n")) if len(line) > 200
        ]
        if long_lines:
            print(
                f"  LONG LINES in {r.name} (>200 chars, could be tables/descriptions):"
            )
            for ln in long_lines[:5]:
                print(f"    Line {ln}")
            if len(long_lines) > 5:
                print(f"    ...and {len(long_lines) - 5} more")
            print()

        # Duplicate-ish patterns
        lines = text.split("\n")
        word_counts = {}
        for line in lines:
            words = line.strip().lower()
            if len(words) > 20:
                if words in word_counts:
                    word_counts[words] += 1
                else:
                    word_counts[words] = 1
        dupes = {k: v for k, v in word_counts.items() if v > 1}
        if dupes:
            print(f"  POSSIBLE DUPLICATES in {r.name}:")
            for text_snippet, count in list(dupes.items())[:3]:
                print(f"    '{text_snippet[:60]}...' appears {count}x")
            print()


def json_report(reports: list[FileReport]) -> dict:
    """Generate machine-readable report."""
    combined_tokens = sum(r.total_tokens for r in reports)
    return {
        "combined_tokens": combined_tokens,
        "combined_budget": TOKEN_BUDGET_COMBINED,
        "combined_pct": round(combined_tokens / TOKEN_BUDGET_COMBINED * 100, 1),
        "over_budget": combined_tokens > TOKEN_BUDGET_COMBINED,
        "files": [
            {
                "name": r.name,
                "tokens": r.total_tokens,
                "budget": r.budget,
                "pct": r.pct_used,
                "lines": r.total_lines,
                "over_budget": r.over_budget,
                "top_sections": [
                    {
                        "heading": s.heading,
                        "tokens": s.tokens,
                        "lines": f"{s.line_start}-{s.line_end}",
                    }
                    for s in sorted(r.sections, key=lambda x: x.tokens, reverse=True)[
                        :5
                    ]
                ],
            }
            for r in reports
        ],
    }


def hook_output(reports: list[FileReport]) -> str:
    """Generate concise warning for hook injection."""
    combined_tokens = sum(r.total_tokens for r in reports)
    combined_pct = combined_tokens / TOKEN_BUDGET_COMBINED * 100

    if combined_pct < WARN_THRESHOLD * 100:
        return ""

    lines = [
        f"CONTEXT BUDGET: {combined_tokens:,}/{TOKEN_BUDGET_COMBINED:,} tokens ({combined_pct:.0f}%)"
    ]
    for r in reports:
        if r.pct_used >= WARN_THRESHOLD * 100:
            lines.append(
                f"  {r.name}: {r.total_tokens:,}/{r.budget:,} ({r.pct_used:.0f}%)"
            )

    big_sections = []
    for r in reports:
        for s in r.sections:
            if s.tokens > SECTION_WARN_TOKENS:
                big_sections.append(f"{r.name}:{s.heading} ({s.tokens} tok)")
    if big_sections:
        lines.append("  Large sections: " + ", ".join(big_sections[:3]))

    return "\n".join(lines)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--report"

    reports = []
    for name, path in MONITORED_FILES.items():
        report = analyze_file(name, path)
        if report:
            reports.append(report)

    if not reports:
        print("No monitored files found.")
        sys.exit(0)

    if mode == "--json":
        print(json.dumps(json_report(reports), indent=2))
    elif mode == "--check":
        warning = hook_output(reports)
        if warning:
            print(warning)
            sys.exit(1)
        sys.exit(0)
    elif mode == "--compact":
        print_report(reports, compact_mode=True)
    elif mode == "--hook":
        # For SessionStart hook — output warning if over threshold
        warning = hook_output(reports)
        if warning:
            print(json.dumps({"hookSpecificOutput": warning}))
    else:
        print_report(reports)


if __name__ == "__main__":
    main()
