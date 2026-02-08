#!/usr/bin/env python3
"""
PopChaos Labs - Ecosystem Consistency Checker v2.0
Detects stale data, broken references, and cross-file inconsistencies.
Includes dependency graph, propagation map, and staleness detection.

Usage:
    python consistency_checker.py              # Full check + propagation map
    python consistency_checker.py --json       # Output JSON for programmatic use
    python consistency_checker.py --summary    # One-line summary only
    python consistency_checker.py --deps       # Show dependency graph only
    python consistency_checker.py --save       # Save report to Obsidian vault

Checks:
    1. Article counts across all files vs actual disk counts
    2. Skill counts/names across registry, SESSION_INIT, DIRECTORY, etc.
    3. Skill files on disk vs registry.json
    4. Registry skill descriptions vs actual counts
    5. File path references (do referenced paths exist?)
    6. Date staleness (overdue recurring tasks, stale files)
    7. Cross-file data agreement (roadmap counts, company names)
    8. SESSION_INIT completeness (all skills/docs referenced?)
    9. Audio terminology correctness (LUFS not RMS)
   10. Git repo status for key directories
   11. Cron job setup for recurring tasks

Design: Code > Tokens. Run this script instead of burning tokens
re-reading files to check consistency.
"""

import os
import re
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

HOME = Path.home()
OBSIDIAN = HOME / "Documents" / "Obsidian"
SKILLS_DIR = HOME / ".claude" / "skills"
MEMORY_DIR = HOME / ".claude" / "projects" / "-Users-nissimagent" / "memory"
TOOLS_DIR = HOME / "Development" / "tools"
DEV_DIR = HOME / "Development"

# All ecosystem files (keyed for reference in reports)
ECOSYSTEM_FILES = {
    "SESSION_INIT": MEMORY_DIR / "SESSION_INIT.md",
    "MEMORY": MEMORY_DIR / "MEMORY.md",
    "CLAUDE_MD": HOME / ".claude" / "CLAUDE.md",
    "ACTIVE_TASKS": OBSIDIAN / "ACTIVE-TASKS.md",
    "MASTER_ROADMAP": OBSIDIAN / "MASTER-ROADMAP-RANKING.md",
    "DIRECTORY": OBSIDIAN / "DIRECTORY.md",
    "CRITICAL_CONTEXT": OBSIDIAN / "CRITICAL-CONTEXT.md",
    "ECOSYSTEM_STATUS": OBSIDIAN / "Claude-Ecosystem-Status.md",
    "RECURRING_TASKS": OBSIDIAN / "RECURRING-TASKS.md",
    "CONTEXT_MEMORY": OBSIDIAN / "CONTEXT-MEMORY-SYSTEM.md",
    "TASK_LOG": OBSIDIAN / "TASK-LOG.md",
    "REGISTRY": SKILLS_DIR / "registry.json",
}

# Knowledge base directories (source of truth for article counts)
KNOWLEDGE_BASES = {
    "lenny": {
        "label": "Lenny Rachitsky",
        "path": DEV_DIR / "lennys-podcast-transcripts",
        "count_dir": "episodes",
        "type": "episodes",
    },
    "cherie": {
        "label": "Cherie Hu / Water & Music",
        "path": DEV_DIR / "cherie-hu",
        "count_dir": "articles",
        "type": "articles",
    },
    "jesse": {
        "label": "Jesse Cannon",
        "path": DEV_DIR / "jesse-cannon",
        "count_dir": "articles",
        "type": "articles",
    },
    "chatprd": {
        "label": "ChatPRD",
        "path": DEV_DIR / "chatprd-blog",
        "count_dir": "articles",
        "type": "articles",
    },
    "pieter": {
        "label": "Pieter Levels",
        "path": DEV_DIR / "indie-hackers" / "pieter-levels",
        "count_dir": "articles",
        "type": "articles",
    },
    "justin": {
        "label": "Justin Welsh",
        "path": DEV_DIR / "indie-hackers" / "justin-welsh",
        "count_dir": "articles",
        "type": "articles",
    },
    "daniel": {
        "label": "Daniel Vassallo",
        "path": DEV_DIR / "indie-hackers" / "daniel-vassallo",
        "count_dir": "articles",
        "type": "articles",
    },
}

# Map skill names to knowledge base keys (for count validation)
SKILL_TO_KB = {
    "ask-lenny": "lenny",
    "ask-cherie": "cherie",
    "ask-jesse": "jesse",
    "ask-chatprd": "chatprd",
}

# Files that reference article counts (by ecosystem key)
COUNT_REFERENCE_KEYS = [
    "SESSION_INIT",
    "MEMORY",
    "DIRECTORY",
    "CRITICAL_CONTEXT",
    "ECOSYSTEM_STATUS",
    "CONTEXT_MEMORY",
]

