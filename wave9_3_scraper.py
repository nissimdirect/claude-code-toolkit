#!/usr/bin/env python3
"""Wave 9.3 Scraper — /first-1000 Knowledge Base (Acquisition Playbooks)

Sources:
1. Dan Martell (WP REST API) — 669 posts
2. Amy Hoy / Stacking the Bricks (HTML scrape from /articles/) — 197 posts
3. Dent Global / Daniel Priestley (WP REST API) — 5 posts

Blocked sources (not included):
- Rob Walling (Squarespace robots.txt)
- MicroConf (Squarespace robots.txt)
- Indie Hackers (Cloudflare challenge)
- Russell Brunson (ClickFunnels, no blog)

Usage:
    python3 wave9_3_scraper.py --source dan-martell
    python3 wave9_3_scraper.py --source stacking-the-bricks
    python3 wave9_3_scraper.py --source dent-global
    python3 wave9_3_scraper.py --all
    python3 wave9_3_scraper.py --summary
"""

import argparse
import re
import time
from datetime import datetime
from pathlib import Path

import html2text
import requests
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────────────────

KB_BASE = Path.home() / "Development" / "knowledge-bases" / "first-1000"

DEFAULT_DELAY = 1.0
BATCH_PAUSE = 2.0

H2T = html2text.HTML2Text()
H2T.ignore_links = False
H2T.ignore_images = True
H2T.ignore_emphasis = False
H2T.body_width = 0
H2T.unicode_snob = True

HEADERS = {
    "User-Agent": "Claude-Code-KB-Scraper/1.0 (Knowledge Base Builder; +popchaoslabs.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── Source Definitions ─────────────────────────────────────────────────────

SOURCES = {
    "dan-martell": {
        "name": "Dan Martell",
        "type": "wp-api",
        "api_url": "https://www.danmartell.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "dan-martell",
        "total_est": 669,
    },
    "stacking-the-bricks": {
        "name": "Amy Hoy / Stacking the Bricks",
        "type": "article-list",
        "list_url": "https://stackingthebricks.com/articles/",
        "base_url": "https://stackingthebricks.com",
        "output_dir": KB_BASE / "stacking-the-bricks",
        "total_est": 197,
    },
    "dent-global": {
        "name": "Dent Global / Daniel Priestley",
        "type": "wp-api",
        "api_url": "https://www.dent.global/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "dent-global",
        "total_est": 5,
    },
}


# ── Utility Functions ──────────────────────────────────────────────────────


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:120]


def save_article(
    output_dir: Path,
    index: int,
    title: str,
    content: str,
    url: str,
    date: str = "",
    author: str = "",
) -> Path:
    slug = slugify(title) if title else f"article-{index:04d}"
    filename = f"{index:04d}-{slug}.md"
    filepath = output_dir / filename
    frontmatter = f"""---
title: "{title.replace('"', "'")}"
url: "{url}"
date: "{date}"
author: "{author}"
source: "wave-9.3-first-1000"
scraped: "{datetime.now().isoformat()}"
---

# {title}

"""
    filepath.write_text(frontmatter + content, encoding="utf-8")
    return filepath


def html_to_markdown(html_content: str) -> str:
    if not html_content:
        return ""
    return H2T.handle(html_content).strip()


def rate_limit(delay: float = DEFAULT_DELAY):
    time.sleep(delay)


def get_scraped_urls(output_dir: Path) -> set:
    urls = set()
    if not output_dir.exists():
        return urls
    for f in output_dir.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8")
            match = re.search(r'^url:\s*"([^"]*)"', text, re.MULTILINE)
            if match:
                urls.add(match.group(1))
        except Exception:
            pass
    return urls


# ── WP REST API Scraper ───────────────────────────────────────────────────


