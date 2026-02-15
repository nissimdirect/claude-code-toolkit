#!/usr/bin/env python3
"""E-flux Journal Re-scraper — Extracts article text from Next.js RSC payloads.

E-flux uses React Server Components (Next.js App Router). Article body text
is embedded in self.__next_f.push() script tags as escaped HTML, NOT in the
regular DOM. BeautifulSoup alone misses it entirely (gets zero-width chars).

This scraper:
1. Fetches each article page
2. Extracts text from RSC script payloads (escaped HTML like \\u003cp\\u003e)
3. Converts to clean markdown
4. Saves with proper frontmatter

Usage:
    python3 scrape_eflux.py                  # Scrape all issues (1-160)
    python3 scrape_eflux.py --issues 140-145 # Scrape specific issue range
    python3 scrape_eflux.py --test           # Test with 1 article
"""

import argparse
import json
import re
import time
import html
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md


OUTPUT_DIR = Path("~/Development/art-criticism/e-flux-journal/articles").expanduser()
RATE_LIMIT = 1.5  # seconds between requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PopChaosLabs-KB-Scraper/1.0",
}


def fetch_page(url: str) -> requests.Response | None:
    """Fetch a page with rate limiting and error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        time.sleep(RATE_LIMIT)
        if resp.status_code == 200:
            return resp
        print(f"  HTTP {resp.status_code}: {url}")
        return None
    except requests.RequestException as e:
        print(f"  Error fetching {url}: {e}")
        return None


def extract_rsc_html(page_html: str) -> str:
    """Extract article HTML from Next.js RSC script payloads.

    RSC payloads look like:
        self.__next_f.push([1,"\\u003cp\\u003eSome text..."])

    The escaped HTML contains the actual article body.
    """
    # Find all self.__next_f.push payloads
    pattern = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.DOTALL)
    matches = pattern.findall(page_html)

    # Filter for chunks that contain actual article HTML (paragraphs)
    html_chunks = []
    for chunk in matches:
        # Skip chunks that are RSC component structure (JSON-like, not article text)
        if chunk.startswith(('[', '{')) or '"className"' in chunk[:200]:
            # But allow chunks that START with HTML tags (escaped)
            if not chunk.startswith('\\u003c'):
                continue

        # Only keep chunks that contain paragraph HTML
        if '\\u003cp\\u003e' not in chunk and '\\u003c/p\\u003e' not in chunk:
            continue

        # Skip "related articles" sections
        if 'related__item' in chunk or 'related ' in chunk[:100]:
            continue

        # Unescape: JSON string escaping -> Unicode -> HTML entities
        try:
            # Handle the double-encoding: \\u003c -> literal bytes
            # Use raw_unicode_escape to handle the mixed encoding properly
            unescaped = chunk.encode('utf-8').decode('unicode_escape')
        except (UnicodeDecodeError, UnicodeError):
            # Fallback: just replace the common escaped HTML tags manually
            unescaped = chunk
            unescaped = unescaped.replace('\\u003c', '<')
            unescaped = unescaped.replace('\\u003e', '>')
            unescaped = unescaped.replace('\\u003C', '<')
            unescaped = unescaped.replace('\\u003E', '>')

        # Fix mojibake from unicode_escape mangling UTF-8
        # unicode_escape treats bytes as Latin-1, so re-encode and decode as UTF-8
        try:
            unescaped = unescaped.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass

        # Further unescape HTML entities
        unescaped = html.unescape(unescaped)
        # Clean up remaining escape artifacts
        unescaped = unescaped.replace('\\n', '\n')
        unescaped = unescaped.replace('\\"', '"')

        html_chunks.append(unescaped)

    return "\n".join(html_chunks)


def extract_article_content(page_html: str, url: str) -> dict | None:
    """Extract article metadata and content from an e-flux page."""
    soup = BeautifulSoup(page_html, 'html.parser')

    # Title
    title = None
    h1 = soup.find('h1')
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.text.strip().split(' - ')[0].strip()
    if not title:
        title = "Untitled"

    # Author from RSC data or meta tags
    author = "e-flux"
    # Try meta tag
    for meta in soup.find_all('meta'):
        if meta.get('name') == 'author' or meta.get('property') == 'article:author':
            author = meta.get('content', author)
            break

    # Try h2 with author class
    h2_author = soup.find('h2', class_=lambda c: c and 'author' in c.lower() if c else False)
    if h2_author and h2_author.get_text(strip=True):
        author = h2_author.get_text(strip=True)

    # If no author found in DOM, search RSC payload for author name
    if author == "e-flux":
        author_match = re.search(r'"article__header-authors?"[^>]*>([^<]+)<', page_html)
        if author_match:
            author = html.unescape(author_match.group(1)).strip()
        # Also try RSC-encoded version
        author_match2 = re.search(r'header-authors[^"]*"[^}]*"children":"([^"]+)"', page_html)
        if author_match2:
            found = html.unescape(author_match2.group(1)).strip()
            if found and found != "e-flux":
                author = found

    # Issue/date from URL
    issue_match = re.search(r'/journal/(\d+)/', url)
    issue_num = issue_match.group(1) if issue_match else ""

    # Extract body from RSC payloads
    rsc_html = extract_rsc_html(page_html)

    if rsc_html:
        # Parse the extracted HTML and convert to markdown
        rsc_soup = BeautifulSoup(rsc_html, 'html.parser')

        # Remove footnote markers (sup tags) and images from body
        for tag in rsc_soup.find_all(['sup', 'img', 'figure']):
            tag.decompose()

        content = md(str(rsc_soup), heading_style="ATX", strip=['img'])
    else:
        content = ""

    # Clean up markdown artifacts
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    content = re.sub(r'^\s*\n', '\n', content, flags=re.MULTILINE)
    content = content.strip()

    if len(content.split()) < 50:
        return None  # Skip thin articles

    return {
        "title": title,
        "author": author,
        "url": url,
        "issue": issue_num,
        "content": content,
    }


def get_article_urls(issue_num: int) -> list[str]:
    """Get all article URLs from an issue page."""
    url = f"https://www.e-flux.com/journal/{issue_num}/"
    resp = fetch_page(url)
    if not resp:
        return []

    soup = BeautifulSoup(resp.content, 'html.parser')
    urls = []

    for link in soup.find_all('a', href=True):
        href = link['href']
        full_url = urljoin('https://www.e-flux.com', href)
        if f'/journal/{issue_num}/' in full_url and full_url.count('/') >= 6:
            path = urlparse(full_url).path.strip('/')
            parts = path.split('/')
            if len(parts) >= 3 and parts[0] == 'journal':
                if full_url not in urls:
                    urls.append(full_url)

    return urls


def save_article(article: dict, index: int) -> Path:
    """Save article as markdown with frontmatter."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Filename from index and title slug
    slug = re.sub(r'[^\w\s-]', '', article['title'].lower())
    slug = re.sub(r'[\s]+', '-', slug)[:80]
    filename = f"{index:04d}-{slug}.md"
    filepath = OUTPUT_DIR / filename

    frontmatter = f"""---
title: "{article['title'].replace('"', "'")}"
author: "{article['author'].replace('"', "'")}"
url: "{article['url']}"
issue: "{article['issue']}"
source: "e-flux Journal"
scraped: "{time.strftime('%Y-%m-%dT%H:%M:%S')}"
---"""

    content = f"""{frontmatter}

# {article['title']}

**Author:** {article['author']}
**Source:** e-flux Journal, Issue #{article['issue']}
**URL:** {article['url']}

---

{article['content']}
"""

    filepath.write_text(content, encoding="utf-8")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Re-scrape e-flux Journal (RSC-aware)")
    parser.add_argument("--issues", default="1-160",
                        help="Issue range to scrape (e.g., '140-145' or '141')")
    parser.add_argument("--test", action="store_true",
                        help="Test with single article")
    args = parser.parse_args()

    # Parse issue range
    if "-" in args.issues:
        start, end = args.issues.split("-")
        issue_range = range(int(start), int(end) + 1)
    else:
        issue_range = range(int(args.issues), int(args.issues) + 1)

    if args.test:
        print("TEST MODE: Fetching 1 article from issue 141...")
        urls = get_article_urls(141)
        if urls:
            url = urls[0]
            print(f"  Fetching: {url}")
            resp = fetch_page(url)
            if resp:
                article = extract_article_content(resp.text, url)
                if article:
                    path = save_article(article, 1)
                    word_count = len(article['content'].split())
                    print(f"  Saved: {path.name} ({word_count} words)")
                    print(f"  Title: {article['title']}")
                    print(f"  Author: {article['author']}")
                    print(f"  First 200 chars: {article['content'][:200]}")
                else:
                    print("  Failed to extract content")
        return

    # Full scrape
    print(f"Scraping e-flux Journal issues {args.issues}...")
    total_saved = 0
    total_failed = 0
    article_index = 0

    for issue_num in issue_range:
        print(f"\nIssue {issue_num}/{issue_range[-1]}:")
        urls = get_article_urls(issue_num)
        print(f"  Found {len(urls)} articles")

        for url in urls:
            article_index += 1
            resp = fetch_page(url)
            if not resp:
                total_failed += 1
                continue

            article = extract_article_content(resp.text, url)
            if article:
                path = save_article(article, article_index)
                word_count = len(article['content'].split())
                total_saved += 1
                print(f"  [{article_index}] {article['title'][:60]}... ({word_count} words)")
            else:
                total_failed += 1
                print(f"  [{article_index}] SKIP (thin): {url}")

    print(f"\n{'='*60}")
    print(f"Done. Saved: {total_saved} | Failed: {total_failed}")
    print(f"Output: {OUTPUT_DIR}")

    # Run quality gate
    print(f"\nRunning quality gate...")
    import subprocess
    subprocess.run([
        "python3", str(Path("~/Development/tools/kb_quality_gate.py").expanduser()),
        str(OUTPUT_DIR), "--fix"
    ])


if __name__ == "__main__":
    main()
