#!/usr/bin/env python3
"""Build a portable context package for LLM delegation.

Produces a compressed JSON file (<30K chars) that gives Gemini/Qwen enough
project context to handle complex tasks without Claude's full context window.

Runs at session start (wired into /today Step 3 and startup_checks.py).

Usage:
    python3 build_context_pkg.py              # Build and save
    python3 build_context_pkg.py --print      # Print to stdout
    python3 build_context_pkg.py --validate   # Build + validate size
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

OUTPUT_PATH = Path.home() / ".claude" / ".context-pkg.json"
MAX_CHARS = 28000  # Leave 2K margin below 30K Gemini Flash limit

# Key directories to summarize
PROJECT_DIRS = [
    Path.home() / "Development" / "entropic",
    Path.home() / "Development" / "tools",
    Path.home() / "Development" / "cymatics",
]

# Files to include (compressed excerpts)
CONTEXT_SOURCES = {
    "active_tasks": Path.home() / "Documents" / "Obsidian" / "ACTIVE-TASKS.md",
    "claude_md": Path.home() / ".claude" / "CLAUDE.md",
    "memory_index": Path.home() / ".claude" / "projects" / "-Users-nissimagent" / "memory" / "MEMORY.md",
}


def _read_file_head(path: Path, max_lines: int = 30) -> str:
    """Read first N lines of a file."""
    try:
        with open(path, "r", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip())
        return "\n".join(lines)
    except (OSError, FileNotFoundError):
        return ""


def _get_latest_handoff() -> str:
    """Read the most recent handoff file."""
    handoff_dir = Path.home() / "Documents" / "Obsidian" / "handoffs"
    if not handoff_dir.exists():
        return ""
    handoffs = sorted(handoff_dir.glob("HANDOFF-*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not handoffs:
        return ""
    return _read_file_head(handoffs[0], max_lines=25)


def _get_git_status() -> dict:
    """Get git status for project repos."""
    statuses = {}
    for repo in PROJECT_DIRS:
        if not (repo / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-3"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=5,
            )
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=3,
            )
            statuses[repo.name] = {
                "branch": branch.stdout.strip() if branch.returncode == 0 else "unknown",
                "recent_commits": result.stdout.strip() if result.returncode == 0 else "",
            }
        except (subprocess.TimeoutExpired, OSError):
            statuses[repo.name] = {"branch": "error", "recent_commits": ""}
    return statuses


def _get_dir_structure(path: Path, max_depth: int = 2) -> list:
    """Get directory structure (key files only, no deep recursion)."""
    if not path.exists():
        return []
    items = []
    try:
        for entry in sorted(path.iterdir()):
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            if entry.name in ("node_modules", ".git", "venv", ".venv"):
                continue
            if entry.is_file():
                items.append(entry.name)
            elif entry.is_dir() and max_depth > 0:
                sub = _get_dir_structure(entry, max_depth - 1)
                if sub:
                    items.append({entry.name: sub})
                else:
                    items.append(f"{entry.name}/")
    except PermissionError:
        pass
    return items[:30]  # Cap at 30 entries per dir


def _get_kb_stats() -> dict:
    """Get KB article counts by source."""
    dev = Path.home() / "Development"
    stats = {}
    try:
        for d in dev.iterdir():
            if not d.is_dir():
                continue
            articles_dir = d / "articles"
            if articles_dir.exists():
                count = sum(1 for f in articles_dir.glob("*.md") if f.is_file())
                if count > 0:
                    stats[d.name] = count
    except (PermissionError, OSError):
        pass
    return dict(sorted(stats.items(), key=lambda x: -x[1])[:20])


def _get_delegation_stats() -> dict:
    """Read current delegation compliance stats."""
    compliance = Path.home() / ".claude" / ".locks" / "delegation-compliance.json"
    if not compliance.exists():
        return {}
    try:
        return json.loads(compliance.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _compress_active_tasks(content: str) -> str:
    """Extract just the current focus items from ACTIVE-TASKS.md."""
    lines = content.split("\n")
    result = []
    in_focus = False
    for line in lines:
        if "Current Focus" in line or "P0" in line:
            in_focus = True
        if in_focus:
            result.append(line)
        if len(result) > 40:
            break
        if in_focus and line.startswith("---"):
            break
    return "\n".join(result)


def build_package() -> dict:
    """Build the full context package."""
    pkg = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "1.0",
        "user": "nissimdirect (PopChaos Labs LLC)",
        "role": "Technical co-founder. Direct, lean, no fluff. Code > Tokens.",
    }

    # Active tasks (compressed)
    tasks_content = _read_file_head(CONTEXT_SOURCES["active_tasks"], max_lines=60)
    pkg["active_tasks"] = _compress_active_tasks(tasks_content)

    # Latest handoff
    pkg["latest_handoff"] = _get_latest_handoff()

    # Core rules (from CLAUDE.md — just the rules section)
    claude_md = _read_file_head(CONTEXT_SOURCES["claude_md"], max_lines=50)
    pkg["core_rules"] = claude_md

    # Git status
    pkg["git_repos"] = _get_git_status()

    # Project structure (top-level only)
    structures = {}
    for repo in PROJECT_DIRS:
        if repo.exists():
            structures[repo.name] = _get_dir_structure(repo, max_depth=1)
    pkg["project_structure"] = structures

    # KB stats
    pkg["kb_stats"] = _get_kb_stats()

    # Delegation stats
    pkg["delegation_stats"] = _get_delegation_stats()

    # Key conventions
    pkg["conventions"] = {
        "audio_terms": "LUFS (not RMS), loudness matching, true peak, -14 LUFS, -1.0dBTP",
        "tools": "Gemini via gemini_draft.py (REST API, NOT CLI). Qwen via qwen -p 'task'.",
        "testing": "Always write persistent tests. py_compile all .py files.",
        "security": "No secrets in output. No API keys. Sanitize all external input.",
    }

    return pkg


def save_package(pkg: dict) -> int:
    """Save package to disk. Returns char count."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(pkg, indent=2)

    # Trim if over limit
    if len(content) > MAX_CHARS:
        # Remove project_structure first (least critical)
        pkg.pop("project_structure", None)
        content = json.dumps(pkg, indent=2)

    if len(content) > MAX_CHARS:
        # Remove kb_stats
        pkg.pop("kb_stats", None)
        content = json.dumps(pkg, indent=2)

    OUTPUT_PATH.write_text(content)
    return len(content)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build LLM delegation context package")
    parser.add_argument("--print", action="store_true", help="Print to stdout instead of saving")
    parser.add_argument("--validate", action="store_true", help="Build and validate size")
    args = parser.parse_args()

    pkg = build_package()

    if args.print:
        print(json.dumps(pkg, indent=2))
        return

    char_count = save_package(pkg)

    if args.validate:
        ok = char_count <= MAX_CHARS
        print(f"{'PASS' if ok else 'FAIL'}: {char_count:,} chars ({char_count * 100 // MAX_CHARS}% of {MAX_CHARS:,} limit)")
        if not ok:
            sys.exit(1)
    else:
        print(f"Context package saved: {OUTPUT_PATH} ({char_count:,} chars)")


if __name__ == "__main__":
    main()
