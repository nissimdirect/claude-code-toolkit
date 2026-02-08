#!/usr/bin/env python3
"""
Strip all [[wiki-links]] from corpus articles.
Restores articles to clean text by removing [[ and ]] brackets.
Used to undo bad tagger runs.
"""

import os
import re
import sys
from pathlib import Path


CORPORA = [
    '~/Development/jesse-cannon',
    '~/Development/cherie-hu',
    '~/Development/chatprd-blog',
    '~/Development/lennys-podcast-transcripts',
    '~/Development/indie-hackers/pieter-levels',
    '~/Development/indie-hackers/justin-welsh',
    '~/Development/indie-hackers/daniel-vassallo',
]


def strip_wikilinks(content):
    """Remove [[...]] brackets, keeping inner text"""
    return re.sub(r'\[\[(.*?)\]\]', r'\1', content)


def process_directory(corpus_dir, dry_run=False):
    """Strip wiki-links from all markdown files in corpus"""
    corpus_path = Path(os.path.expanduser(corpus_dir))
    if not corpus_path.exists():
        return 0, 0

    modified = 0
    unchanged = 0

    # Find all .md files recursively
    for md_file in corpus_path.rglob('*.md'):
        # Skip INDEX.md and other non-article files
        if md_file.name in ('INDEX.md', 'README.md'):
            continue

        content = md_file.read_text(encoding='utf-8')
        cleaned = strip_wikilinks(content)

        if cleaned != content:
            if not dry_run:
                md_file.write_text(cleaned, encoding='utf-8')
            modified += 1
        else:
            unchanged += 1

    return modified, unchanged


def main():
    dry_run = '--dry-run' in sys.argv

    print(f"🧹 Strip Wiki-Links {'(DRY RUN)' if dry_run else ''}\n")

    total_modified = 0
    total_unchanged = 0

    for corpus_dir in CORPORA:
        name = Path(os.path.expanduser(corpus_dir)).name
        modified, unchanged = process_directory(corpus_dir, dry_run)
        total_modified += modified
        total_unchanged += unchanged
        print(f"   {name}: {modified} cleaned, {unchanged} unchanged")

    print(f"\n   Total: {total_modified} files cleaned, {total_unchanged} unchanged")
    if dry_run:
        print("   Run without --dry-run to apply")
    else:
        print("✅ Done!")


if __name__ == '__main__':
    main()
