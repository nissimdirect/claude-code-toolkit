#!/usr/bin/env python3
"""Convert cleaned VTT transcript .txt files into markdown articles with YAML frontmatter.

Handles three categories of CC YouTube content:
1. Retreat presentations (artist talks at CC retreats)
2. Carnival/event compilations (multi-artist showcases)
3. Project documentation (short awardee project videos)
"""

import re
import sys
from pathlib import Path
from datetime import datetime

MIN_WORDS = 100  # Skip transcripts under this threshold


def classify_transcript(title: str) -> dict:
    """Classify a transcript by title and extract metadata."""
    lower = title.lower()

    # Retreat presentations
    retreat_match = re.search(r'(\d{4}) creative capital (?:artist )?retreat', lower)
    if retreat_match or 'presents at the' in lower or 'retreat' in lower:
        year = retreat_match.group(1) if retreat_match else "unknown"
        if year == "unknown":
            year_match = re.search(r'(\d{4})', title)
            year = year_match.group(1) if year_match else "unknown"

        # Extract artist name from "X Presents at the YYYY..."
        artist = title.split(' Presents')[0].split(' presents')[0].split(' Opens')[0].split("'s Opening")[0]
        artist = re.sub(r'[^\w\s,&.\'-]', '', artist).strip()

        return {
            "type": "retreat",
            "artist": artist,
            "year": year,
            "tags": ["creative-capital", "awardee-presentation", f"retreat-{year}", "grant-winner", "artist-talk", "transcript"],
        }

    # Carnival/event compilations
    if 'carnival' in lower:
        year_match = re.search(r'(\d{4})', title)
        year = year_match.group(1) if year_match else "unknown"
        return {
            "type": "carnival",
            "artist": "Creative Capital",
            "year": year,
            "tags": ["creative-capital", "carnival", f"carnival-{year}", "multi-artist", "project-videos", "transcript"],
        }

    # Full presentations (e.g., "Full 2012 Presentation")
    if 'full' in lower and 'presentation' in lower:
        year_match = re.search(r'(\d{4})', title)
        year = year_match.group(1) if year_match else "unknown"
        return {
            "type": "event",
            "artist": "Creative Capital",
            "year": year,
            "tags": ["creative-capital", "full-presentation", f"event-{year}", "multi-artist", "transcript"],
        }

    # Project documentation ("Artist: Project Title | Creative Capital Project")
    if 'creative capital project' in lower:
        artist = title.split(':')[0].split('：')[0].strip() if (':' in title or '：' in title) else title.split('|')[0].split('｜')[0].strip()
        artist = re.sub(r'[^\w\s,&.\'-]', '', artist).strip()
        return {
            "type": "project",
            "artist": artist,
            "year": "unknown",
            "tags": ["creative-capital", "project-documentation", "awardee-project", "grant-winner", "transcript"],
        }

    # CC Exchange, info
    if 'exchange' in lower or 'art of justice' in lower or 'showing your work' in lower:
        artist = title.split(':')[0].split('：')[0].strip() if (':' in title or '：' in title) else "Creative Capital"
        artist = re.sub(r'[^\w\s,&.\'-]', '', artist).strip()
        return {
            "type": "info",
            "artist": artist,
            "year": "unknown",
            "tags": ["creative-capital", "information", "artist-advice", "transcript"],
        }

    # Fallback
    artist = title.split(':')[0].split('：')[0].split('|')[0].split('｜')[0].strip()
    artist = re.sub(r'[^\w\s,&.\'-]', '', artist).strip()
    return {
        "type": "other",
        "artist": artist,
        "year": "unknown",
        "tags": ["creative-capital", "transcript"],
    }


def make_safe_filename(meta: dict, title: str) -> str:
    """Generate a safe, descriptive filename."""
    t = meta["type"]
    artist = meta["artist"]
    year = meta["year"]

    safe_artist = re.sub(r'[^\w\s-]', '', artist.lower())
    safe_artist = re.sub(r'\s+', '-', safe_artist.strip())[:60]

    if t == "retreat":
        return f"cc-retreat-{year}-{safe_artist}.md"
    elif t == "carnival":
        return f"cc-carnival-{year}.md"
    elif t == "event":
        return f"cc-event-{year}-full-presentation.md"
    elif t == "project":
        return f"cc-project-{safe_artist}.md"
    elif t == "info":
        safe_title = re.sub(r'[^\w\s-]', '', title.lower())
        safe_title = re.sub(r'\s+', '-', safe_title.strip())[:60]
        return f"cc-info-{safe_title}.md"
    else:
        safe_title = re.sub(r'[^\w\s-]', '', title.lower())
        safe_title = re.sub(r'\s+', '-', safe_title.strip())[:60]
        return f"cc-{safe_title}.md"


def make_title(meta: dict) -> str:
    """Generate article title."""
    t = meta["type"]
    artist = meta["artist"]
    year = meta["year"]

    if t == "retreat":
        return f"{artist} — Creative Capital {year} Retreat Presentation"
    elif t == "carnival":
        return f"Creative Capital Carnival {year} — Artist Project Videos"
    elif t == "event":
        return f"Creative Capital {year} Full Presentation"
    elif t == "project":
        return f"{artist} — Creative Capital Awardee Project"
    else:
        return f"{artist} — Creative Capital"


def txt_to_article(txt_path: Path, output_dir: Path) -> Path:
    """Convert a cleaned transcript .txt to a markdown article."""
    text = txt_path.read_text(encoding="utf-8").strip()
    if not text:
        return None

    words = len(text.split())
    if words < MIN_WORDS:
        return None

    # Extract title from filename (remove .en suffix)
    raw_title = txt_path.stem
    if raw_title.endswith('.en'):
        raw_title = raw_title[:-3]

    meta = classify_transcript(raw_title)
    title = make_title(meta)
    filename = make_safe_filename(meta, raw_title)
    tags_str = ', '.join(f'"{t}"' for t in meta["tags"])

    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    event_type = meta["type"].replace("_", " ").title()

    article = f"""---
title: "{title}"
author: "{meta['artist']}"
source: "Creative Capital YouTube"
scraped: "{now}"
tags: [{tags_str}]
---

# {title}

**Artist:** {meta['artist']}
**Type:** {event_type}
**Words:** {words}
**Source:** YouTube auto-generated transcript

---

## Transcript

{text}
"""

    out_path = output_dir / filename
    out_path.write_text(article, encoding="utf-8")
    return out_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 vtt_to_articles.py <txt_directory> [output_directory]")
        sys.exit(1)

    txt_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else txt_dir.parent / "articles"
    out_dir.mkdir(parents=True, exist_ok=True)

    converted = 0
    skipped = 0
    for txt_file in sorted(txt_dir.glob("*.txt")):
        result = txt_to_article(txt_file, out_dir)
        if result:
            words = len(txt_file.read_text(encoding="utf-8").split())
            print(f"  {result.name} ({words} words)")
            converted += 1
        else:
            words = len(txt_file.read_text(encoding="utf-8").split()) if txt_file.exists() else 0
            if words < MIN_WORDS:
                print(f"  SKIP (< {MIN_WORDS} words): {txt_file.name} ({words} words)")
            skipped += 1

    print(f"\nConverted {converted} transcripts, skipped {skipped}")


if __name__ == "__main__":
    main()
