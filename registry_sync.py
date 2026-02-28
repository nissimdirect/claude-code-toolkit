#!/usr/bin/env python3
"""
Registry Sync — Rebuilds registry.json from disk and propagates counts.

Replaces manual /propagate skill workflow. Filesystem is source of truth.

Usage:
    python3 registry_sync.py              # Dry-run: show what would change
    python3 registry_sync.py --apply      # Write changes to all files
    python3 registry_sync.py --registry   # Only rebuild registry.json
    python3 registry_sync.py --counts     # Only propagate counts
"""

import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

HOME = Path.home()
SKILLS_DIR = HOME / ".claude" / "skills"
AGENTS_DIR = HOME / ".claude" / "agents"
REGISTRY_PATH = SKILLS_DIR / "registry.json"
MEMORY_DIR = HOME / ".claude" / "projects" / "-Users-nissimagent" / "memory"
OBSIDIAN = HOME / "Documents" / "Obsidian"
BACKUP_DIR = HOME / ".claude" / ".backups"

# Files where counts are propagated
COUNT_TARGETS = {
    "MEMORY": MEMORY_DIR / "MEMORY.md",
    "SESSION_INIT": MEMORY_DIR / "SESSION_INIT.md",
    "WORKFLOW": MEMORY_DIR / "workflow.md",
    "CURRENT_STATE": MEMORY_DIR / "current-state.md",
    "DIRECTORY": OBSIDIAN / "DIRECTORY.md",
}


# ──────────────────────────────────────────────
# Disk scanning (source of truth)
# ──────────────────────────────────────────────


def scan_disk():
    """Scan filesystem for skills and agents."""
    active = sorted(
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists() and d.name != "_frozen"
    )
    frozen_dir = SKILLS_DIR / "_frozen"
    frozen = (
        sorted(d.name for d in frozen_dir.iterdir() if d.is_dir())
        if frozen_dir.exists()
        else []
    )
    agents = (
        sorted(f.stem for f in AGENTS_DIR.glob("*.md")) if AGENTS_DIR.exists() else []
    )
    return {"skills_active": active, "skills_frozen": frozen, "agents": agents}


def extract_frontmatter(skill_md_path):
    """Extract description and category from SKILL.md YAML frontmatter or content."""
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return "", ""

    description = ""
    category = ""

    # Try YAML frontmatter (between --- markers)
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        # Extract description
        desc_match = re.search(r"^description:\s*(.+)$", fm_text, re.MULTILINE)
        if desc_match:
            description = desc_match.group(1).strip().strip('"').strip("'")
        # Extract category
        cat_match = re.search(r"^category:\s*(.+)$", fm_text, re.MULTILINE)
        if cat_match:
            category = cat_match.group(1).strip().strip('"').strip("'")

    # Fallback: try to get description from first paragraph after title
    if not description:
        # Look for "Use when" or "Use this" lines
        use_match = re.search(
            r"(Use (?:when|this).+?)(?:\n\n|\n#|\Z)", content, re.DOTALL
        )
        if use_match:
            description = use_match.group(1).strip().replace("\n", " ")

    return description, category


# ──────────────────────────────────────────────
# Registry rebuilding
# ──────────────────────────────────────────────


def load_existing_registry():
    """Load existing registry.json to preserve descriptions/categories."""
    if not REGISTRY_PATH.exists():
        return {}
    try:
        with open(REGISTRY_PATH) as f:
            data = json.load(f)
        return {s["name"]: s for s in data.get("skills", [])}
    except Exception:
        return {}


def rebuild_registry(disk_state):
    """Generate registry.json content from disk scan."""
    existing = load_existing_registry()
    skills = []

    for name in disk_state["skills_active"]:
        skill_md = SKILLS_DIR / name / "SKILL.md"

        # Prefer existing registry data (preserves curated descriptions)
        if name in existing:
            entry = existing[name].copy()
            # Ensure path is correct
            entry["path"] = f"~/.claude/skills/{name}/SKILL.md"
            skills.append(entry)
        else:
            # New skill — extract from SKILL.md
            desc, cat = extract_frontmatter(skill_md)
            skills.append(
                {
                    "name": name,
                    "path": f"~/.claude/skills/{name}/SKILL.md",
                    "description": desc or f"Skill: {name}",
                    "user_invocable": True,
                    "category": cat or "uncategorized",
                }
            )

    counts = {
        "total_skills": len(disk_state["skills_active"]),
        "total_articles": existing.get("__counts_total_articles", 0),
    }
    # Try to preserve article count from existing registry
    if REGISTRY_PATH.exists():
        try:
            with open(REGISTRY_PATH) as f:
                old = json.load(f)
            old_counts = old.get("counts", {})
            if "total_articles" in old_counts:
                counts["total_articles"] = old_counts["total_articles"]
        except Exception:
            pass

    return {
        "skills": skills,
        "counts": counts,
        "last_updated": date.today().isoformat(),
    }


