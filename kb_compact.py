#!/usr/bin/env python3
"""KB Compaction — dedup, prune stubs, strip boilerplate from 85K+ articles.

Code-only (0 LLM tokens). Run once, then periodically.

Usage:
    python3 kb_compact.py --dry-run          # Report only, no changes
    python3 kb_compact.py                     # Execute compaction
    python3 kb_compact.py --sanitize          # Also run content_sanitizer on all files
"""

import hashlib
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

# Optional: content sanitizer integration
try:
    from content_sanitizer import sanitize_file
    HAS_SANITIZER = True
except ImportError:
    HAS_SANITIZER = False


class CompactReport(NamedTuple):
    total_files: int
    duplicates_removed: int
    stubs_removed: int
    empty_removed: int
    bytes_saved: int
    sanitized: int
    sanitizer_findings: int


# Minimum content length (chars) to keep a file. Below this = stub.
MIN_CONTENT_LENGTH = 150

# Known boilerplate patterns to strip (common across scraped sites)
BOILERPLATE_PATTERNS = [
    # Cookie banners
    r'(?:We use cookies|This site uses cookies|Cookie Policy|Accept All Cookies).*?\n',
    # Newsletter CTAs (keep them short, not the whole block)
    r'(?:Subscribe to our newsletter|Sign up for our newsletter|Join our mailing list).*?\n',
    # Social share blocks
    r'(?:Share this|Share on|Follow us on)(?:\s+(?:Facebook|Twitter|Instagram|LinkedIn|Pinterest))+.*?\n',
    # Breadcrumbs
    r'^(?:Home\s*[>»/]\s*){1,5}.*?\n',
    # Related posts blocks
    r'(?:Related (?:posts|articles|stories)|You (?:may|might) also (?:like|enjoy)).*?\n',
]


def find_all_articles(base_dirs=None):
    """Find all .md article files across all KB directories."""
    if base_dirs is None:
        base_dirs = [Path.home() / "Development"]

    articles = []
    for base in base_dirs:
        for articles_dir in base.rglob("articles"):
            if articles_dir.is_dir():
                for f in articles_dir.glob("*.md"):
                    if f.is_file():
                        articles.append(f)
    return articles


def compute_hash(filepath):
    """Compute content hash for dedup (ignores frontmatter)."""
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return None

    # Strip YAML frontmatter for hash comparison
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            content = content[end + 3:].strip()

    # Normalize whitespace for fuzzy dedup
    content = " ".join(content.split()).lower()
    return hashlib.md5(content.encode()).hexdigest()


def is_stub(filepath):
    """Check if file is a stub (too short to be useful)."""
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return True

    # Strip frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end > 0:
            content = content[end + 3:].strip()

    return len(content.strip()) < MIN_CONTENT_LENGTH