# Also check these non-keyed files
COUNT_REFERENCE_EXTRAS = [
    SKILLS_DIR / "self-improve" / "SKILL.md",
]

# Critical paths that should exist
EXPECTED_PATHS = [
    HOME / ".claude" / "CLAUDE.md",
    OBSIDIAN / "ACTIVE-TASKS.md",
    OBSIDIAN / "MASTER-ROADMAP-RANKING.md",
    OBSIDIAN / "ROADMAP.md",
    OBSIDIAN / "CRITICAL-CONTEXT.md",
    OBSIDIAN / "DIRECTORY.md",
    OBSIDIAN / "RECURRING-TASKS.md",
    OBSIDIAN / "RESOURCE-TRACKER.md",
    MEMORY_DIR / "SESSION_INIT.md",
    MEMORY_DIR / "MEMORY.md",
    SKILLS_DIR / "registry.json",
    TOOLS_DIR / "scraper.py",
    TOOLS_DIR / "auto_tag_corpus.py",
    TOOLS_DIR / "track_resources.py",
    DEV_DIR / "JUCE" / "JUCE",
]


# ──────────────────────────────────────────────
# Dependency Graph (the core design artifact)
# ──────────────────────────────────────────────

DEPENDENCY_GRAPH = {
    "skill_added": {
        "description": "New skill directory added to ~/.claude/skills/<name>/SKILL.md",
        "updates": [
            ("registry.json", "Add skill entry with name, path, description, categories"),
            ("SESSION_INIT.md", "Update skill count in 'Skills Arsenal (N Skills)' header + add row to skill table"),
            ("DIRECTORY.md", "Add skill to appropriate section in Skills Menu"),
            ("Claude-Ecosystem-Status.md", "Update Skills Inventory section and total count"),
            ("CRITICAL-CONTEXT.md", "Update Skills Inventory count and list"),
        ],
    },
    "skill_removed": {
        "description": "Skill directory deleted from ~/.claude/skills/",
        "updates": [
            ("registry.json", "Remove skill entry"),
            ("SESSION_INIT.md", "Update skill count + remove from skill table"),
            ("DIRECTORY.md", "Remove from Skills Menu"),
            ("Claude-Ecosystem-Status.md", "Update Skills Inventory"),
            ("CRITICAL-CONTEXT.md", "Update count and list"),
        ],
    },
    "article_count_changed": {
        "description": "Knowledge base article count changed (after scrape or cleanup)",
        "updates": [
            ("registry.json", "Update affected skill description with new count"),
            ("SESSION_INIT.md", "Update Knowledge Bases table: per-source counts + TOTAL row"),
            ("DIRECTORY.md", "Update Knowledge Bases section: per-source counts + total"),
            ("CRITICAL-CONTEXT.md", "Update advisor counts in Skills Inventory"),
            ("Claude-Ecosystem-Status.md", "Update advisor article counts"),
            ("self-improve/SKILL.md", "Update Training Data Audit section counts"),
            ("Affected ask-*/SKILL.md", "Update data count in skill header/instructions"),
        ],
    },
    "task_completed": {
        "description": "A project task is marked complete",
        "updates": [
            ("ACTIVE-TASKS.md", "Check box [x], move to Completed section"),
            ("TASK-LOG.md", "Append completion entry with date, tokens, cost, outcome"),
            ("SESSION_INIT.md", "Update Current Project Status table (status column)"),
            ("MASTER-ROADMAP-RANKING.md", "Add completion marker to Top 10 section"),
        ],
    },
    "learning_captured": {
        "description": "New learning, pattern, or mistake discovered",
        "updates": [
            ("MEMORY.md", "Add to appropriate section (Patterns, Mistakes, etc.)"),
            ("SESSION_INIT.md", "Update if it changes session protocol or workflow rules"),
            ("CLAUDE.md", "Update if it changes build commands, code style, or workflows"),
            ("self-improve/SKILL.md", "Update if it changes audit criteria or red flags"),
        ],
    },
    "prd_written": {
        "description": "New PRD document created in ~/Documents/Obsidian/PRDs/",
        "updates": [
            ("DIRECTORY.md", "Add to PRD list"),
            ("ACTIVE-TASKS.md", "Mark 'Write PRD for X' as complete if it was a task"),
            ("SESSION_INIT.md", "Update 'PRDs Written' list"),
        ],
    },
    "tool_built": {
        "description": "New Python/Bash tool created in ~/Development/tools/",
        "updates": [
            ("SESSION_INIT.md", "Add to 'Tools Built' table"),
            ("DIRECTORY.md", "Add to 'Tools & Infrastructure' section"),
            ("CLAUDE.md", "Add build/run commands if user needs them"),
        ],
    },
    "roadmap_reprioritized": {
        "description": "Roadmap items re-ranked or re-scored",
        "updates": [
            ("MASTER-ROADMAP-RANKING.md", "Update full ranking table and Top 10 section"),
            ("ACTIVE-TASKS.md", "Reorder Next Up section based on new ranks"),
            ("SESSION_INIT.md", "Update Execution Sequence table"),
        ],
    },
    "session_ended": {
        "description": "Work session ending (run /session-end)",
        "updates": [
            ("TASK-LOG.md", "Append session summary with totals"),
            ("ACTIVE-TASKS.md", "Update all task statuses (in-progress, completed, blocked)"),
            ("MEMORY.md", "Capture any new learnings from this session"),
            ("RECURRING-TASKS.md", "Update 'Last Run' dates for any maintenance performed"),
        ],
    },
}


