#!/usr/bin/env python3
"""Dead Article Detector - Finds thin/empty articles across the KB.

Scans all KB article directories, identifies articles with fewer than
a configurable number of body words (excluding YAML frontmatter).
Outputs a report grouped by source directory.

Usage:
    python3 detect_dead_articles.py                    # Default: <50 words
    python3 detect_dead_articles.py --threshold 100    # Custom threshold
    python3 detect_dead_articles.py --quarantine       # Move thin articles to quarantine/
"""

import argparse
import re
import shutil
from collections import defaultdict
from pathlib import Path


# All KB source directories (from kb_loader.py ADVISORS mapping)
KB_ROOTS = [
    Path("~/Development/lennys-podcast-transcripts/episodes").expanduser(),
    Path("~/Development/don-norman/articles").expanduser(),
    Path("~/Development/nngroup/articles").expanduser(),
    Path("~/Development/ux-design").expanduser(),
    Path("~/Development/cherie-hu/articles").expanduser(),
    Path("~/Development/jesse-cannon/articles").expanduser(),
    Path("~/Development/music-marketing").expanduser(),
    Path("~/Development/chatprd-blog/articles").expanduser(),
    Path("~/Development/indie-hackers").expanduser(),
    Path("~/Development/plugin-devs").expanduser(),
    Path("~/Development/circuit-modeling").expanduser(),
    Path("~/Development/cto-leaders").expanduser(),
    Path("~/Development/security-leaders").expanduser(),
    Path("~/Development/art-direction").expanduser(),
    Path("~/Development/art-criticism").expanduser(),
    Path("~/Development/creative-interviews").expanduser(),
    Path("~/Development/fonts-in-use/articles").expanduser(),
    Path("~/Development/music-production").expanduser(),
    Path("~/Development/music-business").expanduser(),
    Path("~/Development/marketing-hacker").expanduser(),
    Path("~/Development/atrium").expanduser(),
    Path("~/Development/lenny").expanduser(),
    Path("~/Development/cto/cdm/articles").expanduser(),
    Path("~/Development/audio-production").expanduser(),
    Path("~/Development/art-director/virgil-abloh/articles").expanduser(),
    Path("~/Development/creative-boom/articles").expanduser(),
]


def extract_body_words(filepath: Path) -> int:
    """Count words in article body, excluding YAML/markdown frontmatter."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0

    lines = content.split("\n")
    body_start = 0

    # Skip YAML frontmatter (--- ... ---)
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                body_start = i + 1
                break
    # Skip markdown header block (# Title ... ---)
    elif lines and lines[0].strip().startswith("# "):
        for i, line in enumerate(lines):
            if line.strip() == "---" and i > 0:
                body_start = i + 1
                break
            if i > 15:
                body_start = 0
                break

    body = "\n".join(lines[body_start:])

    # Strip markdown formatting noise
    body = re.sub(r'!\[.*?\]\(.*?\)', '', body)  # images
    body = re.sub(r'\[([^\]]*)\]\([^\)]*\)', r'\1', body)  # links → text
    body = re.sub(r'[#*_`~>|]', '', body)  # formatting chars
    body = re.sub(r'\s+', ' ', body).strip()

    return len(body.split()) if body else 0


def scan_directory(root: Path, threshold: int) -> list[tuple[Path, int]]:
    """Find all .md files under root with fewer than threshold body words."""
    thin = []
    if not root.exists():
        return thin

    for md_file in root.rglob("*.md"):
        if md_file.name in ("README.md", "INDEX.md"):
            continue
        word_count = extract_body_words(md_file)
        if word_count < threshold:
            thin.append((md_file, word_count))

    return thin


def get_source_name(filepath: Path) -> str:
    """Extract a readable source name from the file path."""
    dev = Path("~/Development").expanduser()
    try:
        rel = filepath.relative_to(dev)
        # Use the first 1-2 directory components as the source name
        parts = rel.parts
        if len(parts) >= 3 and parts[1] == "articles":
            return parts[0]
        elif len(parts) >= 3:
            return f"{parts[0]}/{parts[1]}"
        else:
            return parts[0]
    except ValueError:
        return str(filepath.parent.name)


def main():
    parser = argparse.ArgumentParser(description="Detect thin/empty KB articles")
    parser.add_argument("--threshold", type=int, default=50,
                        help="Minimum body words (default: 50)")
    parser.add_argument("--delete", action="store_true",
                        help="Delete thin articles permanently")
    parser.add_argument("--quarantine", action="store_true",
                        help="Move thin articles to a quarantine directory")
    parser.add_argument("--verbose", action="store_true",
                        help="Show individual file paths")
    args = parser.parse_args()

    print(f"\nScanning KB for articles with < {args.threshold} body words...\n")

    all_thin: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    total_scanned = 0
    total_thin = 0

    for root in KB_ROOTS:
        thin = scan_directory(root, args.threshold)
        for filepath, wc in thin:
            source = get_source_name(filepath)
            all_thin[source].append((filepath, wc))

        # Count total .md files
        if root.exists():
            total_scanned += sum(1 for _ in root.rglob("*.md"))

    # Sort by count (worst offenders first)
    sorted_sources = sorted(all_thin.items(), key=lambda x: -len(x[1]))

    print(f"{'Source':<40} {'Thin':<8} {'Examples'}")
    print("-" * 80)

    for source, files in sorted_sources:
        total_thin += len(files)
        example = files[0][0].name if files else ""
        wc_example = files[0][1] if files else 0
        print(f"{source:<40} {len(files):<8} {example} ({wc_example} words)")

        if args.verbose:
            for fp, wc in files[:5]:
                print(f"  {wc:>4} words: {fp.name}")
            if len(files) > 5:
                print(f"  ... and {len(files) - 5} more")

    print("-" * 80)
    print(f"Total scanned: {total_scanned}")
    print(f"Total thin (<{args.threshold} words): {total_thin}")
    print(f"Percentage: {total_thin / total_scanned * 100:.1f}%" if total_scanned else "N/A")

    if args.delete and total_thin > 0:
        deleted = 0
        for source, files in sorted_sources:
            for filepath, wc in files:
                filepath.unlink()
                deleted += 1
        print(f"\nDeleted {deleted} thin articles permanently.")

    elif args.quarantine and total_thin > 0:
        quarantine_dir = Path("~/Development/kb-quarantine").expanduser()
        quarantine_dir.mkdir(exist_ok=True)
        moved = 0
        for source, files in sorted_sources:
            source_dir = quarantine_dir / source.replace("/", "--")
            source_dir.mkdir(exist_ok=True)
            for filepath, wc in files:
                dest = source_dir / filepath.name
                shutil.move(str(filepath), str(dest))
                moved += 1
        print(f"\nMoved {moved} thin articles to {quarantine_dir}")


if __name__ == "__main__":
    main()
