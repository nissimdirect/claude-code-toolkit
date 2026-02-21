#!/usr/bin/env python3
"""Wave 9 Scraper — /first-1000 Knowledge Base Sources

Scrapes Wave 9.1 (Core Engine) sources for the /first-1000 skill:
1. Andrew Chen (WP REST API) — 706 posts
2. Pat Flynn / Smart Passive Income (WP REST API) — 369 posts
3. First Round Review (Sitemap + HTML) — 947 posts
4. YC Library (Sitemap + HTML) — 448 posts
5. Arvid Kahl (symlink from existing marketing-hacker scrape) — 435 posts

Usage:
    python3 wave9_scraper.py --source andrew-chen
    python3 wave9_scraper.py --source pat-flynn
    python3 wave9_scraper.py --source first-round
    python3 wave9_scraper.py --source yc-library
    python3 wave9_scraper.py --source arvid-kahl
    python3 wave9_scraper.py --all          # Run all sources
    python3 wave9_scraper.py --summary      # Show what would be scraped
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import html2text
import requests
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────────────────

KB_BASE = Path.home() / "Development" / "knowledge-bases" / "first-1000"
SANITIZER_PATH = Path.home() / "Development" / "tools" / "content_sanitizer.py"
QUALITY_GATE_PATH = Path.home() / "Development" / "tools" / "kb_quality_gate.py"

# Rate limiting
DEFAULT_DELAY = 1.0  # seconds between requests
BATCH_PAUSE = 2.0    # seconds between batches of 10

# HTML to markdown converter
H2T = html2text.HTML2Text()
H2T.ignore_links = False
H2T.ignore_images = True
H2T.ignore_emphasis = False
H2T.body_width = 0  # Don't wrap lines
H2T.unicode_snob = True

HEADERS = {
    "User-Agent": "Claude-Code-KB-Scraper/1.0 (Knowledge Base Builder; +popchaoslabs.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Source Definitions ─────────────────────────────────────────────────────

SOURCES = {
    "andrew-chen": {
        "name": "Andrew Chen",
        "type": "wp-api",
        "api_url": "https://andrewchen.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "andrew-chen",
        "total_est": 706,
    },
    "pat-flynn": {
        "name": "Pat Flynn / Smart Passive Income",
        "type": "wp-api",
        "api_url": "https://www.smartpassiveincome.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "pat-flynn",
        "total_est": 369,
    },
    "first-round": {
        "name": "First Round Review",
        "type": "sitemap-html",
        "sitemap_url": "https://review.firstround.com/sitemap-posts.xml",
        "output_dir": KB_BASE / "first-round",
        "total_est": 947,
    },
    "yc-library": {
        "name": "Y Combinator Library",
        "type": "sitemap-html",
        "sitemap_url": "https://www.ycombinator.com/library/sitemap.xml",
        "output_dir": KB_BASE / "yc-library",
        "total_est": 448,
    },
    "arvid-kahl": {
        "name": "Arvid Kahl (symlink from marketing-hacker)",
        "type": "symlink",
        "source_dir": Path.home() / "Development" / "marketing-hacker" / "arvid-kahl" / "articles",
        "output_dir": KB_BASE / "arvid-kahl",
        "total_est": 435,
    },
}


# ── Utility Functions ──────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:120]


def save_article(output_dir: Path, index: int, title: str, content: str,
                 url: str, date: str = "", author: str = "") -> Path:
    """Save an article as markdown with frontmatter."""
    slug = slugify(title) if title else f"article-{index:04d}"
    filename = f"{index:04d}-{slug}.md"
    filepath = output_dir / filename

    frontmatter = f"""---
title: "{title.replace('"', "'")}"
url: "{url}"
date: "{date}"
author: "{author}"
source: "wave-9-first-1000"
scraped: "{datetime.now().isoformat()}"
---

# {title}

