#!/usr/bin/env python3
"""Article Trimmer - Strips boilerplate from KB articles.

Removes common web scraping artifacts: navigation bars, related articles,
cookie notices, share buttons, repeated author bios, image markdown,
excessive whitespace. Makes articles leaner for search and prompt injection.

Usage:
    python3 trim_articles.py                     # Dry run (report only)
    python3 trim_articles.py --apply             # Trim all articles in-place
    python3 trim_articles.py --apply --verbose   # Trim with per-file details
    python3 trim_articles.py --sample 5          # Show before/after for 5 random articles
"""

import argparse
import re
from pathlib import Path


# All KB source directories
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

# ── Boilerplate Patterns ──────────────────────────────────────────

# Lines that are pure navigation/UI artifacts
NAV_PATTERNS = [
    re.compile(r'^\s*\[?(Home|About|Contact|Menu|Navigation|Search|Subscribe|Login|Sign [Uu]p|Register)\]?\s*$', re.IGNORECASE),
    re.compile(r'^\s*\[?(Previous|Next|Prev|Back|Forward|Read [Mm]ore|Continue [Rr]eading|Show [Mm]ore)\]?\s*$', re.IGNORECASE),
    re.compile(r'^\s*\[?(Skip to .*|Jump to .*|Go to .*)\]?\s*$', re.IGNORECASE),
    re.compile(r'^\s*(Share|Tweet|Pin|Email|Print|Copy [Ll]ink|SHARE:?)\s*$', re.IGNORECASE),
    re.compile(r'^\s*\[?(Facebook|Twitter|LinkedIn|Instagram|YouTube|TikTok|Pinterest|Reddit|WhatsApp)\]?\s*$', re.IGNORECASE),
]

# Block patterns - if a line matches, remove it AND subsequent lines until a blank line
BLOCK_START_PATTERNS = [
    re.compile(r'^\s*#{1,3}\s*(Related (?:Articles?|Posts?|Stories?|Content)|You (?:May|Might) Also (?:Like|Enjoy)|More (?:From|Like This|Stories)|Recommended|Popular (?:Posts?|Articles?)|Trending|Also (?:Read|See)|Further Reading)', re.IGNORECASE),
    re.compile(r'^\s*\*{0,2}(Related (?:Articles?|Posts?)|You (?:May|Might) Also)', re.IGNORECASE),
    re.compile(r'^\s*#{1,3}\s*(Comments?|Leave a (?:Reply|Comment)|Discussion|Responses?)\s*$', re.IGNORECASE),
    re.compile(r'^\s*#{1,3}\s*(Newsletter|Subscribe|Get (?:Our|The) Newsletter|Sign [Uu]p|Join (?:Our|The))\s*$', re.IGNORECASE),
    re.compile(r'^\s*#{1,3}\s*(About [Tt]he [Aa]uthor|Author [Bb]io|Written [Bb]y)\s*$', re.IGNORECASE),
    re.compile(r'^\s*#{1,3}\s*(Tags?|Categories?|Topics?|Filed [Uu]nder)\s*$', re.IGNORECASE),
    re.compile(r'^\s*#{1,3}\s*(Footer|Copyright|All [Rr]ights [Rr]eserved)\s*$', re.IGNORECASE),
]

# Single-line removal patterns
REMOVE_LINE_PATTERNS = [
    re.compile(r'^\s*!\[.*?\]\(.*?\)\s*$'),  # Standalone image markdown
    re.compile(r'^\s*\[!\[.*?\]\(.*?\)\]\(.*?\)\s*$'),  # Linked images
    re.compile(r'^\s*<img\b[^>]*/?>\s*$', re.IGNORECASE),  # HTML images
    re.compile(r'^\s*<iframe\b[^>]*>.*?</iframe>\s*$', re.IGNORECASE),  # Iframes
    re.compile(r'^\s*Cookie', re.IGNORECASE),  # Cookie notices
    re.compile(r'^\s*We use cookies', re.IGNORECASE),
    re.compile(r'^\s*This (?:website|site) uses cookies', re.IGNORECASE),
    re.compile(r'^\s*Accept (?:All )?Cookies?\s*$', re.IGNORECASE),
    re.compile(r'^\s*\d+ comments?\s*$', re.IGNORECASE),  # Comment counts
    re.compile(r'^\s*Loading\.{0,3}\s*$', re.IGNORECASE),  # Loading indicators
    re.compile(r'^\s*Advertisement\s*$', re.IGNORECASE),  # Ad markers
    re.compile(r'^\s*Sponsored\s*$', re.IGNORECASE),
    re.compile(r'^\s*Photo:?\s*$', re.IGNORECASE),  # Orphaned photo captions
    re.compile(r'^\s*Image:?\s*$', re.IGNORECASE),
    re.compile(r'^\s*Credit:?\s*$', re.IGNORECASE),
    re.compile(r'^\s*\| \|', re.IGNORECASE),  # Empty table cells
    re.compile(r'^\s*\[\s*\]\s*$'),  # Empty links
    re.compile(r'^\s*\*\s*\*\s*\*\s*$'),  # Decorative separators (*** alone)
    re.compile(r'^\s*---+\s*$'),  # Horizontal rules (except frontmatter)
    re.compile(r'^\s*\u200c+\s*$'),  # Zero-width non-joiner chars (e-flux artifact)
]