# ──────────────────────────────────────────────
# Issue class
# ──────────────────────────────────────────────

class Issue:
    def __init__(self, severity, file_ref, message, expected=None, actual=None,
                 line_num=None, fixable=False, fix_hint=None):
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW
        self.file_ref = str(file_ref)
        self.message = message
        self.expected = expected
        self.actual = actual
        self.line_num = line_num
        self.fixable = fixable
        self.fix_hint = fix_hint

    def __str__(self):
        loc = self.file_ref
        if self.line_num:
            loc += f":{self.line_num}"
        detail = ""
        if self.expected is not None and self.actual is not None:
            detail = f" (expected: {self.expected}, found: {self.actual})"
        fix = ""
        if self.fix_hint:
            fix = f"\n      Fix: {self.fix_hint}"
        tag = " [FIXABLE]" if self.fixable else ""
        return f"  [{self.severity}] {loc}: {self.message}{detail}{tag}{fix}"

    def to_dict(self):
        return {
            "severity": self.severity,
            "file": self.file_ref,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
            "line": self.line_num,
            "fixable": self.fixable,
            "fix_hint": self.fix_hint,
        }


# ──────────────────────────────────────────────
# Disk counting (source of truth)
# ──────────────────────────────────────────────

def count_articles(base_path, subdir, content_type):
    """Count items in a knowledge base directory."""
    target = base_path / subdir if subdir else base_path
    if not target.exists():
        return 0
    if content_type == "episodes":
        return len([d for d in target.iterdir() if d.is_dir() and not d.name.startswith('.')])
    else:
        return len(list(target.glob("*.md")))


def get_actual_counts():
    """Get real article counts from filesystem (ground truth)."""
    actual = {}
    for key, info in KNOWLEDGE_BASES.items():
        actual[key] = count_articles(info["path"], info["count_dir"], info["type"])
    actual["total"] = sum(actual.values())
    actual["indie_total"] = actual.get("pieter", 0) + actual.get("justin", 0) + actual.get("daniel", 0)
    return actual


def get_disk_skills():
    """Get all skills on disk (directory/SKILL.md format)."""
    if not SKILLS_DIR.exists():
        return set()
    return {f.parent.name for f in SKILLS_DIR.glob("*/SKILL.md") if f.is_file()}


def get_registry_data():
    """Get skills from registry.json."""
    registry_path = SKILLS_DIR / "registry.json"
    if not registry_path.exists():
        return [], {}
    try:
        with open(registry_path) as f:
            data = json.load(f)
        skills = data.get("skills", [])
        names = [s["name"] for s in skills]
        by_name = {s["name"]: s for s in skills}
        return names, by_name
    except Exception:
        return [], {}


def load_file_by_key(key):
    """Load an ecosystem file's content by key."""
    path = ECOSYSTEM_FILES.get(key)
    if path and path.exists():
        return path.read_text(encoding="utf-8")
    return None