"""
    filepath.write_text(frontmatter + content, encoding="utf-8")
    return filepath


def html_to_markdown(html_content: str) -> str:
    """Convert HTML to clean markdown."""
    if not html_content:
        return ""
    return H2T.handle(html_content).strip()


def rate_limit(delay: float = DEFAULT_DELAY):
    """Sleep for rate limiting."""
    time.sleep(delay)


# ── WP REST API Scraper ───────────────────────────────────────────────────

def scrape_wp_api(source_key: str, resume_from: int = 0) -> dict:
    """Scrape all posts from a WordPress REST API endpoint."""
    source = SOURCES[source_key]
    api_url = source["api_url"]
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check existing files for resume capability
    existing = list(output_dir.glob("*.md"))
    if existing and resume_from == 0:
        resume_from = len(existing)
        print(f"  Found {len(existing)} existing files. Resuming from page {resume_from // 100 + 1}...")

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    # First, get total count
    resp = requests.get(api_url, params={"per_page": 1}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("X-WP-Total", 0))
    total_pages = int(resp.headers.get("X-WP-TotalPages", 0))
    print(f"  Total posts: {total} ({total_pages} pages)")

    article_index = resume_from
    start_page = (resume_from // 100) + 1

    for page in range(start_page, total_pages + 1):
        print(f"  Fetching page {page}/{total_pages}...")

        try:
            resp = requests.get(
                api_url,
                params={"per_page": 100, "page": page, "orderby": "date", "order": "asc"},
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            posts = resp.json()
        except Exception as e:
            print(f"    ERROR fetching page {page}: {e}")
            stats["failed"] += 1
            rate_limit(5.0)  # Longer pause on error
            continue

        for post in posts:
            stats["attempted"] += 1
            article_index += 1

            try:
                title = BeautifulSoup(post["title"]["rendered"], "html.parser").get_text()
                html_content = post["content"]["rendered"]
                md_content = html_to_markdown(html_content)
                url = post.get("link", "")
                date = post.get("date", "")
                author_id = post.get("author", "")

                # Skip very short articles (likely stubs)
                if len(md_content.split()) < 30:
                    stats["skipped"] += 1
                    continue

                save_article(output_dir, article_index, title, md_content,
                           url, date, str(author_id))
                stats["success"] += 1

            except Exception as e:
                print(f"    ERROR processing post {article_index}: {e}")
                stats["failed"] += 1

        # Batch pause every 10 pages
        if page % 10 == 0:
            print(f"    Batch pause ({BATCH_PAUSE}s)...")
            rate_limit(BATCH_PAUSE)
        else:
            rate_limit(DEFAULT_DELAY)

    return stats


# ── Sitemap + HTML Scraper ─────────────────────────────────────────────────

def get_sitemap_urls(sitemap_url: str) -> list[str]:
    """Extract article URLs from a sitemap XML."""
    resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    xml = resp.text

    urls = re.findall(r'<loc>([^<]+)</loc>', xml)
    # Filter out non-article URLs
    article_urls = []
    for url in urls:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        # Skip root, tag pages, category pages, sitemap refs
        if not path or path == "sitemap.xml" or "/tag/" in path:
            continue
        # For YC Library, only include /library/ URLs with content IDs
        if "ycombinator.com" in url:
            if "/library/" in url and len(path.split("/")) >= 2:
                # Skip meta pages like /library/bookmarks, /library/search etc
                lib_path = path.replace("library/", "")
                if lib_path and lib_path not in ("bookmarks", "continue-watching", "search", "founder_link", "sitemap.xml"):
                    article_urls.append(url)
        else:
            article_urls.append(url)

    return article_urls


def extract_first_round_article(html: str, url: str) -> tuple[str, str, str]:
    """Extract title, author, and content from First Round Review."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Author
    author = ""
    author_el = soup.find("meta", {"name": "author"})
    if author_el:
        author = author_el.get("content", "")

    # Content - First Round uses article tags or main content areas
    content = ""
    # Try various content selectors
    for selector in ["article", ".post-content", ".article-content", "main", ".content"]:
        content_el = soup.select_one(selector)
        if content_el:
            # Remove nav, header, footer, sidebar elements
            for tag in content_el.find_all(["nav", "header", "footer", "aside", "script", "style"]):
                tag.decompose()
            content = html_to_markdown(str(content_el))
            break

    if not content:
        # Fallback: get the largest text block
        body = soup.find("body")
        if body:
            for tag in body.find_all(["nav", "header", "footer", "aside", "script", "style"]):
                tag.decompose()
            content = html_to_markdown(str(body))

    return title, author, content


