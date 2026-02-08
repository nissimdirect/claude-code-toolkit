#!/usr/bin/env python3
"""Atrium Knowledge Base Expansion Scraper

Scrapes critical theory, grant recipients, and art publications
to massively expand the Atrium advisor's knowledge base.

Target: 2,167 -> 8,000+ articles

Sources (by difficulty):
  STATIC HTML (Quick Wins):
    - UbuWeb Papers (~300 canonical theory texts)
    - Stanford Encyclopedia of Philosophy - Aesthetics (~40 entries)
    - Marxists.org Art Section (~100+ texts)
    - Bureau of Public Secrets / Situationist International (~60 texts)

  GRANT RECIPIENTS (Paginated HTML):
    - Creative Capital Awardees (1,062 artists, 22 pages)
    - Artadia Awards (~450 artists, 19 pages)
    - USA Fellows (1,060 fellows, 9 pages)

  ART PUBLICATIONS (WordPress/Static):
    - BOMB Magazine Interviews (1,200+ interviews)
    - Texte zur Kunst (1,000+ articles)
    - Momus (2,000+ articles)

Usage:
    python3 scrape_atrium.py all          # Scrape everything
    python3 scrape_atrium.py quick        # Static HTML only (fastest)
    python3 scrape_atrium.py grants       # Grant recipients only
    python3 scrape_atrium.py pubs         # Publications only
    python3 scrape_atrium.py <source>     # Single source

Code > Tokens: This runs independently, no Claude interaction needed.
"""

import os
import sys
import time
import json
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# === CONFIG ===
BASE_OUTPUT = Path.home() / "Development" / "art-criticism"
RATE_LIMIT = 1.5  # seconds between requests (be polite)
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) PopChaos Labs Art Research'
})


def fetch(url, retry=3):
    """Fetch URL with retry and rate limiting."""
    for attempt in range(retry):
        try:
            time.sleep(RATE_LIMIT)
            resp = SESSION.get(url, timeout=30)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            if attempt == retry - 1:
                print(f"    FAIL: {url} - {e}")
                return None
            time.sleep(2 ** attempt)
    return None


def slugify(text):
    """Create URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:60]


def save_article(output_dir, article_id, title, url, author, date, content, source):
    """Save article as markdown with frontmatter."""
    articles_dir = output_dir / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(title) if title != "Untitled" else f"article-{article_id}"
    filepath = articles_dir / f"{article_id:04d}-{slug}.md"

    md_content = f"""---
title: "{title.replace('"', "'")}"
author: "{author}"
date: "{date}"
url: "{url}"
source: "{source}"
scraped: "{datetime.now().isoformat()}"
---

# {title}

**Author:** {author}
**Date:** {date}
**Source:** {source}
**URL:** {url}

---

{content}
"""
    filepath.write_text(md_content, encoding='utf-8')
    return filepath


def save_index(output_dir, source_name, articles, errors):
    """Save INDEX.md and metadata.json."""
    # Metadata
    meta_dir = output_dir / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "source": source_name,
        "scraped_at": datetime.now().isoformat(),
        "total_articles": len(articles),
        "errors": len(errors),
        "articles": articles,
    }
    (meta_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    # INDEX.md
    index = f"""# {source_name} - Knowledge Base

**Scraped:** {datetime.now().strftime('%Y-%m-%d')}
**Total Articles:** {len(articles)}
**Errors:** {len(errors)}

## Articles