# ──────────────────────────────────────────────
# Count propagation
# ──────────────────────────────────────────────


def compute_counts(disk_state):
    """Compute count values from disk state."""
    return {
        "skills": len(disk_state["skills_active"]),
        "frozen": len(disk_state["skills_frozen"]),
        "agents": len(disk_state["agents"]),
    }


def propagate_counts(counts, dry_run=True):
    """Update hardcoded counts in all dependent files.

    Returns list of (file_label, old_text, new_text, path) changes.
    """
    changes = []
    n_skills = counts["skills"]
    n_agents = counts["agents"]

    # Define replacement rules per file
    # Each rule: (file_key, pattern, replacement_func)
    rules = [
        # MEMORY.md — "N skills" in the Infra line
        (
            "MEMORY",
            r"(\d+)\s+skills\b",
            lambda _m: f"{n_skills} skills",
            "Infra",  # context hint — only match on lines with "Infra" context
        ),
        # MEMORY.md — "N agents" in the Infra line
        (
            "MEMORY",
            r"(\d+)\s+agents\b",
            lambda _m: f"{n_agents} agents",
            "Infra",
        ),
        # SESSION_INIT.md — "Skills Arsenal (N Skills)"
        (
            "SESSION_INIT",
            r"Skills Arsenal \(\d+ Skills?\)",
            lambda _m: f"Skills Arsenal ({n_skills} Skills)",
            None,
        ),
        # DIRECTORY.md — "Skills Menu (N Skills)"
        (
            "DIRECTORY",
            r"Skills Menu \(\d+ Skills?\)",
            lambda _m: f"Skills Menu ({n_skills} Skills)",
            None,
        ),
    ]

    for file_key, pattern, repl_func, context_hint in rules:
        path = COUNT_TARGETS.get(file_key)
        if not path or not path.exists():
            continue

        content = path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        new_lines = []
        changed = False

        for line in lines:
            # If context_hint given, only apply to lines containing it
            if context_hint and context_hint.lower() not in line.lower():
                new_lines.append(line)
                continue

            new_line = re.sub(pattern, repl_func, line)
            if new_line != line:
                changes.append((file_key, line.strip(), new_line.strip(), path))
                changed = True
            new_lines.append(new_line)

        if changed and not dry_run:
            backup_file(path)
            path.write_text("".join(new_lines), encoding="utf-8")

    # CURRENT_STATE.md — "N skills" (more complex line, use targeted approach)
    cs_path = COUNT_TARGETS.get("CURRENT_STATE")
    if cs_path and cs_path.exists():
        content = cs_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        new_lines = []
        changed = False

        for line in lines:
            # Match the Infrastructure section line with skill count
            if (
                "skills" in line.lower()
                and "agents" in line.lower()
                and ("MCP" in line or "hooks" in line)
            ):
                # This is the infrastructure summary line
                new_line = re.sub(r"(\d+)\s+skills\b", f"{n_skills} skills", line)
                new_line = re.sub(r"(\d+)\s+agents\b", f"{n_agents} agents", new_line)
                if new_line != line:
                    changes.append(
                        (
                            "CURRENT_STATE",
                            line.strip()[:80] + "...",
                            new_line.strip()[:80] + "...",
                            cs_path,
                        )
                    )
                    changed = True
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        if changed and not dry_run:
            backup_file(cs_path)
            cs_path.write_text("".join(new_lines), encoding="utf-8")

    # WORKFLOW.md — "N agents ... N skills" on the installed line
    wf_path = COUNT_TARGETS.get("WORKFLOW")
    if wf_path and wf_path.exists():
        content = wf_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        new_lines = []
        changed = False

        for line in lines:
            if (
                "agents" in line.lower()
                and "skills" in line.lower()
                and "installed" in line.lower()
            ):
                new_line = re.sub(r"(\d+)\s+agents\b", f"{n_agents} agents", line)
                new_line = re.sub(r"(\d+)\s+skills\b", f"{n_skills} skills", new_line)
                if new_line != line:
                    changes.append(
                        ("WORKFLOW", line.strip(), new_line.strip(), wf_path)
                    )
                    changed = True
                new_lines.append(new_line)
            else:
                new_lines.append(line)

        if changed and not dry_run:
            backup_file(wf_path)
            wf_path.write_text("".join(new_lines), encoding="utf-8")

    return changes