def extract_yc_library_article(html: str, url: str) -> tuple[str, str, str]:
    """Extract title, author, and content from YC Library page."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Author
    author = ""
    # YC Library often has author info in specific elements
    author_el = soup.find("meta", {"name": "author"})
    if author_el:
        author = author_el.get("content", "")

    # Content
    content = ""
    # YC Library uses various content containers
    for selector in ["article", ".ycdc-card", ".library-content", "main", ".content"]:
        content_el = soup.select_one(selector)
        if content_el:
            for tag in content_el.find_all(["nav", "header", "footer", "aside", "script", "style"]):
                tag.decompose()
            content = html_to_markdown(str(content_el))
            if len(content.split()) > 30:
                break

    if not content:
        body = soup.find("body")
        if body:
            for tag in body.find_all(["nav", "header", "footer", "aside", "script", "style"]):
                tag.decompose()
            content = html_to_markdown(str(body))

    return title, author, content


def scrape_sitemap_html(source_key: str, resume_from: int = 0) -> dict:
    """Scrape articles from sitemap URLs via HTML fetch."""
    source = SOURCES[source_key]
    sitemap_url = source["sitemap_url"]
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check existing for resume
    existing = list(output_dir.glob("*.md"))
    if existing and resume_from == 0:
        resume_from = len(existing)
        print(f"  Found {len(existing)} existing files.")

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    # Get URLs from sitemap
    print(f"  Fetching sitemap: {sitemap_url}")
    urls = get_sitemap_urls(sitemap_url)
    print(f"  Found {len(urls)} article URLs")

    # Choose extractor based on source
    if source_key == "first-round":
        extractor = extract_first_round_article
    elif source_key == "yc-library":
        extractor = extract_yc_library_article
    else:
        extractor = extract_first_round_article  # default fallback

    # Build set of already-scraped URLs for resume
    scraped_urls = set()
    for f in existing:
        try:
            text = f.read_text(encoding="utf-8")
            match = re.search(r'^url:\s*"([^"]*)"', text, re.MULTILINE)
            if match:
                scraped_urls.add(match.group(1))
        except Exception:
            pass

    article_index = resume_from
    batch_count = 0

    for i, url in enumerate(urls):
        if url in scraped_urls:
            continue

        stats["attempted"] += 1
        article_index += 1
        batch_count += 1

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 404:
                stats["skipped"] += 1
                continue
            resp.raise_for_status()

            title, author, content = extractor(resp.text, url)

            if not title:
                title = url.split("/")[-1].replace("-", " ").title()

            # Skip very short articles
            if len(content.split()) < 30:
                stats["skipped"] += 1
                continue

            save_article(output_dir, article_index, title, content,
                       url, "", author)
            stats["success"] += 1

            if stats["success"] % 50 == 0:
                print(f"    Progress: {stats['success']} articles saved ({i+1}/{len(urls)} URLs)")

        except requests.exceptions.Timeout:
            print(f"    TIMEOUT: {url}")
            stats["failed"] += 1
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 429:
                print(f"    RATE LIMITED. Pausing 30s...")
                time.sleep(30)
                stats["failed"] += 1
            else:
                print(f"    HTTP ERROR {e.response.status_code if e.response else '?'}: {url}")
                stats["failed"] += 1
        except Exception as e:
            print(f"    ERROR: {url} — {e}")
            stats["failed"] += 1

        # Rate limiting
        if batch_count % 10 == 0:
            rate_limit(BATCH_PAUSE)
        else:
            rate_limit(DEFAULT_DELAY)

    return stats


# ── Symlink Handler ────────────────────────────────────────────────────────

def setup_symlink(source_key: str) -> dict:
    """Create symlink from existing scraped content."""
    source = SOURCES[source_key]
    source_dir = source["source_dir"]
    output_dir = source["output_dir"]

    if not source_dir.exists():
        print(f"  ERROR: Source directory not found: {source_dir}")
        return {"attempted": 0, "success": 0, "failed": 1, "skipped": 0}

    # Count source articles
    source_articles = list(source_dir.glob("*.md"))
    count = len(source_articles)

    # If output_dir exists as a regular dir, remove it first (it was created empty)
    if output_dir.exists() and not output_dir.is_symlink():
        # Only remove if empty
        if not any(output_dir.iterdir()):
            output_dir.rmdir()
        else:
            print(f"  Output dir already has content ({len(list(output_dir.iterdir()))} items). Skipping.")
            return {"attempted": count, "success": count, "failed": 0, "skipped": 0}

    if output_dir.is_symlink():
        print(f"  Symlink already exists: {output_dir} -> {os.readlink(output_dir)}")
        return {"attempted": count, "success": count, "failed": 0, "skipped": 0}

    # Create symlink
    os.symlink(source_dir, output_dir)
    print(f"  Created symlink: {output_dir} -> {source_dir}")
    print(f"  Linked {count} articles")

    return {"attempted": count, "success": count, "failed": 0, "skipped": 0}


# ── Main Orchestrator ──────────────────────────────────────────────────────

def scrape_source(source_key: str) -> dict:
    """Scrape a single source."""
    source = SOURCES[source_key]
    print(f"\n{'='*60}")
    print(f"Scraping: {source['name']}")
    print(f"Type: {source['type']}")
    print(f"Output: {source['output_dir']}")
    print(f"{'='*60}")

    if source["type"] == "wp-api":
        return scrape_wp_api(source_key)
    elif source["type"] == "sitemap-html":
        return scrape_sitemap_html(source_key)
    elif source["type"] == "symlink":
        return setup_symlink(source_key)
    else:
        print(f"  Unknown source type: {source['type']}")
        return {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}


def print_summary():
    """Print summary of all sources."""
    print("\n" + "=" * 60)
    print("Wave 9.1 — Source Summary")
    print("=" * 60)
    total_est = 0
    total_existing = 0
    for key, source in SOURCES.items():
        output_dir = source["output_dir"]
        existing = 0
        if output_dir.exists():
            if output_dir.is_symlink():
                target = Path(os.readlink(output_dir))
                existing = len(list(target.glob("*.md")))
            else:
                existing = len(list(output_dir.glob("*.md")))

        status = "DONE" if existing > 0 else "PENDING"
        print(f"  {source['name']:40s} | Est: {source['total_est']:>5d} | Existing: {existing:>5d} | {status}")
        total_est += source["total_est"]
        total_existing += existing

    print(f"\n  {'TOTAL':40s} | Est: {total_est:>5d} | Existing: {total_existing:>5d}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Wave 9.1 scraper for /first-1000 KB")
    parser.add_argument("--source", choices=list(SOURCES.keys()), help="Scrape a specific source")
    parser.add_argument("--all", action="store_true", help="Scrape all sources")
    parser.add_argument("--summary", action="store_true", help="Show scraping summary")
    parser.add_argument("--sanitize", action="store_true", help="Run content sanitizer after scraping")
    parser.add_argument("--quality-gate", action="store_true", help="Run quality gate after scraping")
    args = parser.parse_args()

    if args.summary:
        print_summary()
        return

    if not args.source and not args.all:
        print("Usage: python3 wave9_scraper.py --source <name> | --all | --summary")
        print(f"Available sources: {', '.join(SOURCES.keys())}")
        return

    sources_to_scrape = list(SOURCES.keys()) if args.all else [args.source]
    all_stats = {}

    start_time = time.time()

    for source_key in sources_to_scrape:
        try:
            stats = scrape_source(source_key)
            all_stats[source_key] = stats
            print(f"\n  Results: {stats['success']} saved, {stats['failed']} failed, {stats['skipped']} skipped")
        except Exception as e:
            print(f"\n  FATAL ERROR scraping {source_key}: {e}")
            all_stats[source_key] = {"attempted": 0, "success": 0, "failed": 1, "skipped": 0}

    elapsed = time.time() - start_time

    # Print final report
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)
    total_success = sum(s["success"] for s in all_stats.values())
    total_failed = sum(s["failed"] for s in all_stats.values())
    total_skipped = sum(s["skipped"] for s in all_stats.values())

    for key, stats in all_stats.items():
        print(f"  {SOURCES[key]['name']:40s} | {stats['success']:>4d} saved | {stats['failed']:>3d} failed | {stats['skipped']:>3d} skipped")

    print(f"\n  TOTAL: {total_success} articles saved, {total_failed} failed, {total_skipped} skipped")
    print(f"  Time: {elapsed:.0f}s ({elapsed/60:.1f}m)")

    # Post-scrape steps
    if args.sanitize or args.all:
        print("\n" + "=" * 60)
        print("Running content sanitizer...")
        print("=" * 60)
        for source_key in sources_to_scrape:
            output_dir = SOURCES[source_key]["output_dir"]
            if output_dir.exists() and not output_dir.is_symlink():
                print(f"  Sanitizing: {output_dir}")
                os.system(f"python3 {SANITIZER_PATH} --dir {output_dir}")

    if args.quality_gate or args.all:
        print("\n" + "=" * 60)
        print("Running quality gate...")
        print("=" * 60)
        for source_key in sources_to_scrape:
            output_dir = SOURCES[source_key]["output_dir"]
            if output_dir.exists() and not output_dir.is_symlink():
                print(f"  Quality gate: {output_dir}")
                os.system(f"python3 {QUALITY_GATE_PATH} {output_dir} --fix")

    print_summary()

    print("\nNext steps:")
    print("  1. Verify: python3 ~/Development/tools/kb_loader.py context --advisor first-1000 --query 'how to get first customers'")
    print("  2. Spot-check 3-5 articles from each source")
    print("  3. If quality is good, Wave 9.1 is complete")


if __name__ == "__main__":
    main()
