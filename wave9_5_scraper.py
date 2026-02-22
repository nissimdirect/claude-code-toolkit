#!/usr/bin/env python3
"""Wave 9.5 Scraper — /first-1000 Knowledge Base (Supplementary)

Sources:
1. Kevin Kelly (WP REST API) — 847 posts
2. Noah Kagan (WP REST API) — 619 posts
3. Niche Pursuits (WP REST API) — 3,633 posts
4. Copyblogger (WP REST API) — 2,387 posts
5. Ramit Sethi (WP REST API) — 875 posts
6. Hiten Shah (WP REST API) — 138 posts
7. Marie Forleo (sitemap + HTML) — 661 posts
8. Ship 30 for 30 (sitemap + HTML) — 173 posts
9. Codie Sanchez (sitemap + HTML) — 121 posts
10. Demand Curve (sitemap + HTML) — 38 posts
11. Newsletter Circle (Substack API) — ~162 posts

Skipped:
- Sahil Lavingia (Next.js, only ~6 essays)
- Sunny Lenarduzzi (Incapsula bot protection)
- Brennan Dunn (Statamic CMS, no API)
- Reforge (paywall redirect)
- The Publish Press (no API/sitemap)

Usage:
    python3 wave9_5_scraper.py --source kevin-kelly
    python3 wave9_5_scraper.py --source noah-kagan
    python3 wave9_5_scraper.py --all
    python3 wave9_5_scraper.py --summary
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

SOURCES = {
    "kevin-kelly": {
        "name": "Kevin Kelly",
        "type": "wp-api",
        "api_url": "https://kk.org/thetechnium/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "kevin-kelly",
        "total_est": 847,
    },
    "noah-kagan": {
        "name": "Noah Kagan",
        "type": "wp-api",
        "api_url": "https://noahkagan.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "noah-kagan",
        "total_est": 619,
    },
    "niche-pursuits": {
        "name": "Niche Pursuits",
        "type": "wp-api",
        "api_url": "https://www.nichepursuits.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "niche-pursuits",
        "total_est": 3633,
    },
    "copyblogger": {
        "name": "Copyblogger",
        "type": "wp-api",
        "api_url": "https://copyblogger.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "copyblogger",
        "total_est": 2387,
    },
    "ramit-sethi": {
        "name": "Ramit Sethi",
        "type": "wp-api",
        "api_url": "https://www.iwillteachyoutoberich.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "ramit-sethi",
        "total_est": 875,
    },
    "hiten-shah": {
        "name": "Hiten Shah",
        "type": "wp-api",
        "api_url": "https://hitenism.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "hiten-shah",
        "total_est": 138,
    },
    "marie-forleo": {
        "name": "Marie Forleo",
        "type": "sitemap-html",
        "sitemap_url": "https://www.marieforleo.com/sitemap.xml",
        "url_filter": "/blog/",
        "output_dir": KB_BASE / "marie-forleo",
        "total_est": 661,
    },
    "ship30for30": {
        "name": "Ship 30 for 30",
        "type": "sitemap-html",
        "sitemap_url": "https://www.ship30for30.com/sitemap.xml",
        "url_filter": "/post/",
        "output_dir": KB_BASE / "ship30for30",
        "total_est": 173,
    },
    "codie-sanchez": {
        "name": "Codie Sanchez",
        "type": "sitemap-html",
        "sitemap_url": "https://www.contrarianthinking.co/sitemap.xml",
        "url_filter": "/newsletter-articles/",
        "output_dir": KB_BASE / "codie-sanchez",
        "total_est": 121,
    },
    "demand-curve": {
        "name": "Demand Curve",
        "type": "sitemap-html",
        "sitemap_url": "https://www.demandcurve.com/sitemap.xml",
        "url_filter": "/blog/",
        "output_dir": KB_BASE / "demand-curve",
        "total_est": 38,
    },
    "newsletter-circle": {
        "name": "Newsletter Circle",
        "type": "substack",
        "substack_url": "https://newslettercircle.substack.com",
        "output_dir": KB_BASE / "newsletter-circle",
        "total_est": 162,
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
source: "wave-9.5-first-1000"
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


# ── Sitemap + HTML Scraper ────────────────────────────────────────────────


def scrape_sitemap_html(source_key: str) -> dict:
    source = SOURCES[source_key]
    sitemap_url = source["sitemap_url"]
    url_filter = source.get("url_filter")
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    scraped_urls = get_scraped_urls(output_dir)
    existing_count = len(scraped_urls)
    if existing_count:
        print(f"  Found {existing_count} existing files.")

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    print(f"  Fetching sitemap: {sitemap_url}")
    try:
        resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching sitemap: {e}")
        return {"attempted": 0, "success": 0, "failed": 1, "skipped": 0}

    urls = re.findall(r"<loc>([^<]+)</loc>", resp.text)
    article_urls = []
    for url in urls:
        if url.endswith(".xml"):
            continue
        if url_filter and url_filter not in url:
            continue
        article_urls.append(url)

    print(f"  Found {len(article_urls)} article URLs")

    article_index = existing_count

    for i, url in enumerate(article_urls):
        if url in scraped_urls:
            continue

        stats["attempted"] += 1
        article_index += 1

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 404:
                stats["skipped"] += 1
                continue
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Title
            title = ""
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
            if not title and soup.find("title"):
                title = soup.find("title").get_text(strip=True)

            # Author
            author = ""
            author_el = soup.find("meta", {"name": "author"})
            if author_el:
                author = author_el.get("content", "")

            # Content — try various selectors
            content = ""
            for selector in [
                ".blog-post__body",
                ".post-body",
                ".rich-text-block",
                "article",
                ".hs-blog-post",
                ".entry-content",
                ".post-content",
                "main",
                ".content",
            ]:
                content_el = soup.select_one(selector)
                if content_el:
                    for tag in content_el.find_all(
                        ["nav", "header", "footer", "aside", "script", "style"]
                    ):
                        tag.decompose()
                    content = html_to_markdown(str(content_el))
                    if len(content.split()) > 30:
                        break

            if not content:
                body = soup.find("body")
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

        rate_limit(DEFAULT_DELAY)

    return stats


# ── Substack API Scraper ──────────────────────────────────────────────────


def scrape_substack(source_key: str) -> dict:
    source = SOURCES[source_key]
    substack_url = source["substack_url"]
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    scraped_urls = get_scraped_urls(output_dir)
    existing_count = len(scraped_urls)
    if existing_count:
        print(f"  Found {existing_count} existing files.")

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    article_index = existing_count
    offset = 0
    batch_size = 12

    while True:
        print(f"  Fetching offset {offset}...")

        try:
            resp = requests.get(
                f"{substack_url}/api/v1/archive",
                params={
                    "sort": "new",
                    "search": "",
                    "offset": offset,
                    "limit": batch_size,
                },
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            posts = resp.json()
        except Exception as e:
            print(f"    ERROR fetching archive at offset {offset}: {e}")
            stats["failed"] += 1
            break

        if not posts:
            break

        for post in posts:
            stats["attempted"] += 1

            try:
                title = post.get("title", "")
                url = post.get("canonical_url", "")
                date = post.get("post_date", "")
                author_name = ""
                if post.get("publishedBylines"):
                    author_name = post["publishedBylines"][0].get("name", "")

                html_content = post.get("body_html", "")
                if not html_content:
                    # body_html missing — fetch the page directly
                    if not url:
                        slug = post.get("slug", "")
                        url = f"{substack_url}/p/{slug}"
                    try:
                        page_resp = requests.get(url, headers=HEADERS, timeout=30)
                        page_resp.raise_for_status()
                        soup = BeautifulSoup(page_resp.text, "html.parser")
                        body_el = (
                            soup.select_one(".body.markup")
                            or soup.select_one(".post-content")
                            or soup.select_one("article")
                        )
                        if body_el:
                            html_content = str(body_el)
                        rate_limit(DEFAULT_DELAY)
                    except Exception as fetch_err:
                        print(f"    ERROR fetching post page: {fetch_err}")
                        stats["failed"] += 1
                        continue

                if not html_content:
                    stats["skipped"] += 1
                    continue

                if url in scraped_urls:
                    continue

                md_content = html_to_markdown(html_content)

                if len(md_content.split()) < 30:
                    stats["skipped"] += 1
                    continue

                article_index += 1
                save_article(
                    output_dir, article_index, title, md_content, url, date, author_name
                )
                stats["success"] += 1

            except Exception as e:
                print(f"    ERROR processing post: {e}")
                stats["failed"] += 1

        offset += batch_size
        rate_limit(DEFAULT_DELAY)

    return stats


# ── Main Orchestrator ──────────────────────────────────────────────────────

SCRAPERS = {
    "wp-api": scrape_wp_api,
    "sitemap-html": scrape_sitemap_html,
    "substack": scrape_substack,
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
    print("Wave 9.5 — Source Summary")
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
        description="Wave 9.5 scraper for /first-1000 KB (Supplementary)"
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
        print("Usage: python3 wave9_5_scraper.py --source <name> | --all | --summary")
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
    print("WAVE 9.5 SCRAPING COMPLETE")
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

    print("\nSkipped sources (Wave 9.5):")
    print("  - Sahil Lavingia: Next.js, only ~6 essays")
    print("  - Sunny Lenarduzzi: Incapsula bot protection")
    print("  - Brennan Dunn: Statamic CMS, no API")
    print("  - Reforge: Paywall redirect")
    print("  - The Publish Press: No API/sitemap")


if __name__ == "__main__":
    main()
