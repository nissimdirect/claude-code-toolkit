#!/usr/bin/env python3
"""
Index circuit modeling articles into knowledge.db (SQLite FTS5).
Reads scraped markdown articles and inserts them into the existing DB.
Zero tokens — pure code execution.

Usage:
    python3 index_circuit_modeling.py           # Index all articles
    python3 index_circuit_modeling.py --dry-run  # Show what would be indexed
    python3 index_circuit_modeling.py --count     # Show current count
"""

import os
import sys
import re
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

DB_PATH = os.path.expanduser("~/Development/knowledge.db")
CIRCUIT_DIR = os.path.expanduser("~/Development/circuit-modeling")

# Category → skill mapping
CATEGORY_SKILL_MAP = {
    "wdf": "cto",
    "va": "cto",
    "spice": "cto",
    "nodal": "cto",
    "newton-raphson": "cto",
    "schematics": "audio-production",
    "distortion": "audio-production",
    "space-echo": "audio-production",
    "spring-reverb": "audio-production",
    "ml": "cto",
    "whitebox": "cto",
    "textbooks": "cto",
    "juce": "cto",
    "clippers": "cto",
}

# Category → source name
CATEGORY_SOURCE_MAP = {
    "wdf": "Circuit Modeling — WDF",
    "va": "Circuit Modeling — VA",
    "spice": "Circuit Modeling — SPICE",
    "nodal": "Circuit Modeling — Nodal Analysis",
    "newton-raphson": "Circuit Modeling — Newton-Raphson",
    "schematics": "Circuit Modeling — Schematics",
    "distortion": "Circuit Modeling — Distortion",
    "space-echo": "Circuit Modeling — Space Echo",
    "spring-reverb": "Circuit Modeling — Spring Reverb",
    "ml": "Circuit Modeling — ML/Neural",
    "whitebox": "Circuit Modeling — White-Box",
    "textbooks": "Circuit Modeling — EE Textbooks",
    "juce": "Circuit Modeling — JUCE",
    "clippers": "Circuit Modeling — Clippers/Waveshapers",
}


def extract_frontmatter(content):
    """Extract YAML frontmatter from markdown."""
    meta = {}
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            fm = content[3:end].strip()
            for line in fm.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta


def get_title(content, filepath, meta):
    """Extract title from frontmatter or first heading."""
    if "title" in meta and meta["title"]:
        return meta["title"]

    # Try first H1
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Fallback to filename
    return filepath.stem.replace("-", " ").replace("_", " ").title()


def get_source_url(meta):
    """Extract source URL from frontmatter."""
    return meta.get("source", meta.get("url", ""))


def index_articles(dry_run=False):
    """Index all circuit modeling articles into knowledge.db."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    articles_dir = Path(CIRCUIT_DIR) / "articles"
    forums_dir = Path(CIRCUIT_DIR) / "forums"

    indexed = 0
    skipped = 0
    errors = 0

    # Collect all .md files from articles/ and forums/
    md_files = []
    if articles_dir.exists():
        md_files.extend(articles_dir.rglob("*.md"))
    if forums_dir.exists():
        md_files.extend(forums_dir.rglob("*.md"))

    print(f"Found {len(md_files)} markdown files to index")
    if dry_run:
        for f in sorted(md_files):
            rel = f.relative_to(Path(CIRCUIT_DIR))
            print(f"  [DRY-RUN] {rel}")
        return

    for filepath in sorted(md_files):
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            if len(content.strip()) < 50:
                skipped += 1
                continue

            file_hash = hashlib.md5(content.encode()).hexdigest()

            # Check if already indexed
            cur.execute("SELECT id FROM articles WHERE file_path = ?", (str(filepath),))
            if cur.fetchone():
                skipped += 1
                continue

            meta = extract_frontmatter(content)
            title = get_title(content, filepath, meta)
            source_url = get_source_url(meta)

            # Determine category from path
            rel = filepath.relative_to(Path(CIRCUIT_DIR))
            parts = rel.parts
            if parts[0] == "articles" and len(parts) > 1:
                category = parts[1]
            elif parts[0] == "forums":
                category = "forums"
            else:
                category = "general"

            source = CATEGORY_SOURCE_MAP.get(category, f"Circuit Modeling — {category}")
            skill = CATEGORY_SKILL_MAP.get(category, "cto")
            word_count = len(content.split())

            cur.execute("""
                INSERT INTO articles (
                    file_path, file_hash, title, author, source, source_url,
                    skill, date_scraped, date_indexed, type, content, word_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(filepath),
                file_hash,
                title,
                meta.get("author", "Unknown"),
                source,
                source_url,
                skill,
                meta.get("scraped", datetime.now().isoformat()),
                datetime.now().isoformat(),
                "article",
                content,
                word_count,
            ))

            indexed += 1

        except Exception as e:
            errors += 1
            print(f"  ERROR: {filepath.name}: {e}")

    conn.commit()

    # Update FTS index
    try:
        cur.execute("INSERT INTO articles_fts(articles_fts) VALUES('rebuild')")
        conn.commit()
    except Exception:
        pass  # FTS might not exist or might auto-update

    conn.close()

    print(f"\nIndexing complete:")
    print(f"  Indexed: {indexed}")
    print(f"  Skipped: {skipped} (already indexed or too small)")
    print(f"  Errors:  {errors}")
    print(f"  Total in DB: {get_count()}")


def get_count():
    """Get total article count."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM articles")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM articles WHERE source LIKE 'Circuit Modeling%'")
    circuit = cur.fetchone()[0]
    conn.close()
    return f"{total} total ({circuit} circuit modeling)"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Index circuit modeling into knowledge.db")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be indexed")
    parser.add_argument("--count", action="store_true", help="Show current count")
    args = parser.parse_args()

    if args.count:
        print(f"Articles in DB: {get_count()}")
        return

    index_articles(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
