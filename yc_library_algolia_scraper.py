#!/usr/bin/env python3
"""YC Library Scraper via Algolia API.

YC Library is a React SPA — HTML pages have no content.
This scraper queries the Algolia search API directly to get all articles.

Usage:
    python3 yc_library_algolia_scraper.py
"""

import base64
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Configuration ──────────────────────────────────────────────────────────

KB_DIR = Path.home() / "Development" / "knowledge-bases" / "first-1000" / "yc-library"

ALGOLIA_APP_ID = "45BWZJ1SGC"
ALGOLIA_KEY_RAW = (
    "eee01aa8e22ce361825f51914404ed398645258b826ea00e837bc41caccded37"
    "restrictIndices=Article_production"
    "&tagFilters=%5B%22ycdc_public%22%2C%5B%22kb_root_176%22%5D%5D"
    "&analyticsTags=%5B%22ycdc%22%5D"
)
ALGOLIA_KEY = base64.b64encode(ALGOLIA_KEY_RAW.encode()).decode()

ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/Article_production/query"
HEADERS = {
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_KEY,
    "Content-Type": "application/json",
}

MIN_WORDS = 30  # Skip very short entries


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:120]


def main():
    KB_DIR.mkdir(parents=True, exist_ok=True)

    # Remove old failed scrape files
    for f in KB_DIR.glob("*.md"):
        f.unlink()

    # Get total count
    resp = requests.post(ALGOLIA_URL, headers=HEADERS, json={
        "params": "query=&hitsPerPage=0"
    }, timeout=30)
    data = resp.json()
    total = data["nbHits"]
    print(f"Total YC Library articles: {total}")

    # Fetch all pages
    hits_per_page = 50
    all_hits = []
    page = 0
    total_pages = (total + hits_per_page - 1) // hits_per_page

    while page < total_pages:
        print(f"  Fetching page {page + 1}/{total_pages}...")
        resp = requests.post(ALGOLIA_URL, headers=HEADERS, json={
            "params": f"query=&hitsPerPage={hits_per_page}&page={page}"
        }, timeout=30)
        data = resp.json()
        hits = data.get("hits", [])
        if not hits:
            break
        all_hits.extend(hits)
        page += 1
        time.sleep(0.5)  # Be respectful

    print(f"  Fetched {len(all_hits)} articles total")

    # Save articles
    stats = {"saved": 0, "skipped": 0}
    for i, hit in enumerate(all_hits, 1):
        title = hit.get("title", f"Article {i}")
        body = hit.get("body", "")
        words = len(body.split())

        if words < MIN_WORDS:
            stats["skipped"] += 1
            continue

        # Get metadata
        parents = hit.get("parents", [])
        slug = parents[0].get("slug", "") if parents else ""
        url = f"https://www.ycombinator.com/library/{slug}" if slug else ""
        date = hit.get("created_at", "")

        # Build markdown
        file_slug = slugify(title)
        filename = f"{i:04d}-{file_slug}.md"
        filepath = KB_DIR / filename

        frontmatter = f"""---
title: "{title.replace('"', "'")}"
url: "{url}"
date: "{date}"
author: "Y Combinator"
source: "wave-9-first-1000"
scraped: "{datetime.now().isoformat()}"
word_count: {words}
---

# {title}

"""
        filepath.write_text(frontmatter + body, encoding="utf-8")
        stats["saved"] += 1

    print(f"\nDone!")
    print(f"  Saved: {stats['saved']} articles")
    print(f"  Skipped: {stats['skipped']} (< {MIN_WORDS} words)")
    print(f"  Output: {KB_DIR}")


if __name__ == "__main__":
    main()