def load_file_by_path(path):
    """Load a file's content by path."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


# ──────────────────────────────────────────────
# Check: Article counts
# ──────────────────────────────────────────────

def check_article_counts(actual_counts):
    """Check all reference files for stale article counts.
    Uses line-by-line matching: number must appear on same line as source keyword.
    """
    issues = []

    source_keywords = {
        "lenny": ["lenny", "podcast episode", "podcast transcripts"],
        "cherie": ["cherie", "water & music", "water and music"],
        "jesse": ["jesse cannon", "jesse"],
        "chatprd": ["chatprd", "chat prd", "claire vo"],
        "pieter": ["pieter levels", "pieter"],
        "justin": ["justin welsh", "justin"],
        "daniel": ["daniel vassallo", "daniel"],
        "total": ["total article", "total:", "**total**"],
    }

    # Build list of (file_label, file_path) to check
    files_to_check = []
    for key in COUNT_REFERENCE_KEYS:
        path = ECOSYSTEM_FILES.get(key)
        if path:
            files_to_check.append((key, path))
    for path in COUNT_REFERENCE_EXTRAS:
        files_to_check.append((path.name, path))

    for file_label, file_path in files_to_check:
        if not file_path.exists():
            issues.append(Issue("HIGH", file_label, f"File does not exist: {file_path}"))
            continue

        lines = file_path.read_text(encoding="utf-8").splitlines()

        for line_num, line in enumerate(lines, 1):
            line_lower = line.lower()

            for source, keywords in source_keywords.items():
                expected = actual_counts.get(source, 0)
                if expected == 0:
                    continue

                if not any(kw in line_lower for kw in keywords):
                    continue

                # Extract all numbers from this line
                numbers = []
                for n in re.findall(r'[\d,]+', line):
                    clean = n.replace(',', '')
                    if clean.isdigit():
                        numbers.append(int(clean))

                for num in numbers:
                    if num < 8 and source != "daniel":
                        continue
                    if 2020 <= num <= 2030:
                        continue
                    if num == expected:
                        continue
                    if abs(num - expected) <= 3:
                        continue

                    # --- False positive filters ---

                    # Find where this number appears on the line
                    num_str = str(num)
                    num_idx = line.find(num_str)
                    if num_idx < 0:
                        # Try comma-formatted
                        num_str = f"{num:,}"
                        num_idx = line.find(num_str)

                    # Context after the number (next 25 chars)
                    context_after = line_lower[num_idx:num_idx+len(num_str)+25] if num_idx >= 0 else ""

                    # Skip numbers followed by "topic", "index" (e.g. "89 topic indexes")
                    if any(w in context_after for w in ['topic', 'index']):
                        continue

                    # Skip numbers followed by "project", "item" (roadmap counts)
                    if any(w in context_after for w in ['project', 'item']):
                        continue

                    # Skip numbers followed by "skill" (skill counts, not article)
                    if 'skill' in context_after:
                        continue

                    # Skip "combined" lines for individual sources
                    if source in ('pieter', 'justin', 'daniel') and 'combined' in line_lower:
                        continue

                    # Skip token economics lines (contain $, tokens, ~XXK)
                    if any(p in line_lower for p in ['$', 'tokens', 'token cost', 'roi', 'cost per']):
                        continue

                    # Skip multi-source lines entirely: if 3+ different source keywords
                    # appear on one line, it's an aggregate/breakdown line where the checker
                    # can't reliably determine which number belongs to which source.
                    sources_on_line = [s for s, kws in source_keywords.items()
                                       if s != 'total' and any(kw in line_lower for kw in kws)]
                    if len(sources_on_line) >= 3:
                        continue

                    label = KNOWLEDGE_BASES.get(source, {}).get("label", source)
                    issues.append(Issue(
                        "HIGH", file_label,
                        f"Stale count for {label}",
                        expected=expected, actual=num,
                        line_num=line_num, fixable=True,
                        fix_hint=f"Update {num} -> {expected}",
                    ))

    return issues


# ──────────────────────────────────────────────
# Check: Skill consistency
# ──────────────────────────────────────────────

def check_skill_consistency(disk_skills, registry_names, registry_by_name, actual_counts):
    """Check skills across registry, disk, and documentation files."""
    issues = []
    registry_set = set(registry_names)

    # 1. Registry vs disk
    missing_from_registry = disk_skills - registry_set
    missing_from_disk = registry_set - disk_skills

    for skill in sorted(missing_from_registry):
        issues.append(Issue(
            "HIGH", "registry.json",
            f"Skill '{skill}' on disk but NOT in registry.json",
            fixable=True,
            fix_hint=f"Add '{skill}' entry to registry.json",
        ))

    for skill in sorted(missing_from_disk):
        issues.append(Issue(
            "CRITICAL", "registry.json",
            f"Skill '{skill}' in registry but SKILL.md MISSING from disk",
        ))

    # 2. Registry skill descriptions: check article counts
    for skill_name, kb_key in SKILL_TO_KB.items():
        if skill_name not in registry_by_name:
            continue
        desc = registry_by_name[skill_name].get("description", "")
        type_word = KNOWLEDGE_BASES[kb_key]["type"]
        count_match = re.search(r'(\d[\d,]*)\+?\s*' + type_word, desc)
        if count_match:
            raw = count_match.group(1).replace(",", "")
            try:
                desc_count = int(raw)
            except ValueError:
                continue
            actual = actual_counts.get(kb_key, 0)
            if desc_count != actual and abs(desc_count - actual) > 2:
                issues.append(Issue(
                    "MEDIUM", "registry.json",
                    f"Skill '{skill_name}' description count stale",
                    expected=actual, actual=desc_count,
                    fixable=True,
                    fix_hint=f"Update description: {desc_count} -> {actual} {type_word}",
                ))

    # 3. Skill count in SESSION_INIT header
    content = load_file_by_key("SESSION_INIT")
    if content:
        match = re.search(r'Skills Arsenal \((\d+) Skills?\)', content)
        if match:
            stated = int(match.group(1))
            actual_count = len(disk_skills)
            if stated != actual_count:
                issues.append(Issue(
                    "HIGH", "SESSION_INIT",
                    "Skills Arsenal count stale",
                    expected=actual_count, actual=stated,
                    fixable=True,
                    fix_hint=f"Update '({stated} Skills)' -> '({actual_count} Skills)'",
                ))

    # 4. Skill count in CRITICAL_CONTEXT
    content = load_file_by_key("CRITICAL_CONTEXT")
    if content:
        match = re.search(r'(\d+)\s*[Tt]otal\)?', content)
        if match:
            stated = int(match.group(1))
            actual_count = len(disk_skills)
            if abs(stated - actual_count) > 1:
                issues.append(Issue(
                    "MEDIUM", "CRITICAL_CONTEXT",
                    "Skill count stale",
                    expected=actual_count, actual=stated,
                    fixable=True,
                ))

    # 5. Skill count in ECOSYSTEM_STATUS
    content = load_file_by_key("ECOSYSTEM_STATUS")
    if content:
        match = re.search(r'[Tt]otal:?\s*(\d+)\s*skills?', content)
        if match:
            stated = int(match.group(1))
            actual_count = len(disk_skills)
            if stated != actual_count:
                issues.append(Issue(
                    "MEDIUM", "ECOSYSTEM_STATUS",
                    "Skill count stale",
                    expected=actual_count, actual=stated,
                    fixable=True,
                ))

    # 6. All disk skills should be mentioned in SESSION_INIT
    content = load_file_by_key("SESSION_INIT")
    if content:
        for skill_name in sorted(disk_skills):
            if skill_name not in content:
                issues.append(Issue(
                    "MEDIUM", "SESSION_INIT",
                    f"Skill '/{skill_name}' on disk but not in SESSION_INIT.md",
                ))

    # 7. All disk skills should be mentioned in DIRECTORY
    content = load_file_by_key("DIRECTORY")
    if content:
        for skill_name in sorted(disk_skills):
            if skill_name not in content:
                issues.append(Issue(
                    "MEDIUM", "DIRECTORY",
                    f"Skill '/{skill_name}' on disk but not in DIRECTORY.md",
                ))

    # 8. Skills referenced in docs that don't exist on disk
    for doc_key in ["SESSION_INIT", "DIRECTORY"]:
        content = load_file_by_key(doc_key)
        if not content:
            continue
        mentioned = set(re.findall(r'`/([a-z][a-z0-9-]+)`', content))
        for skill_name in sorted(mentioned):
            if skill_name not in disk_skills and skill_name not in registry_set:
                # Check common aliases
                if skill_name == "ask-trinity" and "ask-indie-trinity" in disk_skills:
                    issues.append(Issue(
                        "MEDIUM", doc_key,
                        f"References '/{skill_name}' but skill is actually named '/ask-indie-trinity'",
                        fixable=True,
                    ))
                else:
                    issues.append(Issue(
                        "LOW", doc_key,
                        f"References '/{skill_name}' which doesn't exist",
                    ))

    return issues


# ──────────────────────────────────────────────
# Check: File paths exist
# ──────────────────────────────────────────────

def check_file_paths():
    """Verify all expected file paths exist."""
    issues = []
    for path in EXPECTED_PATHS:
        if not path.exists():
            issues.append(Issue(
                "MEDIUM", "DISK",
                f"Expected path does not exist: {path}",
            ))
    return issues


# ──────────────────────────────────────────────
# Check: Date staleness
# ──────────────────────────────────────────────

def check_staleness():
    """Check for overdue recurring tasks and stale files."""
    issues = []
    today = datetime.now()

    # Check RECURRING-TASKS.md for overdue items
    content = load_file_by_key("RECURRING_TASKS")
    if content:
        for match in re.finditer(r'\*\*Next Run:\*\*\s*(\d{4}-\d{2}-\d{2})', content):
            try:
                next_run = datetime.strptime(match.group(1), '%Y-%m-%d')
                if next_run < today:
                    days_overdue = (today - next_run).days
                    issues.append(Issue(
                        "HIGH", "RECURRING_TASKS",
                        f"Overdue recurring task (due {match.group(1)}, {days_overdue} days overdue)",
                    ))
            except ValueError:
                pass

    # Check key files for modification staleness
    stale_threshold = timedelta(days=14)
    for key in ["ECOSYSTEM_STATUS", "DIRECTORY"]:
        path = ECOSYSTEM_FILES.get(key)
        if not path or not path.exists():
            continue
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        age = today - mtime
        if age > stale_threshold:
            issues.append(Issue(
                "LOW", key,
                f"File not modified in {age.days} days (may be stale)",
            ))

    return issues


# ──────────────────────────────────────────────
# Check: Cross-file agreement
# ──────────────────────────────────────────────

def check_cross_file_agreement():
    """Check that facts agree across multiple files."""
    issues = []

    # Roadmap item count consistency
    roadmap_counts = {}
    for key in ["SESSION_INIT", "MASTER_ROADMAP", "DIRECTORY", "RECURRING_TASKS"]:
        content = load_file_by_key(key)
        if not content:
            continue
        for match in re.finditer(
            r'(?:[Aa]ll\s+)?(\d{2,3})\s*(?:projects?|items?)\s*(?:scored|ranked|identified|analyzed|roadmap)?',
            content
        ):
            count = int(match.group(1))
            if 60 <= count <= 100:
                roadmap_counts[key] = count
                break

    if len(set(roadmap_counts.values())) > 1:
        most_common = max(set(roadmap_counts.values()), key=list(roadmap_counts.values()).count)
        for key, count in roadmap_counts.items():
            if count != most_common:
                issues.append(Issue(
                    "MEDIUM", key,
                    "Roadmap item count disagrees with other files",
                    expected=most_common, actual=count,
                    fixable=True,
                ))

    # Sessions completed in ECOSYSTEM_STATUS
    content = load_file_by_key("ECOSYSTEM_STATUS")
    if content:
        match = re.search(r'Sessions Completed:\s*(\d+)', content)
        if match:
            stated = int(match.group(1))
            task_log = load_file_by_key("TASK_LOG")
            if task_log:
                session_count = len(re.findall(r'## \d{4}-\d{2}-\d{2} \(Session \d+\)', task_log))
                if session_count > stated:
                    issues.append(Issue(
                        "LOW", "ECOSYSTEM_STATUS",
                        "Sessions Completed is stale",
                        expected=session_count, actual=stated,
                        fixable=True,
                    ))

    return issues


# ──────────────────────────────────────────────
# Check: Audio terminology
# ──────────────────────────────────────────────

def check_terminology():
    """Check for incorrect audio terminology."""
    issues = []
    keys_to_check = ["SESSION_INIT", "MEMORY", "CRITICAL_CONTEXT", "CLAUDE_MD"]

    for key in keys_to_check:
        content = load_file_by_key(key)
        if not content:
            continue
        if 'volume matching' in content.lower():
            issues.append(Issue(
                "MEDIUM", key,
                "Contains 'volume matching' -- should use 'loudness matching'",
            ))

    return issues


# ──────────────────────────────────────────────
# Check: SESSION_INIT completeness
# ──────────────────────────────────────────────

def check_session_init_completeness():
    """Verify SESSION_INIT has required sections and references all key files."""
    issues = []
    content = load_file_by_key("SESSION_INIT")
    if not content:
        issues.append(Issue("CRITICAL", "SESSION_INIT", "File does not exist"))
        return issues

    required_sections = [
        "Scan Protocol",
        "Who You Are Working With",
        "System Inventory",
        "Skills Arsenal",
        "Current Project Status",
        "Session Protocol",
    ]

    for section in required_sections:
        if section not in content:
            issues.append(Issue(
                "HIGH", "SESSION_INIT",
                f"Missing required section: '{section}'",
            ))

    # Check all Obsidian .md files are referenced
    if OBSIDIAN.exists():
        for md_file in sorted(OBSIDIAN.glob("*.md")):
            name = md_file.stem
            if name.endswith(".OLD") or name.startswith("SESSION-"):
                continue
            if name == "CONSISTENCY-REPORT":
                continue
            if name not in content and name.replace("-", " ") not in content:
                issues.append(Issue(
                    "LOW", "SESSION_INIT",
                    f"Obsidian doc '{name}.md' not referenced",
                ))

    return issues


# ──────────────────────────────────────────────
# Check: Git repos
# ──────────────────────────────────────────────

def check_git_repos():
    """Check that key directories are git repos."""
    issues = []
    should_be_repos = [TOOLS_DIR]
    for repo_path in should_be_repos:
        if repo_path.exists() and not (repo_path / ".git").exists():
            issues.append(Issue(
                "LOW", "DISK",
                f"Should be a git repo: {repo_path}",
                fix_hint=f"cd {repo_path} && git init",
            ))
    return issues


# ──────────────────────────────────────────────
# Check: Cron jobs
# ──────────────────────────────────────────────

def check_cron():
    """Check if expected cron jobs exist."""
    issues = []
    try:
        result = os.popen("crontab -l 2>/dev/null").read()
    except Exception:
        result = ""

    if "track_resources" not in result:
        issues.append(Issue("LOW", "SYSTEM", "Daily resource tracker cron not set up"))
    if "scrape-all" not in result:
        issues.append(Issue("LOW", "SYSTEM", "Monthly scrape cron not set up"))

    return issues


# ──────────────────────────────────────────────
# Report output
# ──────────────────────────────────────────────

def print_ground_truth(actual_counts, disk_skills, registry_names):
    """Print filesystem ground truth."""
    print()
    print("GROUND TRUTH (Filesystem = Source of Truth)")
    print("-" * 50)
    for kb_key in ["lenny", "cherie", "jesse", "chatprd", "pieter", "justin", "daniel"]:
        label = KNOWLEDGE_BASES[kb_key]["label"]
        count = actual_counts.get(kb_key, 0)
        t = KNOWLEDGE_BASES[kb_key]["type"]
        print(f"  {label:.<38} {count} {t}")
    print(f"  {'TOTAL':.<38} {actual_counts.get('total', 0)}")
    print(f"  {'Indie Trinity combined':.<38} {actual_counts.get('indie_total', 0)}")
    print()
    print(f"  Skills on disk: {len(disk_skills)}")
    print(f"    ({', '.join(sorted(disk_skills))})")
    print(f"  Skills in registry: {len(registry_names)}")
    if set(registry_names) != disk_skills:
        diff = disk_skills.symmetric_difference(set(registry_names))
        print(f"    MISMATCH: {diff}")
    print()


def print_issues(all_issues):
    """Print issues grouped by severity."""
    if not all_issues:
        print("ALL CLEAR -- No consistency issues found.")
        return

    severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    by_severity = defaultdict(list)
    for issue in all_issues:
        by_severity[issue.severity].append(issue)

    for severity in severity_order:
        group = by_severity.get(severity, [])
        if not group:
            continue
        print(f"{severity} ({len(group)} issues)")
        print("-" * 50)
        for issue in group:
            print(issue)
        print()

    total = len(all_issues)
    fixable = sum(1 for i in all_issues if i.fixable)
    crit = len(by_severity.get("CRITICAL", []))
    high = len(by_severity.get("HIGH", []))

    print("SUMMARY")
    print("-" * 50)
    print(f"  Critical: {crit}")
    print(f"  High:     {high}")
    print(f"  Medium:   {len(by_severity.get('MEDIUM', []))}")
    print(f"  Low:      {len(by_severity.get('LOW', []))}")
    print(f"  Total:    {total}")
    print(f"  Fixable:  {fixable}")
    print()


def print_dependency_graph():
    """Print the full propagation map."""
    print()
    print("PROPAGATION MAP")
    print("(When X changes, update Y)")
    print("=" * 55)
    print()

    for event_key, info in DEPENDENCY_GRAPH.items():
        print(f"WHEN: {info['description']}")
        for target, action in info["updates"]:
            print(f"  -> {target}: {action}")
        print()


def generate_markdown_report(all_issues, actual_counts, disk_skills, registry_names):
    """Generate markdown report for Obsidian vault."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sev = defaultdict(int)
    for i in all_issues:
        sev[i.severity] += 1
    fixable = sum(1 for i in all_issues if i.fixable)

    report = f"""# System Consistency Report

**Generated:** {now}
**Issues:** {len(all_issues)} ({sev['CRITICAL']} critical, {sev['HIGH']} high, {sev['MEDIUM']} medium, {sev['LOW']} low)
**Auto-Fixable:** {fixable}

---

## Ground Truth (Filesystem)

| Source | Count |
|--------|-------|
"""
    for kb_key in ["lenny", "cherie", "jesse", "chatprd", "pieter", "justin", "daniel"]:
        label = KNOWLEDGE_BASES[kb_key]["label"]
        count = actual_counts.get(kb_key, 0)
        report += f"| {label} | {count} |\n"
    report += f"| **TOTAL** | **{actual_counts.get('total', 0)}** |\n"
    report += f"\n**Skills on disk:** {len(disk_skills)}  \n"
    report += f"**Skills in registry:** {len(registry_names)}\n\n---\n\n"

    severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    for severity in severity_order:
        group = [i for i in all_issues if i.severity == severity]
        if not group:
            continue
        report += f"## {severity} ({len(group)})\n\n"
        for issue in group:
            detail = ""
            if issue.expected is not None and issue.actual is not None:
                detail = f" (expected: {issue.expected}, found: {issue.actual})"
            fix = ""
            if issue.fix_hint:
                fix = f" -- Fix: {issue.fix_hint}"
            report += f"- **{issue.file_ref}**: {issue.message}{detail}{fix}\n"
        report += "\n"

    if not all_issues:
        report += "## All Clear\n\nNo consistency issues detected.\n\n"

    # Add propagation map
    report += "---\n\n## Propagation Map\n\n"
    for event_key, info in DEPENDENCY_GRAPH.items():
        report += f"### {info['description']}\n"
        for target, action in info["updates"]:
            report += f"- **{target}**: {action}\n"
        report += "\n"

    report += f"\n---\n\n**Generated by:** `consistency_checker.py` v2.0  \n"
    report += f"**Related:** [[ACTIVE-TASKS]] | [[DIRECTORY]] | [[RECURRING-TASKS]]\n"
    return report