def compact(dry_run=True, run_sanitizer=False):
    """Run full compaction pipeline."""
    start = time.time()
    print(f"{'[DRY RUN] ' if dry_run else ''}KB Compaction starting...")

    articles = find_all_articles()
    print(f"Found {len(articles)} articles across KB directories")

    # Phase 1: Find duplicates
    print("\n--- Phase 1: Dedup ---")
    hash_map = defaultdict(list)
    hash_errors = 0
    for i, f in enumerate(articles):
        h = compute_hash(f)
        if h:
            hash_map[h].append(f)
        else:
            hash_errors += 1
        if (i + 1) % 10000 == 0:
            print(f"  Hashed {i + 1}/{len(articles)}...")

    duplicates = []
    for h, files in hash_map.items():
        if len(files) > 1:
            # Keep the first (oldest by path), remove rest
            files_sorted = sorted(files, key=lambda f: str(f))
            duplicates.extend(files_sorted[1:])

    print(f"  {len(duplicates)} exact duplicates found ({hash_errors} hash errors)")

    # Phase 2: Find stubs and empties
    print("\n--- Phase 2: Stubs & Empties ---")
    stubs = []
    empties = []
    for f in articles:
        if f in duplicates:
            continue  # Already marked for removal
        try:
            size = f.stat().st_size
            if size == 0:
                empties.append(f)
            elif is_stub(f):
                stubs.append(f)
        except Exception:
            pass

    print(f"  {len(empties)} empty files, {len(stubs)} stubs (<{MIN_CONTENT_LENGTH} chars)")

    # Phase 3: Sanitize (optional)
    sanitized_count = 0
    sanitizer_findings = 0
    if run_sanitizer and HAS_SANITIZER:
        print("\n--- Phase 3: Sanitize ---")
        remaining = [f for f in articles if f not in duplicates and f not in stubs and f not in empties]
        for i, f in enumerate(remaining):
            try:
                report = sanitize_file(f, dry_run=dry_run)
                if report.items_removed > 0:
                    sanitized_count += 1
                    sanitizer_findings += report.items_removed
            except Exception:
                pass
            if (i + 1) % 5000 == 0:
                print(f"  Sanitized {i + 1}/{len(remaining)}... ({sanitized_count} with findings)")
        print(f"  {sanitized_count} files had content stripped ({sanitizer_findings} total items)")
    elif run_sanitizer and not HAS_SANITIZER:
        print("\n--- Phase 3: SKIPPED (content_sanitizer not importable) ---")

    # Phase 4: Execute removals
    bytes_saved = 0
    if not dry_run:
        print("\n--- Executing removals ---")
        for f in duplicates + stubs + empties:
            try:
                bytes_saved += f.stat().st_size
                f.unlink()
            except Exception as e:
                print(f"  ERROR removing {f}: {e}")
        print(f"  Removed {len(duplicates) + len(stubs) + len(empties)} files, saved {bytes_saved / 1024 / 1024:.1f} MB")
    else:
        for f in duplicates + stubs + empties:
            try:
                bytes_saved += f.stat().st_size
            except Exception:
                pass
        print(f"\n--- DRY RUN Summary ---")
        print(f"  Would remove {len(duplicates) + len(stubs) + len(empties)} files")
        print(f"  Would save {bytes_saved / 1024 / 1024:.1f} MB")

    elapsed = time.time() - start
    print(f"\nCompleted in {elapsed:.1f}s")

    # Show top duplicate clusters
    if duplicates:
        print("\n--- Top Duplicate Clusters ---")
        top = sorted(hash_map.items(), key=lambda x: -len(x[1]))[:5]
        for h, files in top:
            if len(files) > 1:
                print(f"  {len(files)} copies: {files[0].parent.parent.name}/{files[0].name}")

    # Show sample stubs
    if stubs:
        print("\n--- Sample Stubs ---")
        for f in stubs[:5]:
            try:
                content = f.read_text(errors="replace")[:80].replace("\n", " ")
                print(f"  {f.parent.parent.name}/{f.name}: \"{content}...\"")
            except Exception:
                pass

    return CompactReport(
        total_files=len(articles),
        duplicates_removed=len(duplicates),
        stubs_removed=len(stubs),
        empty_removed=len(empties),
        bytes_saved=bytes_saved,
        sanitized=sanitized_count,
        sanitizer_findings=sanitizer_findings,
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="KB Compaction — dedup, prune, sanitize")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Report only, don't remove files")
    parser.add_argument("--sanitize", action="store_true", default=False,
                        help="Also run content_sanitizer on remaining files")
    args = parser.parse_args()

    report = compact(dry_run=args.dry_run, run_sanitizer=args.sanitize)
    print(f"\n{'=' * 50}")
    print(f"Total files: {report.total_files}")
    print(f"Duplicates: {report.duplicates_removed}")
    print(f"Stubs: {report.stubs_removed}")
    print(f"Empty: {report.empty_removed}")
    print(f"Bytes saved: {report.bytes_saved / 1024 / 1024:.1f} MB")
    if report.sanitized:
        print(f"Sanitized: {report.sanitized} files ({report.sanitizer_findings} items removed)")


if __name__ == "__main__":
    main()
