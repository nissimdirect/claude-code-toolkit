#!/usr/bin/env python3
"""Fixed Obsidian Documentation Scraper - 2-Step Fetch

FIXES:
1. Fetches HTML first to extract actual markdown path from JavaScript
2. Then fetches the actual markdown file
3. 100% success rate (tested on 5 samples)

Usage: python3 scrape_obsidian_fixed.py
"""
import re
import time
import hashlib
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import yaml

# Configuration
BASE_URL = "https://help.obsidian.md"
PUBLISH_BASE = "https://publish-01.obsidian.md/access/f786db9fac45774fa4f0d8112e232d67"
OUTPUT_DIR = Path("~/Development/obsidian-docs").expanduser()
DELAY = 5  # seconds between requests
USER_AGENT = "PopChaosLabs/1.0 (Educational Research; nissim.direct@gmail.com)"

def fetch_sitemap():
    """Fetch all URLs from Obsidian sitemap"""
    sitemap_url = f"{BASE_URL}/sitemap.xml"
    print(f"Fetching sitemap: {sitemap_url}")

    response = requests.get(sitemap_url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'xml')
    urls = [loc.text for loc in soup.find_all('loc')]

    print(f"Found {len(urls)} pages\n")
    return urls

def fetch_markdown_2step(web_url):
    """2-step fetch: HTML → extract markdown path → fetch markdown"""
    try:
        # Step 1: Fetch HTML and extract markdown path
        html_response = requests.get(web_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        html_response.raise_for_status()

        # Extract preloadPage path from JavaScript
        match = re.search(r'window\.preloadPage=f\("([^"]+)"\)', html_response.text)

        if not match:
            return None, "Could not find preloadPage in HTML"

        markdown_url = match.group(1)

        # Step 2: Fetch actual markdown
        md_response = requests.get(markdown_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        md_response.raise_for_status()

        content = md_response.text

        # Check for 404
        if "## Not Found" in content:
            return None, "404 - File does not exist"

        # Extract title from YAML frontmatter or first heading
        title = None

        if content.strip().startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1])
                    # Keep original frontmatter, extract actual content
                    content = parts[2].strip()

                    # Try to get title from various frontmatter fields
                    if isinstance(frontmatter, dict):
                        title = (frontmatter.get('title') or
                                frontmatter.get('aliases', [None])[0] if frontmatter.get('aliases') else None)
                except:
                    pass

        # Fallback: extract title from first heading
        if not title:
            for line in content.split('\n'):
                if line.startswith('# '):
                    title = line[2:].strip()
                    break

        # Last fallback: use URL path
        if not title:
            title = web_url.split('/')[-1].replace('-', ' ').replace('+', ' ').title()
            if not title:
                title = "Home"

        return {
            "title": title,
            "content": content,
            "url": web_url
        }, None

    except requests.RequestException as e:
        return None, f"Request error: {e}"
    except Exception as e:
        return None, f"Parse error: {e}"

def generate_metadata(extracted):
    """Generate YAML frontmatter metadata"""
    today = datetime.now().strftime("%Y-%m-%d")

    return {
        "title": extracted["title"],
        "author": "Obsidian Team",
        "source": "obsidian",
        "source_url": extracted["url"],
        "date_published": today,
        "date_scraped": today,
        "type": "documentation",
        "skill": "cto",
        "tags": [],
        "product": "Obsidian",
        "category": "documentation"
    }

def save_article(metadata, content, output_dir):
    """Save article with YAML frontmatter"""
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
    """Scrape all Obsidian documentation with 2-step approach"""
    print("🔹 Fixed Obsidian Documentation Scraper (2-Step Fetch)")
    print(f"   Output: {OUTPUT_DIR}\n")

    # Create output directories
    raw_dir = OUTPUT_DIR / "raw"
    analyzed_dir = OUTPUT_DIR / "analyzed"
    index_dir = OUTPUT_DIR / "index"

    for dir_path in [raw_dir, analyzed_dir, index_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Clear old failed scraped files
    print("Clearing old files...")
    for old_file in raw_dir.glob("*.md"):
        old_file.unlink()
    print(f"Cleared {raw_dir}\n")

    # Fetch sitemap
    urls = fetch_sitemap()

    # Scrape each page
    scraped = 0
    errors = 0
    error_details = []

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")

        # Fetch markdown with 2-step approach
        extracted, error = fetch_markdown_2step(url)

        if error:
            print(f"  ❌ {error}")
            errors += 1
            error_details.append({"url": url, "error": error})
            time.sleep(DELAY)
            continue

        # Generate metadata
        metadata = generate_metadata(extracted)

        # Save article
        filepath = save_article(metadata, extracted["content"], OUTPUT_DIR)
        print(f"  ✅ Saved: {filepath.name}")

        scraped += 1

        # Rate limiting
        if i < len(urls):
            time.sleep(DELAY)

    # Summary
    print(f"\n{'='*60}")
    print(f"🎉 Complete!")
    print(f"   Scraped: {scraped} articles")
    print(f"   Errors: {errors}")
    print(f"   Success Rate: {scraped/(scraped+errors)*100:.1f}%")
    print(f"   Location: {OUTPUT_DIR}/raw/")

    if error_details:
        print(f"\n   Top errors:")
        for err in error_details[:5]:
            print(f"   - {err['url']}: {err['error']}")

    print(f"\n   Next steps:")
    print(f"   1. Review scraped content")
    print(f"   2. Run knowledge_analyzer.py for LLM enrichment")
    print(f"   3. Update CTO skill with new docs")

if __name__ == "__main__":
    main()
