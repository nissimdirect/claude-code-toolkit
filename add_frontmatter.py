#!/usr/bin/env python3
"""
YAML Frontmatter Addition Tool
Converts markdown headers to YAML frontmatter using metadata.json
Skips files that already have frontmatter (e.g., Lenny transcripts)
Run after TF-IDF tagger to avoid header corruption

Code > Tokens: runs locally, zero API cost
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime


# Corpus directories and their advisor names
CORPORA = {
    '~/Development/jesse-cannon': 'jesse-cannon',
    '~/Development/cherie-hu': 'cherie-hu',
    '~/Development/chatprd-blog': 'chatprd',
    '~/Development/indie-hackers/pieter-levels': 'pieter-levels',
    '~/Development/indie-hackers/justin-welsh': 'justin-welsh',
    '~/Development/indie-hackers/daniel-vassallo': 'daniel-vassallo',
}

# Lenny already has frontmatter — skip
SKIP_DIRS = [
    '~/Development/lennys-podcast-transcripts',
]


def has_frontmatter(content):
    """Check if file already starts with YAML frontmatter (---)"""
    return content.strip().startswith('---')


def strip_wiki_links(text):
    """Remove [[wiki-links]] from text, keeping inner text"""
    return re.sub(r'\[\[(.*?)\]\]', r'\1', text)


def parse_markdown_header(content):
    """Extract header info from markdown format and return content after ---"""
    lines = content.split('\n')

    # Find the --- separator
    separator_idx = None
    for i, line in enumerate(lines):
        if line.strip() == '---' and i > 0:
            separator_idx = i
            break

    if separator_idx is None:
        # No separator found — return content as-is
        return None, content

    header_lines = lines[:separator_idx]
    body_lines = lines[separator_idx + 1:]

    # Parse header
    title = None
    author = None
    date = None
    url = None

    for line in header_lines:
        clean = strip_wiki_links(line).strip()

        if clean.startswith('# '):
            title = clean[2:].strip()
        elif clean.startswith('**Author:**'):
            author = clean.replace('**Author:**', '').strip()
        elif clean.startswith('**Date:**'):
            date = clean.replace('**Date:**', '').strip()
        elif clean.startswith('**URL:**'):
            url = clean.replace('**URL:**', '').strip()

    header_data = {
        'title': title,
        'author': author,
        'date': date,
        'url': url,
    }

    body = '\n'.join(body_lines)
    return header_data, body


def build_frontmatter(metadata, advisor_name):
    """Build YAML frontmatter string from metadata dict"""
    # Escape title for YAML (quotes if contains colons, quotes, etc.)
    title = metadata.get('title', 'Untitled')
    if title and any(c in title for c in ':\'\"#[]{}|>&*!%@'):
        title = f'"{title}"'

    lines = ['---']
    lines.append(f'title: {title}')

    if metadata.get('date'):
        lines.append(f'date: {metadata["date"]}')

    if metadata.get('author'):
        lines.append(f'author: {metadata["author"]}')

    lines.append(f'source: {advisor_name}')

    if metadata.get('url'):
        lines.append(f'url: {metadata["url"]}')

    if metadata.get('word_count'):
        lines.append(f'word_count: {metadata["word_count"]}')

    lines.append('---')
    return '\n'.join(lines)


def process_corpus(corpus_dir, advisor_name, dry_run=False):
    """Add YAML frontmatter to all articles in a corpus directory"""
    corpus_path = Path(os.path.expanduser(corpus_dir))

    if not corpus_path.exists():
        print(f"   ⚠️  Directory not found: {corpus_path}")
        return 0, 0

    # Load metadata.json if available
    metadata_file = corpus_path / 'metadata' / 'metadata.json'
    metadata_lookup = {}

    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
            for article in meta.get('articles', []):
                filename = article.get('file', '')
                if filename:
                    # metadata.json uses relative paths like "articles/001-foo.md"
                    metadata_lookup[filename] = article
        print(f"   Loaded {len(metadata_lookup)} metadata entries")

    # Find all article files
    article_files = []

    # Pattern 1: articles/*.md
    articles_dir = corpus_path / 'articles'
    if articles_dir.exists():
        article_files.extend(articles_dir.glob('*.md'))

    # Pattern 2: how-i-ai/*.md (ChatPRD)
    howiai_dir = corpus_path / 'how-i-ai'
    if howiai_dir.exists():
        article_files.extend(howiai_dir.glob('*.md'))

    # Pattern 3: guides/*.md (ChatPRD)
    guides_dir = corpus_path / 'guides'
    if guides_dir.exists():
        article_files.extend(guides_dir.glob('*.md'))

    # Pattern 4: product-updates/*.md (ChatPRD)
    updates_dir = corpus_path / 'product-updates'
    if updates_dir.exists():
        article_files.extend(updates_dir.glob('*.md'))

    converted = 0
    skipped = 0

    for filepath in sorted(article_files):
        content = filepath.read_text(encoding='utf-8')

        # Skip files that already have frontmatter
        if has_frontmatter(content):
            skipped += 1
            continue

        # Try to get metadata from metadata.json first (clean data)
        rel_path = str(filepath.relative_to(corpus_path))
        meta_entry = metadata_lookup.get(rel_path, {})

        if meta_entry:
            # Use metadata.json (clean, no wiki-links)
            metadata = {
                'title': meta_entry.get('title', 'Untitled'),
                'date': meta_entry.get('date', ''),
                'author': meta_entry.get('author', ''),
                'url': meta_entry.get('url', ''),
                'word_count': meta_entry.get('word_count', 0),
            }
        else:
            # Fall back to parsing markdown header
            header_data, _ = parse_markdown_header(content)
            if header_data is None:
                skipped += 1
                continue
            metadata = header_data
            # Estimate word count
            metadata['word_count'] = len(content.split())

        # Parse body (everything after the --- separator)
        _, body = parse_markdown_header(content)

        # Build new file content
        frontmatter = build_frontmatter(metadata, advisor_name)
        new_content = frontmatter + '\n' + body

        if not dry_run:
            filepath.write_text(new_content, encoding='utf-8')

        converted += 1

    return converted, skipped


def main():
    dry_run = '--dry-run' in sys.argv
    verbose = '--verbose' in sys.argv

    print(f"📄 YAML Frontmatter Tool {'(DRY RUN)' if dry_run else ''}")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    total_converted = 0
    total_skipped = 0

    for corpus_dir, advisor_name in CORPORA.items():
        print(f"📂 {advisor_name}:")
        converted, skipped = process_corpus(corpus_dir, advisor_name, dry_run)
        total_converted += converted
        total_skipped += skipped
        print(f"   ✅ Converted: {converted}, Skipped: {skipped}")

    print(f"\n📊 Summary:")
    print(f"   Total converted: {total_converted}")
    print(f"   Total skipped (already had frontmatter): {total_skipped}")

    if dry_run:
        print(f"\n   Run without --dry-run to apply changes")
    else:
        print(f"\n✅ Complete!")


if __name__ == '__main__':
    main()
