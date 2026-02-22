#!/usr/bin/env python3
"""Wave 9.2 Scraper — /first-1000 Knowledge Base (PMF + Fandom)

Sources:
1. Nathan Barry (WP REST API) — 412 posts
2. Jay Clouse / Creator Science (Ghost sitemap + HTML) — 151 posts
3. Circle.so Blog (sitemap + HTML) — 101 posts
4. PMF Show (Buzzsprout RSS) — 166 episodes
5. Sean Ellis / GrowthHackers (WP REST API) — ~28 posts
6. Li Jin (Substack API) — ~30 posts

Usage:
    python3 wave9_2_scraper.py --source nathan-barry
    python3 wave9_2_scraper.py --source creator-science
    python3 wave9_2_scraper.py --source circle-so
    python3 wave9_2_scraper.py --source pmf-show
    python3 wave9_2_scraper.py --source growthhackers
    python3 wave9_2_scraper.py --source li-jin
    python3 wave9_2_scraper.py --all
    python3 wave9_2_scraper.py --summary
"""

import argparse
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import html2text
import requests
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────────────────

KB_BASE = Path.home() / "Development" / "knowledge-bases" / "first-1000"

# Rate limiting
DEFAULT_DELAY = 1.0
BATCH_PAUSE = 2.0

# HTML to markdown converter
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
    "nathan-barry": {
        "name": "Nathan Barry",
        "type": "wp-api",
        "api_url": "https://nathanbarry.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "nathan-barry",
        "total_est": 412,
    },
    "creator-science": {
        "name": "Jay Clouse / Creator Science",
        "type": "sitemap-html",
        "sitemap_url": "https://creatorscience.com/sitemap-posts.xml",
        "output_dir": KB_BASE / "creator-science",
        "total_est": 151,
        "extractor": "creator-science",
    },
    "circle-so": {
        "name": "Circle.so Blog",
        "type": "sitemap-html",
        "sitemap_url": "https://circle.so/sitemap.xml",
        "url_filter": "/blog/",
        "output_dir": KB_BASE / "circle-so",
        "total_est": 101,
        "extractor": "generic",
    },
    "pmf-show": {
        "name": "Product Market Fit Show",
        "type": "rss",
        "rss_url": "https://rss.buzzsprout.com/1889238.rss",
        "output_dir": KB_BASE / "pmf-show",
        "total_est": 166,
    },
    "growthhackers": {
        "name": "Sean Ellis / GrowthHackers",
        "type": "wp-api",
        "api_url": "https://growthhackers.com/wp-json/wp/v2/posts",
        "output_dir": KB_BASE / "growthhackers",
        "total_est": 28,
    },
    "li-jin": {
        "name": "Li Jin",
        "type": "substack",
        "publication_url": "https://www.lisnewsletter.com",
        "output_dir": KB_BASE / "li-jin",
        "total_est": 30,
    },
}


# ── Utility Functions ──────────────────────────────────────────────────────


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
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
    """Save an article as markdown with frontmatter."""
    slug = slugify(title) if title else f"article-{index:04d}"
    filename = f"{index:04d}-{slug}.md"
    filepath = output_dir / filename

    frontmatter = f"""---
title: "{title.replace('"', "'")}"
url: "{url}"
date: "{date}"
author: "{author}"
source: "wave-9.2-first-1000"
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


def get_scraped_urls(output_dir: Path) -> set:
    """Build set of already-scraped URLs from existing files."""
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
    """Scrape all posts from a WordPress REST API endpoint."""
    source = SOURCES[source_key]
    api_url = source["api_url"]
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    existing = list(output_dir.glob("*.md"))
    resume_from = len(existing)

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    # Get total count
    try:
        resp = requests.get(
            api_url, params={"per_page": 1}, headers=HEADERS, timeout=30
        )
        resp.raise_for_status()
        total = int(resp.headers.get("X-WP-Total", 0))
        total_pages = int(resp.headers.get("X-WP-TotalPages", 0))
    except Exception as e:
        print(f"  ERROR getting total count: {e}")
        # Fallback: paginate until empty
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
                # Past last page
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

                # Skip very short articles
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


# ── Sitemap + HTML Scraper ─────────────────────────────────────────────────


def get_sitemap_urls(sitemap_url: str, url_filter: str = None) -> list[str]:
    """Extract article URLs from a sitemap XML."""
    resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    xml_text = resp.text

    urls = re.findall(r"<loc>([^<]+)</loc>", xml_text)

    article_urls = []
    for url in urls:
        # Skip sitemap index refs
        if url.endswith(".xml"):
            continue
        # Apply URL filter if provided
        if url_filter and url_filter not in url:
            continue
        article_urls.append(url)

    return article_urls


def extract_creator_science(html: str, url: str) -> tuple[str, str, str]:
    """Extract content from Creator Science (Ghost CMS)."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Author
    author = "Jay Clouse"
    author_el = soup.find("meta", {"name": "author"})
    if author_el:
        author = author_el.get("content", "")

    # Content — Ghost typically uses .gh-content or article
    content = ""
    for selector in [".gh-content", ".post-content", "article", "main", ".content"]:
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

    return title, author, content


