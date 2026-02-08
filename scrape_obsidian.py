#!/usr/bin/env python3
"""Obsidian documentation scraper - fetches raw markdown from Obsidian Publish

Obsidian Help is served via Obsidian Publish (JavaScript SPA).
Raw markdown is available directly, which is much cleaner than HTML scraping.
"""

import time
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
import yaml

# Rate limiting
DELAY = 5  # seconds between requests
USER_AGENT = "PopChaosLabs/1.0 (Educational Research; nissim.direct@gmail.com)"

# Obsidian Publish configuration
OBSIDIAN_BASE = "https://help.obsidian.md"
OBSIDIAN_PUBLISH_BASE = "https://publish-01.obsidian.md/access/f786db9fac45774fa4f0d8112e232d67"
OUTPUT_DIR = Path("~/Development/obsidian-docs").expanduser()


def fetch_sitemap() -> List[str]:
    """Fetch all URLs from Obsidian sitemap"""
    sitemap_url = f"{OBSIDIAN_BASE}/sitemap.xml"

    print(f"Fetching sitemap: {sitemap_url}")
    response = requests.get(sitemap_url, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'xml')
    urls = [loc.text for loc in soup.find_all('loc')]

    print(f"Found {len(urls)} pages")
    return urls


def url_to_markdown_path(web_url: str) -> str:
    """Convert web URL to markdown file path

    Example:
        https://help.obsidian.md/Home
        -> https://publish-01.obsidian.md/access/.../Home.md
    """
    path = web_url.replace(OBSIDIAN_BASE + "/", "")

    # Handle special characters in URLs
    if not path:
        path = "Home"

    # Add .md extension
    if not path.endswith('.md'):
        path = f"{path}.md"

    return f"{OBSIDIAN_PUBLISH_BASE}/{path}"


def fetch_markdown(web_url: str) -> Dict:
    """Fetch raw markdown content from Obsidian Publish"""
    md_url = url_to_markdown_path(web_url)

    print(f"  Fetching: {md_url}")

    try:
        response = requests.get(md_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()

        content = response.text

        # Extract title from content (first # heading or from frontmatter)
        title = None

        # Check for existing frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                existing_fm = yaml.safe_load(parts[1])
                # Keep existing content as-is, including frontmatter
                # We'll add our metadata separately
                content = parts[2].strip()

        # Extract title from first heading
        for line in content.split('\n'):
            if line.startswith('# '):
                title = line[2:].strip()
                break

        if not title:
            # Fallback to URL path
            title = urlparse(web_url).path.split('/')[-1].replace('-', ' ').title()
            if not title:
                title = "Home"

        return {
            "title": title,
            "content": content,
            "url": web_url
        }

    except requests.RequestException as e:
        print(f"    ERROR: {e}")
        return None


def generate_metadata(extracted: Dict) -> Dict:
    """Generate YAML frontmatter metadata"""
    today = datetime.now().strftime("%Y-%m-%d")

    metadata = {
        "title": extracted["title"],
        "author": "Obsidian Team",
        "source": "obsidian",
        "source_url": extracted["url"],
        "date_published": today,  # Obsidian doesn't publish dates
        "date_scraped": today,
        "type": "documentation",
        "skill": "cto",
        "tags": [],  # Will be filled by LLM analysis
        "product": "Obsidian",
        "category": "documentation"
    }

    return metadata


def save_article(metadata: Dict, content: str, output_dir: Path) -> Path:
    """Save article with YAML frontmatter"""
    # Generate filename from URL
    url_hash = hashlib.md5(metadata["source_url"].encode()).hexdigest()[:8]
    safe_title = "".join(c for c in metadata["title"] if c.isalnum() or c in (' ', '-', '_'))[:50]
    filename = f"{safe_title.replace(' ', '-').lower()}-{url_hash}.md"

    filepath = output_dir / "raw" / filename

    # Build markdown with frontmatter
    frontmatter = yaml.dump(metadata, default_flow_style=False, allow_unicode=True)
    full_content = f"---\n{frontmatter}---\n\n{content}"

    filepath.write_text(full_content, encoding='utf-8')

    return filepath


def main():
    """Scrape all Obsidian documentation"""
    print("🔹 Obsidian Documentation Scraper")
    print(f"   Output: {OUTPUT_DIR}\n")

    # Create output directories
    raw_dir = OUTPUT_DIR / "raw"
    analyzed_dir = OUTPUT_DIR / "analyzed"
    index_dir = OUTPUT_DIR / "index"

    for dir_path in [raw_dir, analyzed_dir, index_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Fetch sitemap
    urls = fetch_sitemap()

    # Scrape each page
    scraped = 0
    errors = 0

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")

        # Fetch markdown
        extracted = fetch_markdown(url)

        if not extracted:
            errors += 1
            continue

        # Generate metadata
        metadata = generate_metadata(extracted)

        # Save article
        filepath = save_article(metadata, extracted["content"], OUTPUT_DIR)
        print(f"  ✅ Saved: {filepath.name}")

        scraped += 1

        # Rate limiting
        if i < len(urls):  # Don't wait after last one
            time.sleep(DELAY)

    print(f"\n🎉 Complete!")
    print(f"   Scraped: {scraped} articles")
    print(f"   Errors: {errors}")
    print(f"   Location: {OUTPUT_DIR}/raw/")
    print(f"\n   Next steps:")
    print(f"   1. Run knowledge_analyzer.py for LLM enrichment")
    print(f"   2. Run knowledge_sync.py to index in database")


if __name__ == "__main__":
    main()