def scrape_wp_api(source_key: str) -> dict:
    source = SOURCES[source_key]
    api_url = source["api_url"]
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = list(output_dir.glob("*.md"))
    resume_from = len(existing)

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    try:
        resp = requests.get(
            api_url, params={"per_page": 1}, headers=HEADERS, timeout=30
        )
        resp.raise_for_status()
        total = int(resp.headers.get("X-WP-Total", 0))
        total_pages = int(resp.headers.get("X-WP-TotalPages", 0))
    except Exception as e:
        print(f"  ERROR getting total count: {e}")
        total = source["total_est"]
        total_pages = (total // 100) + 1

    print(f"  Total posts: {total} ({total_pages} pages)")

    if resume_from > 0:
        print(f"  Found {resume_from} existing files. Resuming...")

    article_index = resume_from
    start_page = (resume_from // 100) + 1

    for page in range(start_page, total_pages + 1):
        print(f"  Fetching page {page}/{total_pages}...")

        try:
            resp = requests.get(
                api_url,
                params={
                    "per_page": 100,
                    "page": page,
                    "orderby": "date",
                    "order": "asc",
                },
                headers=HEADERS,
                timeout=30,
            )
            if resp.status_code == 400:
                print(f"  Page {page} returned 400 — no more pages.")
                break
            resp.raise_for_status()
            posts = resp.json()
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 400:
                break
            print(f"    ERROR fetching page {page}: {e}")
            stats["failed"] += 1
            rate_limit(5.0)
            continue
        except Exception as e:
            print(f"    ERROR fetching page {page}: {e}")
            stats["failed"] += 1
            rate_limit(5.0)
            continue

        if not posts:
            break

        for post in posts:
            stats["attempted"] += 1
            article_index += 1

            try:
                title = BeautifulSoup(
                    post["title"]["rendered"], "html.parser"
                ).get_text()
                html_content = post["content"]["rendered"]
                md_content = html_to_markdown(html_content)
                url = post.get("link", "")
                date = post.get("date", "")
                author_id = post.get("author", "")

                if len(md_content.split()) < 30:
                    stats["skipped"] += 1
                    continue

                save_article(
                    output_dir,
                    article_index,
                    title,
                    md_content,
                    url,
                    date,
                    str(author_id),
                )
                stats["success"] += 1

            except Exception as e:
                print(f"    ERROR processing post {article_index}: {e}")
                stats["failed"] += 1

        if page % 10 == 0:
            rate_limit(BATCH_PAUSE)
        else:
            rate_limit(DEFAULT_DELAY)

    return stats


# ── Article List Scraper (Stacking the Bricks) ───────────────────────────


def scrape_article_list(source_key: str) -> dict:
    """Scrape articles from a page that lists all articles with links."""
    source = SOURCES[source_key]
    list_url = source["list_url"]
    base_url = source["base_url"]
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    scraped_urls = get_scraped_urls(output_dir)
    existing_count = len(scraped_urls)
    if existing_count:
        print(f"  Found {existing_count} existing files.")

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    # Step 1: Fetch the articles list page
    print(f"  Fetching article list: {list_url}")
    try:
        resp = requests.get(list_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching article list: {e}")
        return {"attempted": 0, "success": 0, "failed": 1, "skipped": 0}

    # Step 2: Extract all article links
    soup = BeautifulSoup(resp.text, "html.parser")
    article_links = []

    # Find all links that point to articles (not /articles/ itself, not external)
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Skip non-article links
        if href in ("/", "/articles/", "#") or href.startswith("http"):
            continue
        if href.startswith("/"):
            full_url = base_url + href
            title_text = a_tag.get_text(strip=True)
            if title_text and len(title_text) > 5:
                article_links.append((full_url, title_text))

    # Deduplicate
    seen = set()
    unique_links = []
    for url, title in article_links:
        if url not in seen:
            seen.add(url)
            unique_links.append((url, title))

    print(f"  Found {len(unique_links)} unique article links")

    article_index = existing_count
    batch_count = 0

    for i, (url, list_title) in enumerate(unique_links):
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

            page_soup = BeautifulSoup(resp.text, "html.parser")

            # Title
            title = ""
            h1 = page_soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
            if not title:
                title = list_title

            # Author
            author = "Amy Hoy"
            author_el = page_soup.find("meta", {"name": "author"})
            if author_el:
                author = author_el.get("content", "Amy Hoy")

            # Content
            content = ""
            for selector in [
                "article",
                ".post-content",
                ".entry-content",
                ".article-content",
                "main",
                ".content",
            ]:
                content_el = page_soup.select_one(selector)
                if content_el:
                    for tag in content_el.find_all(
                        ["nav", "header", "footer", "aside", "script", "style"]
                    ):
                        tag.decompose()
                    content = html_to_markdown(str(content_el))
                    if len(content.split()) > 30:
                        break

            if not content:
                body = page_soup.find("body")
                if body:
                    for tag in body.find_all(
                        ["nav", "header", "footer", "aside", "script", "style"]
                    ):
                        tag.decompose()
                    content = html_to_markdown(str(body))

            if len(content.split()) < 30:
                stats["skipped"] += 1
                continue

            save_article(output_dir, article_index, title, content, url, "", author)
            stats["success"] += 1

            if stats["success"] % 25 == 0:
                print(
                    f"    Progress: {stats['success']} saved ({i + 1}/{len(unique_links)} URLs)"
                )

        except requests.exceptions.Timeout:
            print(f"    TIMEOUT: {url}")
            stats["failed"] += 1
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 429:
                print("    RATE LIMITED. Pausing 30s...")
                time.sleep(30)
                stats["failed"] += 1
            else:
                print(
                    f"    HTTP ERROR {e.response.status_code if e.response else '?'}: {url}"
                )
                stats["failed"] += 1
        except Exception as e:
            print(f"    ERROR: {url} — {e}")
            stats["failed"] += 1

        if batch_count % 10 == 0:
            rate_limit(BATCH_PAUSE)
        else:
            rate_limit(DEFAULT_DELAY)

    return stats


# ── Main Orchestrator ──────────────────────────────────────────────────────

SCRAPERS = {
    "wp-api": scrape_wp_api,
    "article-list": scrape_article_list,
}


def scrape_source(source_key: str) -> dict:
    source = SOURCES[source_key]
    print(f"\n{'=' * 60}")
    print(f"Scraping: {source['name']}")
    print(f"Type: {source['type']}")
    print(f"Output: {source['output_dir']}")
    print(f"{'=' * 60}")

    scraper = SCRAPERS.get(source["type"])
    if not scraper:
        print(f"  Unknown source type: {source['type']}")
        return {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    return scraper(source_key)


def print_summary():
    print("\n" + "=" * 60)
    print("Wave 9.3 — Source Summary")
    print("=" * 60)
    total_est = 0
    total_existing = 0
    for key, source in SOURCES.items():
        output_dir = source["output_dir"]
        existing = 0
        if output_dir.exists():
            existing = len(list(output_dir.glob("*.md")))
        status = "DONE" if existing > 0 else "PENDING"
        print(
            f"  {source['name']:40s} | Est: {source['total_est']:>5d} | Existing: {existing:>5d} | {status}"
        )
        total_est += source["total_est"]
        total_existing += existing

    print(f"\n  {'TOTAL':40s} | Est: {total_est:>5d} | Existing: {total_existing:>5d}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Wave 9.3 scraper for /first-1000 KB (Acquisition)"
    )
    parser.add_argument(
        "--source", choices=list(SOURCES.keys()), help="Scrape a specific source"
    )
    parser.add_argument("--all", action="store_true", help="Scrape all sources")
    parser.add_argument("--summary", action="store_true", help="Show scraping summary")
    args = parser.parse_args()

    if args.summary:
        print_summary()
        return

    if not args.source and not args.all:
        print("Usage: python3 wave9_3_scraper.py --source <name> | --all | --summary")
        print(f"Available sources: {', '.join(SOURCES.keys())}")
        return

    sources_to_scrape = list(SOURCES.keys()) if args.all else [args.source]
    all_stats = {}

    start_time = time.time()

    for source_key in sources_to_scrape:
        try:
            stats = scrape_source(source_key)
            all_stats[source_key] = stats
            print(
                f"\n  Results: {stats['success']} saved, {stats['failed']} failed, {stats['skipped']} skipped"
            )
        except Exception as e:
            print(f"\n  FATAL ERROR scraping {source_key}: {e}")
            import traceback

            traceback.print_exc()
            all_stats[source_key] = {
                "attempted": 0,
                "success": 0,
                "failed": 1,
                "skipped": 0,
            }

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("WAVE 9.3 SCRAPING COMPLETE")
    print("=" * 60)
    total_success = sum(s["success"] for s in all_stats.values())
    total_failed = sum(s["failed"] for s in all_stats.values())
    total_skipped = sum(s["skipped"] for s in all_stats.values())

    for key, stats in all_stats.items():
        print(
            f"  {SOURCES[key]['name']:40s} | {stats['success']:>4d} saved | {stats['failed']:>3d} failed | {stats['skipped']:>3d} skipped"
        )

    print(
        f"\n  TOTAL: {total_success} articles saved, {total_failed} failed, {total_skipped} skipped"
    )
    print(f"  Time: {elapsed:.0f}s ({elapsed / 60:.1f}m)")

    print_summary()

    # Auto-cleanup: sanitize + quality gate
    from post_scrape_cleanup import cleanup

    scraped_dirs = [
        SOURCES[k]["output_dir"]
        for k in sources_to_scrape
        if SOURCES[k]["output_dir"].exists()
    ]
    cleanup(scraped_dirs)

    print("\nBlocked sources (Wave 9.3):")
    print("  - Rob Walling: Squarespace robots.txt blocks ClaudeBot")
    print("  - MicroConf: Squarespace robots.txt blocks ClaudeBot")
    print("  - Indie Hackers: Cloudflare challenge blocks bots")
    print("  - Russell Brunson: ClickFunnels landing page, no blog")


if __name__ == "__main__":
    main()