def extract_generic(html: str, url: str) -> tuple[str, str, str]:
    """Generic HTML article extractor."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = ""
    title_el = soup.find("h1")
    if title_el:
        title = title_el.get_text(strip=True)
    elif soup.find("title"):
        title = soup.find("title").get_text(strip=True)

    # Author
    author = ""
    for meta_name in ["author", "article:author"]:
        author_el = soup.find("meta", {"name": meta_name}) or soup.find(
            "meta", {"property": meta_name}
        )
        if author_el:
            author = author_el.get("content", "")
            break

    # Content — try common selectors
    content = ""
    for selector in [
        "article",
        ".post-content",
        ".article-content",
        ".blog-content",
        ".entry-content",
        "main",
        "[role='main']",
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

    return title, author, content


EXTRACTORS = {
    "creator-science": extract_creator_science,
    "generic": extract_generic,
}


def scrape_sitemap_html(source_key: str) -> dict:
    """Scrape articles from sitemap URLs via HTML fetch."""
    source = SOURCES[source_key]
    sitemap_url = source["sitemap_url"]
    output_dir = source["output_dir"]
    url_filter = source.get("url_filter")
    extractor_name = source.get("extractor", "generic")
    extractor = EXTRACTORS.get(extractor_name, extract_generic)

    output_dir.mkdir(parents=True, exist_ok=True)

    scraped_urls = get_scraped_urls(output_dir)
    existing_count = len(scraped_urls)
    if existing_count:
        print(f"  Found {existing_count} existing files.")

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    print(f"  Fetching sitemap: {sitemap_url}")
    urls = get_sitemap_urls(sitemap_url, url_filter)
    print(f"  Found {len(urls)} article URLs")

    article_index = existing_count
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

            if len(content.split()) < 30:
                stats["skipped"] += 1
                continue

            save_article(output_dir, article_index, title, content, url, "", author)
            stats["success"] += 1

            if stats["success"] % 25 == 0:
                print(
                    f"    Progress: {stats['success']} saved ({i + 1}/{len(urls)} URLs)"
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


# ── RSS Scraper (Buzzsprout) ──────────────────────────────────────────────


def scrape_rss(source_key: str) -> dict:
    """Scrape podcast episodes from RSS feed."""
    source = SOURCES[source_key]
    rss_url = source["rss_url"]
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    scraped_urls = get_scraped_urls(output_dir)
    existing_count = len(scraped_urls)
    if existing_count:
        print(f"  Found {existing_count} existing episodes.")

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    print(f"  Fetching RSS: {rss_url}")
    try:
        resp = requests.get(rss_url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching RSS: {e}")
        return {"attempted": 0, "success": 0, "failed": 1, "skipped": 0}

    # Parse RSS XML
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"  ERROR parsing RSS XML: {e}")
        return {"attempted": 0, "success": 0, "failed": 1, "skipped": 0}

    # Handle namespaces
    ns = {
        "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
        "content": "http://purl.org/rss/1.0/modules/content/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    channel = root.find("channel")
    if channel is None:
        print("  ERROR: No channel found in RSS")
        return {"attempted": 0, "success": 0, "failed": 1, "skipped": 0}

    items = channel.findall("item")
    print(f"  Found {len(items)} episodes")

    article_index = existing_count

    for item in items:
        # Episode URL
        link_el = item.find("link")
        url = link_el.text.strip() if link_el is not None and link_el.text else ""

        if url in scraped_urls:
            continue

        stats["attempted"] += 1
        article_index += 1

        # Title
        title_el = item.find("title")
        title = (
            title_el.text.strip()
            if title_el is not None and title_el.text
            else f"Episode {article_index}"
        )

        # Date
        pub_date_el = item.find("pubDate")
        date = (
            pub_date_el.text.strip()
            if pub_date_el is not None and pub_date_el.text
            else ""
        )

        # Author
        author_el = item.find("itunes:author", ns) or item.find("dc:creator", ns)
        author = (
            author_el.text.strip() if author_el is not None and author_el.text else ""
        )

        # Content — combine description + content:encoded + itunes:summary
        content_parts = []

        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            desc_md = html_to_markdown(desc_el.text)
            if desc_md:
                content_parts.append(desc_md)

        content_encoded = item.find("content:encoded", ns)
        if content_encoded is not None and content_encoded.text:
            ce_md = html_to_markdown(content_encoded.text)
            if ce_md and ce_md not in content_parts:
                content_parts.append(ce_md)

        itunes_summary = item.find("itunes:summary", ns)
        if itunes_summary is not None and itunes_summary.text:
            summary_text = itunes_summary.text.strip()
            if summary_text and summary_text not in "\n".join(content_parts):
                content_parts.append(f"\n## Summary\n\n{summary_text}")

        # Episode-specific metadata
        duration_el = item.find("itunes:duration", ns)
        duration = (
            duration_el.text.strip()
            if duration_el is not None and duration_el.text
            else ""
        )

        episode_el = item.find("itunes:episode", ns)
        episode_num = (
            episode_el.text.strip()
            if episode_el is not None and episode_el.text
            else ""
        )

        if duration or episode_num:
            meta_line = "\n## Episode Info\n\n"
            if episode_num:
                meta_line += f"- **Episode:** {episode_num}\n"
            if duration:
                meta_line += f"- **Duration:** {duration}\n"
            content_parts.append(meta_line)

        content = "\n\n".join(content_parts)

        if len(content.split()) < 15:
            stats["skipped"] += 1
            continue

        save_article(output_dir, article_index, title, content, url, date, author)
        stats["success"] += 1

    return stats


# ── Substack Scraper ──────────────────────────────────────────────────────


def scrape_substack(source_key: str) -> dict:
    """Scrape posts from a Substack publication using their API."""
    source = SOURCES[source_key]
    pub_url = source["publication_url"]
    output_dir = source["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    scraped_urls = get_scraped_urls(output_dir)
    existing_count = len(scraped_urls)
    if existing_count:
        print(f"  Found {existing_count} existing posts.")

    stats = {"attempted": 0, "success": 0, "failed": 0, "skipped": 0}

    # Substack provides an API at /api/v1/archive
    api_url = f"{pub_url}/api/v1/archive"
    all_posts = []
    offset = 0
    limit = 12

    print(f"  Fetching Substack archive: {api_url}")

    while True:
        try:
            resp = requests.get(
                api_url,
                params={"sort": "new", "offset": offset, "limit": limit},
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            posts = resp.json()

            if not posts:
                break

            all_posts.extend(posts)
            offset += limit
            print(f"    Fetched {len(all_posts)} posts so far...")

            rate_limit(1.5)

        except Exception as e:
            print(f"    ERROR at offset {offset}: {e}")
            stats["failed"] += 1
            break

    print(f"  Total posts found: {len(all_posts)}")

    article_index = existing_count

    for post in all_posts:
        url = post.get("canonical_url", "")
        if not url:
            url = f"{pub_url}/p/{post.get('slug', '')}"

        if url in scraped_urls:
            continue

        stats["attempted"] += 1
        article_index += 1

        title = post.get("title", f"Post {article_index}")
        subtitle = post.get("subtitle", "")
        date = post.get("post_date", "")
        author_data = post.get("publishedBylines", [])
        author = author_data[0].get("name", "Li Jin") if author_data else "Li Jin"

        # Get full post content via individual post API
        post_slug = post.get("slug", "")
        content = ""

        if post.get("body_html"):
            content = html_to_markdown(post["body_html"])
        elif post_slug:
            # Try fetching individual post
            try:
                post_resp = requests.get(
                    f"{pub_url}/api/v1/posts/{post_slug}",
                    headers=HEADERS,
                    timeout=30,
                )
                if post_resp.status_code == 200:
                    post_data = post_resp.json()
                    body_html = post_data.get("body_html", "")
                    if body_html:
                        content = html_to_markdown(body_html)
                rate_limit(1.0)
            except Exception:
                pass

        # Fallback to truncated body from archive
        if not content:
            truncated = post.get("truncated_body_text", "")
            description = post.get("description", "")
            content = truncated or description

        if subtitle:
            content = f"*{subtitle}*\n\n{content}"

        if len(content.split()) < 15:
            stats["skipped"] += 1
            continue

        save_article(output_dir, article_index, title, content, url, date, author)
        stats["success"] += 1

    return stats


# ── Main Orchestrator ──────────────────────────────────────────────────────

SCRAPERS = {
    "wp-api": scrape_wp_api,
    "sitemap-html": scrape_sitemap_html,
    "rss": scrape_rss,
    "substack": scrape_substack,
}


def scrape_source(source_key: str) -> dict:
    """Scrape a single source."""
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
    """Print summary of all sources."""
    print("\n" + "=" * 60)
    print("Wave 9.2 — Source Summary")
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
        description="Wave 9.2 scraper for /first-1000 KB (PMF + Fandom)"
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
        print("Usage: python3 wave9_2_scraper.py --source <name> | --all | --summary")
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

    # Final report
    print("\n" + "=" * 60)
    print("WAVE 9.2 SCRAPING COMPLETE")
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

    print("\nNext steps:")
    print(
        "  1. Verify: python3 ~/Development/tools/kb_loader.py context --advisor first-1000 --query 'product market fit'"
    )
    print("  2. Spot-check 3-5 articles from each source")
    print("  3. Update RESEARCH-SCRAPE-BACKLOG.md with Wave 9.2 results")


if __name__ == "__main__":
    main()