def trim_article(content: str) -> str:
    """Trim boilerplate from a single article's content."""
    lines = content.split("\n")
    result = []
    in_frontmatter = False
    frontmatter_done = False
    skip_block = False
    consecutive_blank = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Preserve YAML frontmatter (--- ... ---)
        if i == 0 and stripped == "---":
            in_frontmatter = True
            result.append(line)
            continue
        if in_frontmatter:
            result.append(line)
            if stripped == "---":
                in_frontmatter = False
                frontmatter_done = True
            continue

        # Preserve markdown header block (# Title ... first ---)
        if i == 0 and stripped.startswith("# "):
            result.append(line)
            continue
        if not frontmatter_done and i <= 15:
            if stripped == "---":
                frontmatter_done = True
                result.append(line)
                continue
            if stripped.startswith("**") and ":**" in stripped:
                result.append(line)
                continue
            if stripped.startswith("# "):
                result.append(line)
                continue

        # Check for block-level boilerplate (remove until blank line)
        if any(p.match(stripped) for p in BLOCK_START_PATTERNS):
            skip_block = True
            continue

        if skip_block:
            if not stripped:
                skip_block = False
                # Don't add the blank line after a removed block
            continue

        # Check for nav/UI line patterns
        if any(p.match(stripped) for p in NAV_PATTERNS):
            continue

        # Check for single-line removal patterns
        if any(p.match(line) for p in REMOVE_LINE_PATTERNS):
            continue

        # Collapse excessive blank lines (max 2 consecutive)
        if not stripped:
            consecutive_blank += 1
            if consecutive_blank > 2:
                continue
        else:
            consecutive_blank = 0

        result.append(line)

    # Strip trailing blank lines
    while result and not result[-1].strip():
        result.pop()

    return "\n".join(result) + "\n" if result else ""


def process_file(filepath: Path, apply: bool = False) -> dict:
    """Process a single file. Returns stats dict."""
    try:
        original = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"path": str(filepath), "error": True}

    trimmed = trim_article(original)
    original_size = len(original)
    trimmed_size = len(trimmed)
    saved = original_size - trimmed_size
    pct = (saved / original_size * 100) if original_size > 0 else 0

    if apply and saved > 0:
        filepath.write_text(trimmed, encoding="utf-8")

    return {
        "path": str(filepath),
        "original_size": original_size,
        "trimmed_size": trimmed_size,
        "saved": saved,
        "pct": pct,
        "error": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Trim boilerplate from KB articles")
    parser.add_argument("--apply", action="store_true",
                        help="Apply trimming in-place (default: dry run)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show per-file trimming details")
    parser.add_argument("--sample", type=int, default=0,
                        help="Show before/after for N random articles")
    args = parser.parse_args()

    mode = "APPLYING" if args.apply else "DRY RUN"
    print(f"\n[{mode}] Trimming boilerplate from KB articles...\n")

    from collections import defaultdict
    stats_by_source: dict[str, dict] = defaultdict(lambda: {
        "files": 0, "original_bytes": 0, "trimmed_bytes": 0, "errors": 0
    })
    total_files = 0
    total_saved = 0

    sample_files = []

    for root in KB_ROOTS:
        if not root.exists():
            continue
        for md_file in root.rglob("*.md"):
            if md_file.name in ("README.md", "INDEX.md", "metadata.json"):
                continue

            stat = process_file(md_file, apply=args.apply)
            total_files += 1

            # Source name from path
            dev = Path("~/Development").expanduser()
            try:
                rel = md_file.relative_to(dev)
                source = rel.parts[0]
            except ValueError:
                source = "other"

            s = stats_by_source[source]
            s["files"] += 1
            if stat["error"]:
                s["errors"] += 1
            else:
                s["original_bytes"] += stat["original_size"]
                s["trimmed_bytes"] += stat["trimmed_size"]
                total_saved += stat["saved"]

            if args.verbose and stat.get("pct", 0) > 5:
                print(f"  {stat['pct']:5.1f}% saved: {md_file.name}")

            if args.sample > 0 and stat.get("pct", 0) > 10:
                sample_files.append(md_file)

    # Report
    print(f"\n{'Source':<35} {'Files':<8} {'Original':<12} {'Trimmed':<12} {'Saved':<10} {'%'}")
    print("-" * 85)

    sorted_sources = sorted(stats_by_source.items(),
                            key=lambda x: x[1]["original_bytes"] - x[1]["trimmed_bytes"],
                            reverse=True)

    for source, s in sorted_sources:
        saved = s["original_bytes"] - s["trimmed_bytes"]
        pct = (saved / s["original_bytes"] * 100) if s["original_bytes"] > 0 else 0
        if saved > 0 or args.verbose:
            print(f"{source:<35} {s['files']:<8} {s['original_bytes']:>10,}  {s['trimmed_bytes']:>10,}  {saved:>8,}  {pct:5.1f}%")

    total_original = sum(s["original_bytes"] for s in stats_by_source.values())
    total_trimmed = sum(s["trimmed_bytes"] for s in stats_by_source.values())
    total_pct = (total_saved / total_original * 100) if total_original > 0 else 0

    print("-" * 85)
    print(f"{'TOTAL':<35} {total_files:<8} {total_original:>10,}  {total_trimmed:>10,}  {total_saved:>8,}  {total_pct:5.1f}%")
    print(f"\nTotal saved: {total_saved:,} bytes ({total_saved / 1024 / 1024:.1f} MB)")

    if args.sample > 0 and sample_files:
        import random
        samples = random.sample(sample_files, min(args.sample, len(sample_files)))
        for fp in samples:
            original = fp.read_text(encoding="utf-8", errors="replace")
            trimmed = trim_article(original)
            print(f"\n{'='*60}")
            print(f"FILE: {fp.name}")
            print(f"BEFORE: {len(original)} bytes | AFTER: {len(trimmed)} bytes")
            print(f"{'='*60}")
            print("FIRST 20 LINES (TRIMMED):")
            for line in trimmed.split("\n")[:20]:
                print(f"  {line}")


if __name__ == "__main__":
    main()