"""
    for a in sorted(articles, key=lambda x: x.get("date", ""), reverse=True):
        index += f"- [{a['title']}](articles/{a['file']}) - {a.get('author', '')} ({a.get('date', '')})\n"

    if errors:
        index += f"\n## Errors ({len(errors)})\n\n"
        for e in errors[:20]:
            index += f"- {e}\n"

    (output_dir / "INDEX.md").write_text(index)
    return metadata


# =====================================================================
# STATIC HTML SCRAPERS (Quick Wins)
# =====================================================================

def scrape_ubuweb():
    """Scrape UbuWeb Papers - ~300 canonical avant-garde theory texts."""
    print("\n=== UBUWEB PAPERS ===")
    output_dir = BASE_OUTPUT / "ubuweb-papers"
    base_url = "https://www.ubu.com/papers/"

    resp = fetch(base_url)
    if not resp:
        print("  Failed to fetch UbuWeb papers index")
        return 0

    soup = BeautifulSoup(resp.content, 'html.parser')
    articles = []
    errors = []

    # Find all links to papers
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.endswith('.html') and not href.startswith('http'):
            full_url = urljoin(base_url, href)
            text = a.get_text(strip=True)
            if text and full_url not in [l[0] for l in links]:
                links.append((full_url, text))

    print(f"  Found {len(links)} papers")

    for i, (url, link_text) in enumerate(links, 1):
        try:
            print(f"  [{i}/{len(links)}] {link_text[:60]}...")
            resp = fetch(url)
            if not resp:
                errors.append(f"Failed: {url}")
                continue

            page_soup = BeautifulSoup(resp.content, 'html.parser')

            # Title
            title = link_text
            h1 = page_soup.find('h1')
            if h1:
                title = h1.get_text(strip=True) or title

            # Author - try to extract from title or page
            author = "UbuWeb"
            # Many UbuWeb papers have author in format "Author Name - Title"
            if ' - ' in link_text:
                author = link_text.split(' - ')[0].strip()

            # Content
            body = page_soup.find('body')
            content = md(str(body)) if body else "Content extraction failed"

            filepath = save_article(output_dir, i, title, url, author, "", content, "UbuWeb Papers")
            articles.append({
                "id": i, "title": title, "url": url, "author": author,
                "date": "", "file": filepath.name,
            })
        except Exception as e:
            errors.append(f"Error on {url}: {e}")
            print(f"    SKIP: {e}")

    save_index(output_dir, "UbuWeb Papers", articles, errors)
    print(f"  DONE: {len(articles)} papers saved")
    return len(articles)


def scrape_stanford_aesthetics():
    """Scrape Stanford Encyclopedia of Philosophy - Aesthetics entries."""
    print("\n=== STANFORD ENCYCLOPEDIA - AESTHETICS ===")
    output_dir = BASE_OUTPUT / "stanford-aesthetics"

    # Key aesthetics and art theory entries
    entries = [
        "aesthetic-concept", "aesthetic-judgment", "aesthetics-18th-german",
        "aesthetics-existentialist", "art-definition", "art-ontology-history",
        "benjamin", "beauty", "chinese-aesthetics", "creativity",
        "dewey-aesthetics", "environmental-aesthetics", "feminist-aesthetics",
        "foucault", "hegel-aesthetics", "heidegger-aesthetics",
        "japanese-aesthetics", "kant-aesthetics", "medieval-aesthetics",
        "music", "nietzsche-aesthetics", "perception-episprob",
        "plato-aesthetics", "schopenhauer-aesthetics", "sculpture",
        "sublime", "taste", "tragedy", "value-intrinsic-extrinsic",
        "wittgenstein-aesthetics", "adorno", "aristotle-aesthetics",
        "critical-theory", "culture-cogsci", "imagination",
        "intentionality", "interpretation", "phenomenology",
        "philosophy-religion", "postmodernism",
    ]

    articles = []
    errors = []

    for i, entry in enumerate(entries, 1):
        url = f"https://plato.stanford.edu/entries/{entry}/"
        print(f"  [{i}/{len(entries)}] {entry}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        soup = BeautifulSoup(resp.content, 'html.parser')

        # Title
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else entry.replace('-', ' ').title()

        # Author from preamble
        author = "Stanford Encyclopedia"
        preamble = soup.find('div', id='preamble')
        if preamble:
            # Look for "First published..." or author info
            author_p = preamble.find_all('p')
            for p in author_p:
                text = p.get_text()
                if 'by ' in text.lower():
                    # Extract author name
                    match = re.search(r'by\s+(.+?)(?:\s+and\s+|\s*$)', text, re.IGNORECASE)
                    if match:
                        author = match.group(1).strip().rstrip('.')

        # Content - main article
        article_div = soup.find('div', id='main-text') or soup.find('div', id='article-content')
        if not article_div:
            article_div = soup.find('article')
        content = md(str(article_div)) if article_div else "Content extraction failed"

        filepath = save_article(output_dir, i, title, url, author, "", content, "Stanford Encyclopedia of Philosophy")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": "", "file": filepath.name,
        })

    save_index(output_dir, "Stanford Encyclopedia - Aesthetics", articles, errors)
    print(f"  DONE: {len(articles)} entries saved")
    return len(articles)


def scrape_marxists_art():
    """Scrape Marxists.org Art & Literature section."""
    print("\n=== MARXISTS.ORG - ART & AESTHETICS ===")
    output_dir = BASE_OUTPUT / "marxists-aesthetics"
    base_url = "https://www.marxists.org/subject/art/"

    resp = fetch(base_url)
    if not resp:
        print("  Failed to fetch Marxists.org art index")
        return 0

    soup = BeautifulSoup(resp.content, 'html.parser')
    articles = []
    errors = []

    # Collect all links from art section
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        if text and len(text) > 3:
            if href.startswith('http'):
                full_url = href
            else:
                full_url = urljoin(base_url, href)
            if 'marxists.org' in full_url and full_url not in [l[0] for l in links]:
                # Skip navigation and index links
                if '#' not in href and 'index.htm' not in href.lower():
                    links.append((full_url, text))

    print(f"  Found {len(links)} links")

    for i, (url, link_text) in enumerate(links, 1):
        if i > 200:  # Cap at 200 to be safe
            break
        print(f"  [{i}/{min(len(links), 200)}] {link_text[:60]}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        page_soup = BeautifulSoup(resp.content, 'html.parser')

        title = link_text
        h1 = page_soup.find('h1') or page_soup.find('h2')
        if h1:
            title = h1.get_text(strip=True) or title

        # Try to find author
        author = "Marxists.org"
        for tag in page_soup.find_all(['h2', 'h3', 'p']):
            text = tag.get_text(strip=True)
            if 'written by' in text.lower() or 'author:' in text.lower():
                author = text.replace('Written by', '').replace('Author:', '').strip()
                break

        body = page_soup.find('body')
        content = md(str(body)) if body else "Content extraction failed"

        # Skip if content is too short (likely a redirect or error page)
        if len(content) < 200:
            continue

        filepath = save_article(output_dir, i, title, url, author, "", content, "Marxists.org Aesthetics")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": "", "file": filepath.name,
        })

    save_index(output_dir, "Marxists.org - Art & Aesthetics", articles, errors)
    print(f"  DONE: {len(articles)} texts saved")
    return len(articles)


def scrape_situationist():
    """Scrape Situationist International texts from Bureau of Public Secrets."""
    print("\n=== SITUATIONIST INTERNATIONAL (Bureau of Public Secrets) ===")
    output_dir = BASE_OUTPUT / "situationist-international"
    base_url = "https://www.bopsecrets.org/SI/"

    resp = fetch(base_url)
    if not resp:
        print("  Failed to fetch Situationist index")
        return 0

    soup = BeautifulSoup(resp.content, 'html.parser')
    articles = []
    errors = []

    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        if text and len(text) > 3 and not href.startswith('http') and not href.startswith('#'):
            if href.endswith('.htm') or href.endswith('.html'):
                full_url = urljoin(base_url, href)
                if full_url not in [l[0] for l in links]:
                    links.append((full_url, text))

    # Also scrape the main bopsecrets anthology
    anthology_url = "https://www.bopsecrets.org/SI/anthology.htm"
    resp2 = fetch(anthology_url)
    if resp2:
        soup2 = BeautifulSoup(resp2.content, 'html.parser')
        for a in soup2.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if text and len(text) > 3 and not href.startswith('http') and not href.startswith('#'):
                if href.endswith('.htm') or href.endswith('.html'):
                    full_url = urljoin("https://www.bopsecrets.org/SI/", href)
                    if full_url not in [l[0] for l in links]:
                        links.append((full_url, text))

    print(f"  Found {len(links)} texts")

    for i, (url, link_text) in enumerate(links, 1):
        print(f"  [{i}/{len(links)}] {link_text[:60]}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        page_soup = BeautifulSoup(resp.content, 'html.parser')

        title = link_text
        for tag in page_soup.find_all(['h1', 'h2', 'h3']):
            t = tag.get_text(strip=True)
            if t and len(t) > 3:
                title = t
                break

        author = "Situationist International"

        body = page_soup.find('body')
        content = md(str(body)) if body else "Content extraction failed"

        if len(content) < 100:
            continue

        filepath = save_article(output_dir, i, title, url, author, "", content, "Situationist International")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": "", "file": filepath.name,
        })

    save_index(output_dir, "Situationist International", articles, errors)
    print(f"  DONE: {len(articles)} texts saved")
    return len(articles)


# =====================================================================
# GRANT RECIPIENT SCRAPERS
# =====================================================================

def scrape_creative_capital_awardees():
    """Scrape Creative Capital awardee index - 1,062 artists across 22 pages."""
    print("\n=== CREATIVE CAPITAL AWARDEES ===")
    output_dir = BASE_OUTPUT / "creative-capital-awardees"
    base_url = "https://creative-capital.org/awardee-index/"

    articles = []
    errors = []
    all_links = []

    # Paginate through awardee index
    for page in range(1, 25):
        page_url = f"{base_url}page/{page}/" if page > 1 else base_url
        print(f"  Page {page}...")

        resp = fetch(page_url)
        if not resp or resp.status_code == 404:
            break

        soup = BeautifulSoup(resp.content, 'html.parser')

        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if 'creative-capital.org/projects/' in href and text:
                full_url = urljoin("https://creative-capital.org", href)
                if full_url not in [l[0] for l in all_links]:
                    all_links.append((full_url, text))
                    found += 1

        if found == 0 and page > 1:
            break

    print(f"  Found {len(all_links)} awardee project pages")

    for i, (url, link_text) in enumerate(all_links, 1):
        print(f"  [{i}/{len(all_links)}] {link_text[:50]}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        soup = BeautifulSoup(resp.content, 'html.parser')

        title = link_text
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True) or title

        # Extract artist name and project details
        author = "Creative Capital"
        # Look for artist name in the page
        for cls in ['artist-name', 'awardee-name', 'project-artist']:
            elem = soup.find(class_=cls)
            if elem:
                author = elem.get_text(strip=True)
                break

        # Year
        date = ""
        for cls in ['award-year', 'project-year']:
            elem = soup.find(class_=cls)
            if elem:
                date = elem.get_text(strip=True)
                break

        # Content
        article = soup.find('article') or soup.find('main')
        content = md(str(article)) if article else ""
        if not content or len(content) < 50:
            # Fallback: largest div
            candidates = soup.find_all(['div', 'section'])
            best = max(candidates, key=lambda c: len(c.get_text(strip=True)), default=None)
            content = md(str(best)) if best else "Content extraction failed"

        filepath = save_article(output_dir, i, title, url, author, date, content, "Creative Capital Awardees")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": date, "file": filepath.name,
        })

    save_index(output_dir, "Creative Capital Awardees", articles, errors)
    print(f"  DONE: {len(articles)} awardee profiles saved")
    return len(articles)


def scrape_artadia():
    """Scrape Artadia award recipients - ~450 artists across 19 pages."""
    print("\n=== ARTADIA AWARDEES ===")
    output_dir = BASE_OUTPUT / "artadia-awardees"
    base_url = "https://artadia.org/artist/"

    articles = []
    errors = []
    all_links = []

    for page in range(1, 22):
        page_url = f"{base_url}page/{page}/" if page > 1 else base_url
        print(f"  Page {page}...")

        resp = fetch(page_url)
        if not resp or resp.status_code == 404:
            break

        soup = BeautifulSoup(resp.content, 'html.parser')

        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'artadia.org/artist/' in href and href != base_url:
                path = urlparse(href).path.strip('/')
                parts = path.split('/')
                if len(parts) == 2 and parts[0] == 'artist':
                    text = a.get_text(strip=True)
                    if href not in [l[0] for l in all_links]:
                        all_links.append((href, text or parts[1].replace('-', ' ').title()))
                        found += 1

        if found == 0 and page > 1:
            break

    print(f"  Found {len(all_links)} artist pages")

    for i, (url, link_text) in enumerate(all_links, 1):
        print(f"  [{i}/{len(all_links)}] {link_text[:50]}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        soup = BeautifulSoup(resp.content, 'html.parser')

        title = link_text
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True) or title

        author = title  # Artist name IS the title for grant recipients

        # Try to find year/city
        date = ""
        for tag in soup.find_all(['span', 'p', 'div']):
            text = tag.get_text(strip=True)
            match = re.search(r'(19|20)\d{2}', text)
            if match and len(text) < 100:
                date = match.group(0)
                break

        article = soup.find('article') or soup.find('main') or soup.find('div', class_='entry-content')
        content = md(str(article)) if article else "Content extraction failed"

        filepath = save_article(output_dir, i, title, url, author, date, content, "Artadia Awards")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": date, "file": filepath.name,
        })

    save_index(output_dir, "Artadia Awardees", articles, errors)
    print(f"  DONE: {len(articles)} artist profiles saved")
    return len(articles)


def scrape_usa_fellows():
    """Scrape United States Artists Fellows - 1,060 fellows."""
    print("\n=== USA FELLOWS ===")
    output_dir = BASE_OUTPUT / "usa-fellows"
    base_url = "https://www.unitedstatesartists.org/artists"

    articles = []
    errors = []

    # USA Fellows site - try to get artist listing
    resp = fetch(base_url)
    if not resp:
        print("  Failed to fetch USA Fellows page")
        return 0

    soup = BeautifulSoup(resp.content, 'html.parser')

    # Find artist profile links
    all_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        if '/artists/' in href and text and len(text) > 2:
            full_url = urljoin("https://www.unitedstatesartists.org", href)
            path = urlparse(full_url).path.strip('/')
            parts = path.split('/')
            if len(parts) == 2 and parts[0] == 'artists':
                if full_url not in [l[0] for l in all_links]:
                    all_links.append((full_url, text))

    # Try pagination if initial page has limited results
    for page in range(2, 15):
        page_url = f"{base_url}?page={page}"
        resp = fetch(page_url)
        if not resp:
            break

        soup = BeautifulSoup(resp.content, 'html.parser')
        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if '/artists/' in href and text and len(text) > 2:
                full_url = urljoin("https://www.unitedstatesartists.org", href)
                path = urlparse(full_url).path.strip('/')
                parts = path.split('/')
                if len(parts) == 2 and parts[0] == 'artists':
                    if full_url not in [l[0] for l in all_links]:
                        all_links.append((full_url, text))
                        found += 1

        if found == 0:
            break

    print(f"  Found {len(all_links)} fellow pages")

    for i, (url, link_text) in enumerate(all_links, 1):
        print(f"  [{i}/{len(all_links)}] {link_text[:50]}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        soup = BeautifulSoup(resp.content, 'html.parser')

        title = link_text
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True) or title

        author = title
        date = ""

        article = soup.find('article') or soup.find('main')
        content = md(str(article)) if article else "Content extraction failed"

        filepath = save_article(output_dir, i, title, url, author, date, content, "USA Fellows")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": date, "file": filepath.name,
        })

    save_index(output_dir, "United States Artists Fellows", articles, errors)
    print(f"  DONE: {len(articles)} fellow profiles saved")
    return len(articles)


# =====================================================================
# ART PUBLICATION SCRAPERS
# =====================================================================

def scrape_bomb_magazine():
    """Scrape BOMB Magazine interviews - 1,200+ artist-to-artist conversations."""
    print("\n=== BOMB MAGAZINE INTERVIEWS ===")
    output_dir = BASE_OUTPUT / "bomb-magazine"
    base_url = "https://bombmagazine.org"

    articles = []
    errors = []
    all_links = []

    # Use BOMB's sitemap (21 pages) to discover all article URLs
    for sitemap_page in range(1, 25):
        sitemap_url = f"{base_url}/sitemaps-1-section-articles-1-sitemap-p{sitemap_page}.xml"
        print(f"  Sitemap page {sitemap_page}...")

        resp = fetch(sitemap_url)
        if not resp or resp.status_code == 404:
            break

        # Parse sitemap XML
        soup = BeautifulSoup(resp.content, 'xml')
        if not soup:
            soup = BeautifulSoup(resp.content, 'html.parser')

        found = 0
        for loc in soup.find_all('loc'):
            url = loc.get_text(strip=True)
            if '/articles/' in url and url != f"{base_url}/articles":
                path = urlparse(url).path.strip('/')
                parts = path.split('/')
                if len(parts) >= 4 and parts[0] == 'articles':
                    title = parts[-1].replace('-', ' ').title()
                    if url not in [l[0] for l in all_links]:
                        all_links.append((url, title))
                        found += 1

        if found == 0 and sitemap_page > 1:
            break

    print(f"  Found {len(all_links)} articles/interviews from sitemap")

    for i, (url, link_text) in enumerate(all_links, 1):
        if i > 1500:  # Cap
            break
        print(f"  [{i}/{min(len(all_links), 1500)}] {link_text[:50]}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        soup = BeautifulSoup(resp.content, 'html.parser')

        title = link_text
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True) or title

        # Author
        author = "BOMB Magazine"
        author_elem = soup.find(class_='author') or soup.find('a', rel='author')
        if author_elem:
            author = author_elem.get_text(strip=True)

        # Date from URL pattern /articles/YYYY/MM/DD/
        date = ""
        path_parts = urlparse(url).path.strip('/').split('/')
        if len(path_parts) >= 4:
            try:
                date = f"{path_parts[1]}-{path_parts[2]}-{path_parts[3]}"
            except (IndexError, ValueError):
                pass

        # Content - BOMB uses div.articleContent, not <article>
        article = (soup.find(class_='articleContent')
                   or soup.find(class_='article-content')
                   or soup.find(class_='entry-content')
                   or soup.find('article')
                   or soup.find('main'))
        content = md(str(article)) if article else ""

        if not content or len(content) < 100:
            # Fallback: largest content div
            candidates = soup.find_all('div', class_=True)
            best = max(candidates, key=lambda c: len(c.get_text(strip=True)), default=None)
            if best and len(best.get_text(strip=True)) > 200:
                content = md(str(best))

        if len(content) < 100:
            continue

        filepath = save_article(output_dir, i, title, url, author, date, content, "BOMB Magazine")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": date, "file": filepath.name,
        })

    save_index(output_dir, "BOMB Magazine", articles, errors)
    print(f"  DONE: {len(articles)} interviews/articles saved")
    return len(articles)


def scrape_texte_zur_kunst():
    """Scrape Texte zur Kunst - top-tier German/English critical theory journal."""
    print("\n=== TEXTE ZUR KUNST ===")
    output_dir = BASE_OUTPUT / "texte-zur-kunst"
    base_url = "https://www.textezurkunst.de/en/articles/"

    articles = []
    errors = []
    all_links = []

    # Try year-based archives
    for year in range(2024, 1990, -1):
        page_url = f"{base_url}?year={year}"
        print(f"  Year {year}...")

        resp = fetch(page_url)
        if not resp:
            continue

        soup = BeautifulSoup(resp.content, 'html.parser')

        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if '/en/articles/' in href and text and len(text) > 5:
                full_url = urljoin("https://www.textezurkunst.de", href)
                if full_url not in [l[0] for l in all_links] and full_url != base_url:
                    all_links.append((full_url, text))

    # Also try direct pagination
    for page in range(1, 60):
        page_url = f"{base_url}?page={page}"
        resp = fetch(page_url)
        if not resp:
            break

        soup = BeautifulSoup(resp.content, 'html.parser')
        found = 0
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if '/en/articles/' in href and text and len(text) > 5:
                full_url = urljoin("https://www.textezurkunst.de", href)
                if full_url not in [l[0] for l in all_links] and full_url != base_url:
                    all_links.append((full_url, text))
                    found += 1
        if found == 0 and page > 5:
            break

    print(f"  Found {len(all_links)} articles")

    for i, (url, link_text) in enumerate(all_links, 1):
        print(f"  [{i}/{len(all_links)}] {link_text[:50]}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        soup = BeautifulSoup(resp.content, 'html.parser')

        title = link_text
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True) or title

        author = "Texte zur Kunst"
        author_elem = soup.find(class_='author') or soup.find('a', rel='author')
        if author_elem:
            author = author_elem.get_text(strip=True)

        date = ""
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.get_text(strip=True))[:10]

        article = soup.find('article') or soup.find('main')
        content = md(str(article)) if article else "Content extraction failed"

        if len(content) < 100:
            continue

        filepath = save_article(output_dir, i, title, url, author, date, content, "Texte zur Kunst")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": date, "file": filepath.name,
        })

    save_index(output_dir, "Texte zur Kunst", articles, errors)
    print(f"  DONE: {len(articles)} articles saved")
    return len(articles)


def scrape_momus():
    """Scrape Momus art criticism - ~2,000 articles, WordPress."""
    print("\n=== MOMUS ===")
    output_dir = BASE_OUTPUT / "momus"
    base_url = "https://momus.ca"

    articles = []
    errors = []
    all_links = []

    # WordPress pagination - use category/writing archive
    archive_base = f"{base_url}/category/writing"
    page = 1
    while page <= 150:
        page_url = f"{archive_base}/page/{page}/" if page > 1 else archive_base
        print(f"  Page {page}...")

        resp = fetch(page_url)
        if not resp or resp.status_code == 404:
            break

        soup = BeautifulSoup(resp.content, 'html.parser')
        found = 0

        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if 'momus.ca/' in href and text and len(text) > 10:
                path = urlparse(href).path.strip('/')
                # WordPress date URLs: YYYY/MM/DD/slug or just /slug
                if path and '/page/' not in path and '/category/' not in path \
                   and '/tag/' not in path and '/author/' not in path \
                   and path not in ['', 'about', 'contact', 'subscribe']:
                    if href not in [l[0] for l in all_links]:
                        all_links.append((href, text))
                        found += 1

        if found == 0 and page > 3:
            break
        page += 1

    print(f"  Found {len(all_links)} articles")

    for i, (url, link_text) in enumerate(all_links, 1):
        if i > 2500:  # Cap
            break
        print(f"  [{i}/{min(len(all_links), 2500)}] {link_text[:50]}...")

        resp = fetch(url)
        if not resp:
            errors.append(f"Failed: {url}")
            continue

        soup = BeautifulSoup(resp.content, 'html.parser')

        title = link_text
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True) or title

        author = "Momus"
        author_elem = soup.find(class_='author') or soup.find('a', rel='author')
        if author_elem:
            author = author_elem.get_text(strip=True)

        date = ""
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.get_text(strip=True))[:10]

        # WordPress entry-content
        content_div = soup.find(class_='entry-content') or soup.find('article') or soup.find('main')
        content = md(str(content_div)) if content_div else "Content extraction failed"

        if len(content) < 200:
            continue

        filepath = save_article(output_dir, i, title, url, author, date, content, "Momus")
        articles.append({
            "id": i, "title": title, "url": url, "author": author,
            "date": date, "file": filepath.name,
        })

    save_index(output_dir, "Momus", articles, errors)
    print(f"  DONE: {len(articles)} articles saved")
    return len(articles)


# =====================================================================
# MAIN
# =====================================================================

SOURCES = {
    # Quick wins (static HTML)
    "ubuweb": scrape_ubuweb,
    "stanford": scrape_stanford_aesthetics,
    "marxists": scrape_marxists_art,
    "situationist": scrape_situationist,
    # Grant recipients
    "creative-capital": scrape_creative_capital_awardees,
    "artadia": scrape_artadia,
    "usa-fellows": scrape_usa_fellows,
    # Publications
    "bomb": scrape_bomb_magazine,
    "texte": scrape_texte_zur_kunst,
    "momus": scrape_momus,
}

GROUPS = {
    "quick": ["ubuweb", "stanford", "marxists", "situationist"],
    "grants": ["creative-capital", "artadia", "usa-fellows"],
    "pubs": ["bomb", "texte", "momus"],
    "all": list(SOURCES.keys()),
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scrape_atrium.py <source|group>")
        print(f"\nSources: {', '.join(SOURCES.keys())}")
        print(f"Groups:  {', '.join(GROUPS.keys())}")
        sys.exit(1)

    target = sys.argv[1]
    start = time.time()

    if target in GROUPS:
        sources = GROUPS[target]
    elif target in SOURCES:
        sources = [target]
    else:
        print(f"Unknown source: {target}")
        print(f"Available: {', '.join(list(SOURCES.keys()) + list(GROUPS.keys()))}")
        sys.exit(1)

    total = 0
    results = {}

    print(f"\n{'='*60}")
    print(f"ATRIUM KB EXPANSION - Scraping {len(sources)} source(s)")
    print(f"{'='*60}")

    for source in sources:
        try:
            count = SOURCES[source]()
            results[source] = count
            total += count
        except Exception as e:
            print(f"\n  ERROR in {source}: {e}")
            results[source] = 0

    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"{'='*60}")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Total new articles: {total}")
    print()
    for source, count in results.items():
        print(f"  {source:25s} {count:>6,}")
    print()
    print(f"Output: {BASE_OUTPUT}")
    print(f"\nNext: Update kb_loader.py to include new sources in Atrium")


if __name__ == "__main__":
    main()