# ──────────────────────────────────────────────
# Backup
# ──────────────────────────────────────────────


def backup_file(path):
    """Backup a file before modifying it."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = date.today().isoformat()
    backup_name = f"{path.stem}_{timestamp}{path.suffix}"
    backup_path = BACKUP_DIR / backup_name
    # Don't overwrite existing backup from same day
    if not backup_path.exists():
        shutil.copy2(path, backup_path)


# ──────────────────────────────────────────────
# Registry diff
# ──────────────────────────────────────────────


def diff_registry(new_registry):
    """Compare new registry against existing one. Return changes."""
    changes = []
    old = load_existing_registry()
    old_names = set(old.keys())
    new_names = {s["name"] for s in new_registry["skills"]}

    added = new_names - old_names
    removed = old_names - new_names

    for name in sorted(added):
        changes.append(f"  + ADD skill: {name}")
    for name in sorted(removed):
        changes.append(f"  - REMOVE skill: {name}")

    # Check count changes
    if REGISTRY_PATH.exists():
        try:
            with open(REGISTRY_PATH) as f:
                old_data = json.load(f)
            old_count = old_data.get("counts", {}).get("total_skills", 0)
            new_count = new_registry["counts"]["total_skills"]
            if old_count != new_count:
                changes.append(f"  ~ COUNT: {old_count} -> {new_count} skills")
        except Exception:
            pass

    return changes


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Registry Sync — rebuild registry.json and propagate counts"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Write changes (default is dry-run)"
    )
    parser.add_argument(
        "--registry", action="store_true", help="Only rebuild registry.json"
    )
    parser.add_argument("--counts", action="store_true", help="Only propagate counts")
    parser.add_argument("--json", action="store_true", help="Output JSON summary")

    args = parser.parse_args()
    dry_run = not args.apply
    do_registry = not args.counts  # registry unless --counts only
    do_counts = not args.registry  # counts unless --registry only

    # Scan disk
    disk_state = scan_disk()
    counts = compute_counts(disk_state)

    if not args.json:
        print("Registry Sync")
        print("=" * 40)
        print(f"Skills on disk: {counts['skills']}")
        print(f"Frozen skills:  {counts['frozen']}")
        print(f"Agents on disk: {counts['agents']}")
        print()

    all_changes = []

    # Registry rebuild
    if do_registry:
        new_registry = rebuild_registry(disk_state)
        registry_changes = diff_registry(new_registry)

        if registry_changes:
            if not args.json:
                print("Registry changes:")
                for c in registry_changes:
                    print(c)
                print()
            all_changes.extend(registry_changes)

            if not dry_run:
                backup_file(REGISTRY_PATH)
                with open(REGISTRY_PATH, "w") as f:
                    json.dump(new_registry, f, indent=2)
                if not args.json:
                    print(f"  Written: {REGISTRY_PATH}")
        else:
            if not args.json:
                print("Registry: no changes needed.")
                print()

    # Count propagation
    if do_counts:
        count_changes = propagate_counts(counts, dry_run=dry_run)

        if count_changes:
            if not args.json:
                print("Count propagation:")
                for file_key, old, new, path in count_changes:
                    print(f"  [{file_key}]")
                    print(f"    - {old}")
                    print(f"    + {new}")
                print()
            all_changes.extend([f"{fk}: {o} -> {n}" for fk, o, n, _ in count_changes])

            if dry_run and not args.json:
                print("DRY RUN — no files modified. Use --apply to write.")
        else:
            if not args.json:
                print("Counts: no changes needed.")

    if args.json:
        result = {
            "disk": {
                "skills": counts["skills"],
                "frozen": counts["frozen"],
                "agents": counts["agents"],
            },
            "changes": all_changes,
            "applied": not dry_run,
        }
        print(json.dumps(result, indent=2))

    if not all_changes and not args.json:
        print("\nAll in sync.")

    return 0 if not all_changes else 1


if __name__ == "__main__":
    sys.exit(main())