def output_json(all_issues, actual_counts, disk_skills, registry_names):
    """Output JSON report."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "ground_truth": {
            "article_counts": {
                kb_key: {
                    "label": KNOWLEDGE_BASES[kb_key]["label"],
                    "count": actual_counts.get(kb_key, 0),
                }
                for kb_key in KNOWLEDGE_BASES
            },
            "total_articles": actual_counts.get("total", 0),
            "indie_total": actual_counts.get("indie_total", 0),
            "skills_on_disk": sorted(disk_skills),
            "skills_in_registry": sorted(registry_names),
            "skill_count": len(disk_skills),
        },
        "issues": [i.to_dict() for i in all_issues],
        "summary": {
            "critical": sum(1 for i in all_issues if i.severity == "CRITICAL"),
            "high": sum(1 for i in all_issues if i.severity == "HIGH"),
            "medium": sum(1 for i in all_issues if i.severity == "MEDIUM"),
            "low": sum(1 for i in all_issues if i.severity == "LOW"),
            "total": len(all_issues),
            "fixable": sum(1 for i in all_issues if i.fixable),
        },
        "dependency_graph": {
            k: {"description": v["description"], "updates": v["updates"]}
            for k, v in DEPENDENCY_GRAPH.items()
        },
    }
    print(json.dumps(result, indent=2, default=str))


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="PopChaos Labs Ecosystem Consistency Checker v2.0")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--summary", action="store_true", help="One-line summary")
    parser.add_argument("--deps", action="store_true", help="Show dependency graph only")
    parser.add_argument("--save", action="store_true", help="Save report to Obsidian vault")

    args = parser.parse_args()

    if args.deps:
        print_dependency_graph()
        return

    quiet = args.json or args.summary

    if not quiet:
        print("PopChaos Labs Ecosystem Consistency Checker v2.0")
        print("=" * 55)
        print()
        print("[1/9] Counting actual articles on disk...")

    actual_counts = get_actual_counts()
    disk_skills = get_disk_skills()
    registry_names, registry_by_name = get_registry_data()

    if not quiet:
        print("[2/9] Checking article counts across files...")
    all_issues = check_article_counts(actual_counts)

    if not quiet:
        print("[3/9] Checking skill consistency...")
    all_issues += check_skill_consistency(disk_skills, registry_names, registry_by_name, actual_counts)

    if not quiet:
        print("[4/9] Checking file paths...")
    all_issues += check_file_paths()

    if not quiet:
        print("[5/9] Checking date staleness...")
    all_issues += check_staleness()

    if not quiet:
        print("[6/9] Checking cross-file agreement...")
    all_issues += check_cross_file_agreement()

    if not quiet:
        print("[7/9] Checking audio terminology...")
    all_issues += check_terminology()

    if not quiet:
        print("[8/9] Checking SESSION_INIT completeness...")
    all_issues += check_session_init_completeness()

    if not quiet:
        print("[9/9] Checking git repos and cron...")
    all_issues += check_git_repos()
    all_issues += check_cron()

    # Sort by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_issues.sort(key=lambda x: severity_order.get(x.severity, 99))

    # Output
    if args.json:
        output_json(all_issues, actual_counts, disk_skills, registry_names)
    elif args.summary:
        crit = sum(1 for i in all_issues if i.severity == "CRITICAL")
        high = sum(1 for i in all_issues if i.severity == "HIGH")
        total = len(all_issues)
        fixable = sum(1 for i in all_issues if i.fixable)
        print(f"Consistency: {total} issues ({crit} critical, {high} high) | {fixable} fixable")
    else:
        print()
        print_ground_truth(actual_counts, disk_skills, registry_names)
        print_issues(all_issues)
        print_dependency_graph()

    if args.save:
        report = generate_markdown_report(all_issues, actual_counts, disk_skills, registry_names)
        report_path = OBSIDIAN / "CONSISTENCY-REPORT.md"
        with open(report_path, 'w') as f:
            f.write(report)
        if not quiet:
            print(f"Report saved to: {report_path}")

    # Exit code: critical + high count (capped at 125)
    exit_count = sum(1 for i in all_issues if i.severity in ("CRITICAL", "HIGH"))
    sys.exit(min(exit_count, 125))


if __name__ == "__main__":
    main()
