#!/usr/bin/env python3
"""
Data Analyst KB Scraper — scrapes 32 sources for the /data-analyst skill.

Usage:
    python3 data_analyst_scraper.py --source flowingdata
    python3 data_analyst_scraper.py --source pudding
    python3 data_analyst_scraper.py --source all-priority-1
    python3 data_analyst_scraper.py --source all
    python3 data_analyst_scraper.py --list

Sources (by priority):
    Priority 1 (Frontier gold):    flowingdata, pudding, data-sketches
    Priority 2 (Stats depth):      andrew-gelman, statistical-thinking, simply-statistics
    Priority 3 (Practical):        storytelling-with-data, observable-blog, plotly-blog,
                                   nightingale, info-is-beautiful
    Priority 4 (Enterprise+Acad):  datawrapper, dbt-blog, metabase,
                                   distill-pub, variance-explained, kozyrkov-decision
    Priority 5 (Textbooks+Minds):  wilke-dataviz, data-to-viz, seeing-theory,
                                   r4ds, python-ds-handbook, think-bayes,
                                   andy-kirk, alberto-cairo
    Priority 6 (Advanced Tech):    fpp3, causal-mixtape, the-effect,
                                   feat-engineering, lilian-weng, colah,
                                   modern-stats-bio
"""

import logging
import os
import sys
import time
import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger = logging.getLogger(__name__)

try:
    from content_sanitizer import sanitize_content as _sanitize

    HAS_SANITIZER = True
except ImportError:
    HAS_SANITIZER = False

KB_BASE = Path("~/Development/knowledge-bases/data-analyst").expanduser()

# Data viz / stats concepts for auto-tagging
DATAVIZ_CONCEPTS = [
    # Perception Science
    "preattentive",
    "Gestalt",
    "visual variable",
    "Bertin",
    "Cleveland",
    "data-ink ratio",
    "Tufte",
    "small multiples",
    "sparkline",
    # Chart Types
    "scatter plot",
    "bar chart",
    "line chart",
    "histogram",
    "box plot",
    "violin plot",
    "heatmap",
    "treemap",
    "sankey",
    "chord diagram",
    "beeswarm",
    "ridgeline",
    "bump chart",
    "slope chart",
    "waffle chart",
    "choropleth",
    "hexbin",
    "voronoi",
    "sunburst",
    "dendrogram",
    # Statistics
    "p-value",
    "confidence interval",
    "effect size",
    "regression",
    "correlation",
    "ANOVA",
    "chi-squared",
    "bootstrap",
    "Bayesian",
    "hypothesis testing",
    "null hypothesis",
    "standard deviation",
    "normal distribution",
    "outlier",
    "time series",
    "ARIMA",
    "PCA",
    "t-SNE",
    "UMAP",
    "clustering",
    "K-means",
    "DBSCAN",
    # Tools
    "D3.js",
    "Observable",
    "matplotlib",
    "plotly",
    "ggplot2",
    "seaborn",
    "Vega-Lite",
    "Altair",
    "pandas",
    "R",
    # Encoding
    "color palette",
    "colorblind",
    "sequential",
    "diverging",
    "categorical",
    "perceptual",
    "encoding",
    "annotation",
    # EDA
    "EDA",
    "exploratory data analysis",
    "missing data",
    "imputation",
    "feature engineering",
    "dimensionality reduction",
]
DATAVIZ_CONCEPTS.sort(key=len, reverse=True)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:60]


def auto_tag(text: str) -> str:
    for concept in DATAVIZ_CONCEPTS:
        pattern = re.compile(r"\b(" + re.escape(concept) + r")\b", re.IGNORECASE)

        def replace_if_not_tagged(match, _text=text):
            start = match.start()
            before = _text[max(0, start - 3) : start]
            after = _text[start + len(match.group(0)) : start + len(match.group(0)) + 3]
            if "[[" in before or "]]" in after:
                return match.group(0)
            if before.endswith("[") or "](" in after:
                return match.group(0)
            return f"[[{match.group(0)}]]"

        text = pattern.sub(replace_if_not_tagged, text)
    return text


def save_article(output_dir: Path, idx: int, article: dict) -> Path | None:
    slug = slugify(article["title"])
    filename = f"{idx:04d}-{slug}.md"
    filepath = output_dir / "articles" / filename

    content_raw = article.get("content", "")
    if HAS_SANITIZER:
        sanitized, report = _sanitize(content_raw)
        if report.blocked:
            return None
        if report.items_removed > 0:
            content_raw = sanitized

    tagged = auto_tag(content_raw)

    md_content = f"""# {article["title"]}

**Author:** {article.get("author", "Unknown")}
**Date:** {article.get("date", "Unknown")}
**Source:** {article.get("source", "Unknown")}
**URL:** {article.get("url", "")}

---

{tagged}
"""
    filepath.write_text(md_content, encoding="utf-8")
    return filepath


def save_metadata(
    output_dir: Path, source_name: str, base_url: str, articles: list, errors: list
):
    meta_dir = output_dir / "metadata"
    meta_dir.mkdir(exist_ok=True)
    metadata = {
        "source": source_name,
        "base_url": base_url,
        "scraped_at": datetime.now().isoformat(),
        "total_articles": len(articles),
        "errors": len(errors),
        "articles": [
            {"title": a["title"], "url": a.get("url", ""), "date": a.get("date", "")}
            for a in articles
        ],
    }
    (meta_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    index = f"# {source_name} — Data Analyst KB\n\n"
    index += f"**Scraped:** {datetime.now().strftime('%Y-%m-%d')}\n"
    index += f"**Articles:** {len(articles)}\n**Errors:** {len(errors)}\n\n"
    for a in articles:
        index += f"- {a['title']} ({a.get('date', '?')})\n"
    (output_dir / "INDEX.md").write_text(index)


class BaseScraper:
    def __init__(self, source_name: str, base_url: str, rate_limit: float = 1.5):
        self.source_name = source_name
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.output_dir = KB_BASE / source_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "articles").mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        self.articles = []
        self.errors = []

    def fetch(self, url: str, retry: int = 3) -> requests.Response | None:
        for attempt in range(retry):
            try:
                time.sleep(self.rate_limit)
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                if attempt == retry - 1:
                    self.errors.append({"url": url, "error": str(e)})
                    return None
                time.sleep(2**attempt)
        return None

    def get_article_urls(self) -> list[str]:
        raise NotImplementedError

    def parse_article(self, url: str) -> dict | None:
        raise NotImplementedError

    def run(self):
        print(f"[{self.source_name}] Starting scrape: {self.base_url}")
        print(f"[{self.source_name}] Output: {self.output_dir}")

        # Check for existing articles to enable resume
        existing = list((self.output_dir / "articles").glob("*.md"))
        existing_count = len(existing)
        if existing_count > 0:
            print(
                f"[{self.source_name}] Found {existing_count} existing articles — will skip duplicates"
            )

        existing_urls = set()
        meta_file = self.output_dir / "metadata" / "metadata.json"
        if meta_file.exists():
            try:
                prev = json.loads(meta_file.read_text())
                existing_urls = {
                    a["url"] for a in prev.get("articles", []) if a.get("url")
                }
            except Exception:
                pass

        # Priority: urls.txt (pre-populated from sitemaps) > get_article_urls() (slow crawl)
        urls_file = self.output_dir / "urls.txt"
        if urls_file.exists():
            urls = [
                line.strip()
                for line in urls_file.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            ]
            print(f"[{self.source_name}] Loaded {len(urls)} URLs from urls.txt")
        else:
            urls = self.get_article_urls()
        print(
            f"[{self.source_name}] Found {len(urls)} URLs, {len(existing_urls)} already scraped"
        )

        new_urls = [u for u in urls if u not in existing_urls]
        print(f"[{self.source_name}] Scraping {len(new_urls)} new articles...")

        idx = existing_count
        for i, url in enumerate(new_urls, 1):
            print(f"  [{i}/{len(new_urls)}] {url[:80]}...")
            article = self.parse_article(url)
            if article:
                idx += 1
                article["source"] = self.source_name
                path = save_article(self.output_dir, idx, article)
                if path:
                    self.articles.append(article)

        save_metadata(
            self.output_dir, self.source_name, self.base_url, self.articles, self.errors
        )
        print(
            f"[{self.source_name}] Done: {len(self.articles)} new, {len(self.errors)} errors"
        )
        return len(self.articles)


# ── Source-Specific Scrapers ──────────────────────────────────────


class FlowingDataScraper(BaseScraper):
    """Nathan Yau's FlowingData — practical viz patterns."""

    def __init__(self):
        super().__init__("flowingdata", "https://flowingdata.com", rate_limit=1.0)

    def get_article_urls(self) -> list[str]:
        urls = []
        # FlowingData archives by year/month (slow fallback — urls.txt from sitemap preferred)
        for year in range(2007, 2027):
            for month in range(1, 13):
                archive_url = f"https://flowingdata.com/{year}/{month:02d}/"
                resp = self.fetch(archive_url)
                if not resp:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.select('h2.entry-title a, h2 a[href*="flowingdata.com"]'):
                    href = a.get("href", "")
                    if href and "flowingdata.com" in href and href not in urls:
                        urls.append(href)
                if not soup.select('h2.entry-title a, h2 a[href*="flowingdata.com"]'):
                    # No articles this month, if future year stop
                    if year >= 2026:
                        break
            if year >= 2026 and month <= 3:
                break
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1.entry-title, h1, .post-title")
        title = (
            title_el.get_text(strip=True) if title_el else urlparse(url).path.strip("/")
        )
        date_el = soup.select_one("time, .entry-date, .post-date")
        date = date_el.get("datetime", date_el.get_text(strip=True)) if date_el else ""
        # Extract date from URL pattern /YYYY/MM/DD/
        if not date:
            import re as _re

            date_match = _re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
            if date_match:
                date = (
                    f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                )
        content_el = soup.select_one(
            "div.entry, .entry-content, .post-content, article"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": date[:10],
            "url": url,
            "content": content,
            "author": "Nathan Yau",
        }


class PuddingScraper(BaseScraper):
    """The Pudding — visual essays that invent new viz forms."""

    def __init__(self):
        super().__init__("pudding", "https://pudding.cool", rate_limit=2.0)

    def get_article_urls(self) -> list[str]:
        urls = []
        resp = self.fetch("https://pudding.cool/archives/")
        if not resp:
            # Fallback: try main page
            resp = self.fetch("https://pudding.cool/")
        if not resp:
            return urls
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            # Pudding articles are at /YYYY/MM/slug/
            if re.match(r"/?20\d{2}/\d{2}/[\w-]+", href):
                full = urljoin("https://pudding.cool/", href)
                if full not in urls:
                    urls.append(full)
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, title, .headline")
        title = (
            title_el.get_text(strip=True) if title_el else urlparse(url).path.strip("/")
        )
        # Extract date from URL pattern /YYYY/MM/
        date_match = re.search(r"/(\d{4})/(\d{2})/", url)
        date = f"{date_match.group(1)}-{date_match.group(2)}" if date_match else ""
        author_el = soup.select_one('.byline, .author, [class*="author"]')
        author = author_el.get_text(strip=True) if author_el else "The Pudding"
        # Get all text content — Pudding articles are scrollytelling, heavy on visuals
        content_el = soup.select_one("article, main, .story, body")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 200:
            return None
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": author,
        }


class DataSketchesScraper(BaseScraper):
    """Nadieh Bremer & Shirley Wu — 24 frontier case studies."""

    def __init__(self):
        super().__init__("data-sketches", "https://www.datasketch.es", rate_limit=2.0)

    def get_article_urls(self) -> list[str]:
        urls = []
        resp = self.fetch("https://www.datasketch.es/")
        if not resp:
            return urls
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if (
                href
                and "/project/" in href
                or "/january" in href
                or "/february" in href
                or "/march" in href
                or "/april" in href
                or "/may" in href
                or "/june" in href
                or "/july" in href
                or "/august" in href
                or "/september" in href
                or "/october" in href
                or "/november" in href
                or "/december" in href
            ):
                full = urljoin("https://www.datasketch.es/", href)
                if full not in urls and "datasketch" in full:
                    urls.append(full)
        # Also try known month pages
        months = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]
        for m in months:
            for person in ["nadieh", "shirley"]:
                candidate = f"https://www.datasketch.es/{m}/{person}"
                if candidate not in urls:
                    urls.append(candidate)
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, h2, title")
        title = (
            title_el.get_text(strip=True) if title_el else urlparse(url).path.strip("/")
        )
        # Determine author from URL
        author = (
            "Nadieh Bremer"
            if "nadieh" in url.lower()
            else "Shirley Wu"
            if "shirley" in url.lower()
            else "Data Sketches"
        )
        content_el = soup.select_one("article, main, .content, body")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "",
            "url": url,
            "content": content,
            "author": author,
        }


class NightingaleScraper(BaseScraper):
    """Nightingale — Data Visualization Society journal."""

    def __init__(self):
        super().__init__("nightingale", "https://nightingaledvs.com", rate_limit=2.0)

    def get_article_urls(self) -> list[str]:
        urls = []
        page = 1
        while page <= 50:
            resp = self.fetch(f"https://nightingaledvs.com/page/{page}/")
            if not resp:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            found = False
            for a in soup.select(
                "h2 a[href], h3 a[href], .post-title a[href], article a[href]"
            ):
                href = a.get("href", "")
                if (
                    href
                    and "nightingaledvs.com" in href
                    and "/page/" not in href
                    and href not in urls
                ):
                    urls.append(href)
                    found = True
            if not found:
                break
            page += 1
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1.entry-title, h1, .post-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        date_el = soup.select_one("time, .entry-date, .post-date")
        date = (
            date_el.get("datetime", date_el.get_text(strip=True))[:10]
            if date_el
            else ""
        )
        author_el = soup.select_one('.author, .byline, [rel="author"]')
        author = author_el.get_text(strip=True) if author_el else "DVS"
        content_el = soup.select_one(".entry-content, .post-content, article")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 200:
            return None
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": author,
        }


class StorytellingWithDataScraper(BaseScraper):
    """Cole Nussbaumer Knaflic — storytelling with data blog."""

    def __init__(self):
        super().__init__(
            "storytelling-with-data",
            "https://www.storytellingwithdata.com/blog",
            rate_limit=2.0,
        )

    def get_article_urls(self) -> list[str]:
        urls = []
        # SWD uses Squarespace — paginated blog (urls.txt from sitemap preferred)
        resp = self.fetch("https://www.storytellingwithdata.com/blog")
        if not resp:
            return urls
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select('a[href*="/blog/"]'):
            href = a.get("href", "")
            if href and "/blog/" in href and href != "/blog/" and href != "/blog":
                full = urljoin("https://www.storytellingwithdata.com", href)
                if full not in urls and "storytellingwithdata.com" in full:
                    urls.append(full)
        # Try offset pagination
        for offset in range(1, 30):
            resp = self.fetch(
                f"https://www.storytellingwithdata.com/blog?offset={offset * 10}"
            )
            if not resp:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            found = False
            for a in soup.select('a[href*="/blog/"]'):
                href = a.get("href", "")
                if href and "/blog/" in href and href != "/blog/" and href != "/blog":
                    full = urljoin("https://www.storytellingwithdata.com", href)
                    if full not in urls:
                        urls.append(full)
                        found = True
            if not found:
                break
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .blog-item-title, title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        date_el = soup.select_one("time, .date, .blog-date")
        date = date_el.get_text(strip=True)[:10] if date_el else ""
        content_el = soup.select_one(
            ".blog-item-content, .entry-content, article, .sqs-block-content"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 200:
            return None
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": "Cole Nussbaumer Knaflic",
        }


class AndrewGelmanScraper(BaseScraper):
    """Andrew Gelman's Statistical Modeling blog."""

    def __init__(self):
        super().__init__(
            "andrew-gelman", "https://statmodeling.stat.columbia.edu", rate_limit=2.0
        )

    def get_article_urls(self) -> list[str]:
        urls = []
        page = 1
        while page <= 100:
            resp = self.fetch(f"https://statmodeling.stat.columbia.edu/page/{page}/")
            if not resp:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            found = False
            for a in soup.select("h2.entry-title a, h1.entry-title a, .post-title a"):
                href = a.get("href", "")
                if href and href not in urls:
                    urls.append(href)
                    found = True
            if not found:
                break
            page += 1
            if len(urls) >= 1000:
                break
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1.entry-title, h1, .post-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        date_el = soup.select_one("time, .entry-date, .post-date")
        date = (
            date_el.get("datetime", date_el.get_text(strip=True))[:10]
            if date_el
            else ""
        )
        author_el = soup.select_one(".author, .byline")
        author = author_el.get_text(strip=True) if author_el else "Andrew Gelman"
        content_el = soup.select_one(".entry-content, .post-content")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": author,
        }


class SimplyStatisticsScraper(BaseScraper):
    """Simply Statistics — Leek, Peng, Irizarry."""

    def __init__(self):
        super().__init__(
            "simply-statistics", "https://simplystatistics.org", rate_limit=2.0
        )

    def get_article_urls(self) -> list[str]:
        urls = []
        # Simply Stats uses Hugo — posts at /posts/ or /YYYY/MM/DD/
        resp = self.fetch("https://simplystatistics.org/posts/")
        if resp:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if re.match(r"/?posts?/\d{4}", href) or re.match(
                    r"/?\d{4}/\d{2}/\d{2}/", href
                ):
                    full = urljoin("https://simplystatistics.org/", href)
                    if full not in urls:
                        urls.append(full)
        # Try paginated archives
        for page in range(1, 20):
            resp = self.fetch(f"https://simplystatistics.org/page/{page}/")
            if not resp:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            found = False
            for a in soup.select(
                "h2 a[href], h1 a[href], .post-title a, article a[href]"
            ):
                href = a.get("href", "")
                if href and "/page/" not in href and href not in urls:
                    full = urljoin("https://simplystatistics.org/", href)
                    if "simplystatistics" in full and full not in urls:
                        urls.append(full)
                        found = True
            if not found:
                break
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .post-title, title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or "Simply Statistics" == title:
            return None
        date_el = soup.select_one("time, .date, .post-date")
        date = (
            date_el.get("datetime", date_el.get_text(strip=True))[:10]
            if date_el
            else ""
        )
        author_el = soup.select_one(".author, .byline")
        author = author_el.get_text(strip=True) if author_el else "Simply Statistics"
        content_el = soup.select_one(
            ".d-article, .post-content, .entry-content, article, .content"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 200:
            return None
        # Extract date from URL pattern /posts/YYYY-MM-DD-
        if not date:
            import re as _re

            date_match = _re.search(r"/posts/(\d{4}-\d{2}-\d{2})", url)
            if date_match:
                date = date_match.group(1)
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": author,
        }


class StatisticalThinkingScraper(BaseScraper):
    """Frank Harrell's Statistical Thinking blog."""

    def __init__(self):
        super().__init__(
            "statistical-thinking", "https://www.fharrell.com", rate_limit=2.0
        )

    def get_article_urls(self) -> list[str]:
        urls = []
        resp = self.fetch("https://www.fharrell.com/")
        if not resp:
            return urls
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select('a[href*="/post/"]'):
            href = a.get("href", "")
            full = urljoin("https://www.fharrell.com/", href)
            if full not in urls:
                urls.append(full)
        # Try sitemap
        resp = self.fetch("https://www.fharrell.com/sitemap.xml")
        if resp:
            sitemap_soup = BeautifulSoup(resp.text, "xml")
            for loc in sitemap_soup.select("loc"):
                url = loc.get_text(strip=True)
                if "/post/" in url and url not in urls:
                    urls.append(url)
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .post-title, title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        date_el = soup.select_one("time, .date")
        date = (
            date_el.get("datetime", date_el.get_text(strip=True))[:10]
            if date_el
            else ""
        )
        content_el = soup.select_one(
            ".post-content, .entry-content, article, .content, main"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 200:
            return None
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": "Frank Harrell",
        }


class ObservableBlogScraper(BaseScraper):
    """Observable blog — D3, notebooks, computational viz."""

    def __init__(self):
        super().__init__(
            "observable-blog", "https://observablehq.com/blog", rate_limit=2.0
        )

    def get_article_urls(self) -> list[str]:
        urls = []
        resp = self.fetch("https://observablehq.com/blog")
        if not resp:
            return urls
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select('a[href*="/blog/"]'):
            href = a.get("href", "")
            if href and href != "/blog/" and href != "/blog":
                full = urljoin("https://observablehq.com", href)
                if full not in urls and "observablehq.com" in full:
                    urls.append(full)
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one(
            ".article-body, article, main, .post-content, .content"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 200:
            return None
        return {
            "title": title,
            "date": "",
            "url": url,
            "content": content,
            "author": "Observable",
        }


class PlotlyBlogScraper(BaseScraper):
    """Plotly blog — interactive charting tutorials."""

    def __init__(self):
        super().__init__("plotly-blog", "https://plotly.com/blog/", rate_limit=2.0)

    def get_article_urls(self) -> list[str]:
        urls = []
        resp = self.fetch("https://plotly.com/blog/")
        if not resp:
            return urls
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select('a[href*="/blog/"]'):
            href = a.get("href", "")
            if href and href != "/blog/" and "/blog/tag/" not in href:
                full = urljoin("https://plotly.com", href)
                if full not in urls:
                    urls.append(full)
        # Try pages
        for page in range(2, 20):
            resp = self.fetch(f"https://plotly.com/blog/page/{page}/")
            if not resp:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            found = False
            for a in soup.select('a[href*="/blog/"]'):
                href = a.get("href", "")
                if (
                    href
                    and href != "/blog/"
                    and "/blog/tag/" not in href
                    and "/blog/page/" not in href
                ):
                    full = urljoin("https://plotly.com", href)
                    if full not in urls:
                        urls.append(full)
                        found = True
            if not found:
                break
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one("article, .post-content, .entry-content, main")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 200:
            return None
        return {
            "title": title,
            "date": "",
            "url": url,
            "content": content,
            "author": "Plotly",
        }


class InfoIsBeautifulScraper(BaseScraper):
    """Information is Beautiful — award-winning viz analysis."""

    def __init__(self):
        super().__init__(
            "info-is-beautiful", "https://informationisbeautiful.net", rate_limit=2.0
        )

    def get_article_urls(self) -> list[str]:
        urls = []
        resp = self.fetch("https://informationisbeautiful.net/blog/")
        if not resp:
            return urls
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("h2 a[href], .post-title a[href], article a[href]"):
            href = a.get("href", "")
            if href and "informationisbeautiful.net" in href and href not in urls:
                urls.append(href)
        for page in range(2, 20):
            resp = self.fetch(f"https://informationisbeautiful.net/blog/page/{page}/")
            if not resp:
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            found = False
            for a in soup.select("h2 a[href], .post-title a[href]"):
                href = a.get("href", "")
                if href and href not in urls:
                    urls.append(href)
                    found = True
            if not found:
                break
        # Also get visualizations page
        resp = self.fetch("https://informationisbeautiful.net/visualizations/")
        if resp:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select('a[href*="/visualizations/"]'):
                href = a.get("href", "")
                if href and href != "/visualizations/" and href not in urls:
                    full = urljoin("https://informationisbeautiful.net", href)
                    if full not in urls:
                        urls.append(full)
        return urls

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .post-title, title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one(".entry-content, .post-content, article, main")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "",
            "url": url,
            "content": content,
            "author": "David McCandless",
        }


# ── Enterprise + Academic Scrapers ────────────────────────────────


class DatawrapperScraper(BaseScraper):
    """Datawrapper blog — chart creation tutorials, weekly charts, best practices."""

    def __init__(self):
        super().__init__("datawrapper", "https://www.datawrapper.de", rate_limit=1.5)

    def parse_article(self, url: str) -> dict | None:
        # Datawrapper redirected blog.datawrapper.de → www.datawrapper.de/blog/
        url = url.replace("blog.datawrapper.de/", "www.datawrapper.de/blog/")
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one(".prose, article, main")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        # Date from meta tag
        date = ""
        date_meta = soup.select_one('meta[property="article:published_time"]')
        if date_meta:
            date = (date_meta.get("content") or "")[:10]
        if not date:
            date_el = soup.select_one(".date, time")
            if date_el:
                date = date_el.get("datetime", date_el.get_text(strip=True))
        # Author
        author = ""
        author_el = soup.select_one(".author")
        if author_el:
            author = author_el.get_text(strip=True)
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": author or "Datawrapper Team",
        }


class DbtBlogScraper(BaseScraper):
    """dbt Labs blog — analytics engineering, data modeling, modern data stack."""

    def __init__(self):
        super().__init__("dbt-blog", "https://www.getdbt.com", rate_limit=1.5)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one(".blog-content, .rich-text, article, main")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        # Date from meta or URL pattern
        date = ""
        date_meta = soup.select_one('meta[property="article:published_time"]')
        if date_meta:
            date = (date_meta.get("content") or "")[:10]
        if not date:
            time_el = soup.select_one("time")
            if time_el:
                date = time_el.get("datetime", time_el.get_text(strip=True))
        # Author
        author = ""
        author_el = soup.select_one(".author, .byline, meta[name='author']")
        if author_el:
            author = author_el.get("content", author_el.get_text(strip=True))
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": author or "dbt Labs",
        }


class MetabaseScraper(BaseScraper):
    """Metabase blog — open source BI, embedded analytics, data visualization."""

    def __init__(self):
        super().__init__("metabase", "https://www.metabase.com", rate_limit=1.5)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or "lost" in title.lower():
            return None
        content_el = soup.select_one(".content-container, .MB-Page, article, main")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        # Date from meta
        date = ""
        date_meta = soup.select_one('meta[property="article:published_time"]')
        if date_meta:
            date = (date_meta.get("content") or "")[:10]
        if not date:
            time_el = soup.select_one("time")
            if time_el:
                date = time_el.get("datetime", time_el.get_text(strip=True))
        # Author from meta
        author = ""
        author_meta = soup.select_one('meta[name="author"]')
        if author_meta:
            author = author_meta.get("content", "")
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": author or "Metabase Team",
        }


class DistillPubScraper(BaseScraper):
    """Distill.pub — interactive ML research articles (archived, gold standard)."""

    def __init__(self):
        super().__init__("distill-pub", "https://distill.pub", rate_limit=2.0)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # Distill uses custom web components: dt-article, dt-byline
        title_el = soup.select_one("dt-article h1, d-title h1, h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one("dt-article, d-article, article")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        # Date from byline or meta
        date = ""
        date_meta = soup.select_one('meta[property="article:published_time"]')
        if date_meta:
            date = (date_meta.get("content") or "")[:10]
        if not date:
            # Extract from URL: /2017/momentum/ → 2017
            date_match = re.search(r"/(\d{4})/", url)
            if date_match:
                date = date_match.group(1)
        # Author from .author or byline
        author = ""
        author_el = soup.select_one(".author, dt-byline .author")
        if author_el:
            author = author_el.get_text(strip=True)
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": author,
        }


class VarianceExplainedScraper(BaseScraper):
    """Variance Explained (David Robinson) — Bayesian stats, EDA, tidyverse."""

    def __init__(self):
        super().__init__(
            "variance-explained",
            "https://varianceexplained.org",
            rate_limit=1.5,
        )
        self.session.verify = False  # SSL cert issues
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        # Guard against binary/garbled responses
        try:
            text = resp.text
            if not text or len(text) < 200:
                return None
        except Exception:
            return None
        try:
            soup = BeautifulSoup(text, "html.parser")
        except Exception:
            return None
        title_el = soup.select_one("h1, .post-title, .entry-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one("article, .post-content, .entry-content")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        # Date from time element
        date = ""
        time_el = soup.select_one("time")
        if time_el:
            date = (time_el.get("datetime") or "")[:10]
        if not date:
            date_match = re.search(r"/(\d{4})/(\d{2})/", url)
            if date_match:
                date = f"{date_match.group(1)}-{date_match.group(2)}"
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": "David Robinson",
        }


class KozyrkovScraper(BaseScraper):
    """Kozyrkov Decision Intelligence (Substack) — decision science, applied stats.

    Uses RSS feed since Substack pages are JS-rendered.
    """

    def __init__(self):
        super().__init__(
            "kozyrkov-decision",
            "https://decision.substack.com",
            rate_limit=1.0,
        )

    def run(self) -> int:
        """Override run() to use RSS feed instead of URL-based scraping."""
        print(f"[{self.source_name}] Starting RSS scrape: {self.base_url}")
        print(f"[{self.source_name}] Output: {self.output_dir}")

        existing = list((self.output_dir / "articles").glob("*.md"))
        existing_count = len(existing)
        existing_urls: set[str] = set()
        meta_file = self.output_dir / "metadata" / "metadata.json"
        if meta_file.exists():
            try:
                prev = json.loads(meta_file.read_text())
                existing_urls = {
                    a["url"] for a in prev.get("articles", []) if a.get("url")
                }
            except Exception:
                pass

        idx = existing_count
        offset = 0
        batch_size = 20  # Substack RSS returns 20 per page

        while True:
            feed_url = f"{self.base_url}/feed"
            if offset > 0:
                feed_url += f"?offset={offset}"
            resp = self.fetch(feed_url)
            if not resp or not resp.text.strip():
                break

            try:
                import xml.etree.ElementTree as ET

                root = ET.fromstring(resp.text)
            except Exception:
                break

            items = root.findall(".//item")
            if not items:
                break

            for item in items:
                link_el = item.find("link")
                if link_el is None or not link_el.text:
                    continue
                url = link_el.text.strip()
                if url in existing_urls:
                    continue

                title_el = item.find("title")
                title = (
                    title_el.text.strip()
                    if title_el is not None and title_el.text
                    else ""
                )
                if not title:
                    continue

                # Get full HTML content from content:encoded
                content_encoded = item.find(
                    "{http://purl.org/rss/1.0/modules/content/}encoded"
                )
                if content_encoded is None or not content_encoded.text:
                    continue
                content = md(content_encoded.text)
                if len(content) < 100:
                    continue

                # Date
                date = ""
                pubdate_el = item.find("pubDate")
                if pubdate_el is not None and pubdate_el.text:
                    try:
                        from email.utils import parsedate_to_datetime

                        dt = parsedate_to_datetime(pubdate_el.text)
                        date = dt.strftime("%Y-%m-%d")
                    except Exception:
                        date = pubdate_el.text[:10]

                # Author
                author = ""
                creator_el = item.find("{http://purl.org/dc/elements/1.1/}creator")
                if creator_el is not None and creator_el.text:
                    author = creator_el.text.strip()

                article = {
                    "title": title,
                    "date": date,
                    "url": url,
                    "content": content,
                    "author": author or "Cassie Kozyrkov",
                    "source": self.source_name,
                }
                idx += 1
                path = save_article(self.output_dir, idx, article)
                if path:
                    self.articles.append(article)
                    existing_urls.add(url)

            # Track if any new articles were found in this batch
            batch_new = sum(
                1
                for item in items
                if item.find("link") is not None
                and item.find("link").text
                and item.find("link").text.strip() not in existing_urls
            )
            offset += batch_size
            # Stop if: fewer items than batch (end of feed), no new URLs, or hit max pages
            if len(items) < batch_size or batch_new == 0 or offset >= 200:
                break
            time.sleep(self.rate_limit)

        save_metadata(
            self.output_dir, self.source_name, self.base_url, self.articles, self.errors
        )
        print(
            f"[{self.source_name}] Done: {len(self.articles)} new, {len(self.errors)} errors"
        )
        return len(self.articles)

    def parse_article(self, url: str) -> dict | None:
        """Not used — RSS-based scraper overrides run() directly."""
        return None


# ── Wave 3: Textbooks + Preeminent Minds ─────────────────────────


class WilkeDatavizScraper(BaseScraper):
    """Claus Wilke — Fundamentals of Data Visualization (free online textbook)."""

    def __init__(self):
        super().__init__(
            "wilke-dataviz", "https://clauswilke.com/dataviz", rate_limit=1.0
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # bookdown: second h1 is chapter title, first is book title
        h1s = soup.find_all("h1")
        if len(h1s) >= 2:
            title = h1s[1].get_text(strip=True)
        elif h1s:
            title = h1s[0].get_text(strip=True)
        else:
            return None
        # Strip leading chapter number (e.g., "1Introduction" → "Introduction")
        title = re.sub(r"^\d+\s*", "", title).strip()
        if not title:
            return None
        content_el = soup.select_one(".book-body, .page-inner, section")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2019",
            "url": url,
            "content": content,
            "author": "Claus O. Wilke",
        }


class DataToVizScraper(BaseScraper):
    """Data-to-Viz — chart selection decision tree + caveat guides."""

    def __init__(self):
        super().__init__("data-to-viz", "https://www.data-to-viz.com", rate_limit=1.0)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .mytitle, title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or title.lower() == "data-to-viz":
            # Derive from URL path
            from urllib.parse import urlparse

            path = urlparse(url).path.strip("/").split("/")[-1]
            title = (
                path.replace(".html", "").replace("_", " ").replace("-", " ").title()
            )
        content_el = soup.select_one(".container, .col-lg-8, main, body")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 50:
            return None
        return {
            "title": title,
            "date": "",
            "url": url,
            "content": content,
            "author": "Yan Holtz",
        }


class SeeingTheoryScraper(BaseScraper):
    """Seeing Theory (Brown University) — interactive probability/stats tutorial."""

    def __init__(self):
        super().__init__(
            "seeing-theory", "https://seeing-theory.brown.edu", rate_limit=1.5
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .chapter-title, title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        # Main content — combine all section divs (#section1, #section2, #section3)
        sections = soup.select("[id^='section']")
        if sections:
            content = "\n\n".join(md(str(s)) for s in sections)
        else:
            content_el = soup.select_one(
                ".col-sm-9, main, article, #main-content, .section"
            )
            content = md(str(content_el)) if content_el else ""
        if len(content) < 50:
            return None
        return {
            "title": title,
            "date": "",
            "url": url,
            "content": content,
            "author": "Daniel Kunin et al.",
        }


class R4DSScraper(BaseScraper):
    """R for Data Science 2e (Hadley Wickham) — free online textbook."""

    def __init__(self):
        super().__init__("r4ds", "https://r4ds.hadley.nz", rate_limit=1.0)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one(
            "main, #quarto-document-content, .page-columns, article"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2023",
            "url": url,
            "content": content,
            "author": "Hadley Wickham, Mine Cetinkaya-Rundel, Garrett Grolemund",
        }


class PythonDSHandbookScraper(BaseScraper):
    """Python Data Science Handbook (Jake VanderPlas) — free online textbook."""

    def __init__(self):
        super().__init__(
            "python-ds-handbook",
            "https://jakevdp.github.io/PythonDataScienceHandbook",
            rate_limit=1.0,
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .section h1, title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or "Python Data Science" in title:
            # Use filename as title
            path = urlparse(url).path.split("/")[-1].replace(".html", "")
            title = path.replace("-", " ").title()
        content_el = soup.select_one(".section, article, .text_cell_render, main")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2023",
            "url": url,
            "content": content,
            "author": "Jake VanderPlas",
        }


class ThinkBayesScraper(BaseScraper):
    """Think Bayes 2 (Allen Downey) — Bayesian statistics textbook."""

    def __init__(self):
        super().__init__(
            "think-bayes",
            "https://allendowney.github.io/ThinkBayes2",
            rate_limit=1.0,
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .title, #firstHeading")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one(
            "main, article, .body, #main-content, .jp-Notebook"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2021",
            "url": url,
            "content": content,
            "author": "Allen B. Downey",
        }


class AndyKirkScraper(BaseScraper):
    """Visualising Data (Andy Kirk) — data visualization blog since 2010."""

    def __init__(self):
        super().__init__("andy-kirk", "https://visualisingdata.com", rate_limit=1.5)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        # Elementor-based WordPress: content in .site-content or #content
        content_el = soup.select_one(
            ".site-content, #content, .entry-content, .post-content, article"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        # Date from meta or URL
        date = ""
        date_meta = soup.select_one('meta[property="article:published_time"]')
        if date_meta:
            date = (date_meta.get("content") or "")[:10]
        if not date:
            time_el = soup.select_one("time")
            if time_el:
                date = (time_el.get("datetime") or time_el.get_text(strip=True))[:10]
        if not date:
            date_match = re.search(r"/(\d{4})/(\d{2})/", url)
            if date_match:
                date = f"{date_match.group(1)}-{date_match.group(2)}"
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": "Andy Kirk",
        }


class AlbertoCairoScraper(BaseScraper):
    """The Functional Art (Alberto Cairo) — visualization criticism + theory."""

    def __init__(self):
        super().__init__(
            "alberto-cairo",
            "https://thefunctionalart.blogspot.com",
            rate_limit=1.5,
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # Blogspot uses .post-title or h3.post-title
        title_el = soup.select_one("h3.post-title, h1.post-title, .post-title a, h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one(
            ".post-body, .entry-content, .post-content, article"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 50:
            return None
        # Date from header or abbr
        date = ""
        date_el = soup.select_one(".date-header abbr, .published, time")
        if date_el:
            date = date_el.get("title", date_el.get_text(strip=True))
        if not date:
            date_match = re.search(r"/(\d{4})/(\d{2})/", url)
            if date_match:
                date = f"{date_match.group(1)}-{date_match.group(2)}"
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": "Alberto Cairo",
        }


# ── Wave 4: Advanced Techniques ──────────────────────────────────


class FPP3Scraper(BaseScraper):
    """Forecasting: Principles and Practice 3e (Hyndman & Athanasopoulos).
    NOTE: otexts.com uses CAPTCHA bot protection (returns 202 + redirect).
    Cannot scrape with requests. Would need browser automation."""

    def __init__(self):
        super().__init__("fpp3", "https://otexts.com/fpp3", rate_limit=1.0)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        # Site returns 202 with CAPTCHA redirect — check for it
        if resp.status_code == 202 or "sgcaptcha" in resp.text:
            logger.warning("FPP3: CAPTCHA detected at %s — skipping", url)
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .chapter-title")
        title = title_el.get_text(strip=True) if title_el else ""
        title = re.sub(r"^\d+(\.\d+)*\s*", "", title).strip()
        if not title:
            return None
        content_el = soup.select_one(
            "main, .page-columns, .book-body, section, article"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2021",
            "url": url,
            "content": content,
            "author": "Rob J. Hyndman, George Athanasopoulos",
        }


class CausalMixtapeScraper(BaseScraper):
    """Causal Inference: The Mixtape (Scott Cunningham) — causal methods textbook."""

    def __init__(self):
        super().__init__(
            "causal-mixtape", "https://mixtape.scunning.com", rate_limit=1.0
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, .title")
        title = title_el.get_text(strip=True) if title_el else ""
        title = re.sub(r"^\d+\s*", "", title).strip()
        if not title:
            return None
        content_el = soup.select_one(
            "main, #quarto-document-content, .page-columns, section, article"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2021",
            "url": url,
            "content": content,
            "author": "Scott Cunningham",
        }


class TheEffectScraper(BaseScraper):
    """The Effect (Nick Huntington-Klein) — causal inference for data science."""

    def __init__(self):
        super().__init__("the-effect", "https://theeffectbook.net", rate_limit=1.0)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # Content is in second div.row (first is sidebar/nav)
        rows = soup.select("div.row")
        content_el = rows[1] if len(rows) >= 2 else None
        if not content_el:
            content_el = soup.select_one(
                "main, #quarto-document-content, .book-body, section, article"
            )
        if not content_el:
            return None
        title_el = content_el.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        title = re.sub(r"^Chapter\s+\d+\s*[-–—:]\s*", "", title).strip()
        title = re.sub(r"^\d+\s*", "", title).strip()
        if not title:
            return None
        content = md(str(content_el))
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2022",
            "url": url,
            "content": content,
            "author": "Nick Huntington-Klein",
        }


class FeatEngineeringScraper(BaseScraper):
    """Feature Engineering and Selection (Kuhn & Johnson) — practical ML prep."""

    def __init__(self):
        super().__init__("feat-engineering", "https://feat.engineering", rate_limit=1.0)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # bookdown: second h1 is chapter title
        h1s = soup.find_all("h1")
        if len(h1s) >= 2:
            title = h1s[1].get_text(strip=True)
        elif h1s:
            title = h1s[0].get_text(strip=True)
        else:
            return None
        title = re.sub(r"^\d+(\.\d+)*\s*", "", title).strip()
        if not title:
            return None
        content_el = soup.select_one(".book-body, .page-inner, section, main")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2019",
            "url": url,
            "content": content,
            "author": "Max Kuhn, Kjell Johnson",
        }


class LilianWengScraper(BaseScraper):
    """Lil'Log (Lilian Weng) — gold-standard ML/AI deep dives."""

    def __init__(self):
        super().__init__("lilian-weng", "https://lilianweng.github.io", rate_limit=1.5)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1.post-title, h1, .article-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        content_el = soup.select_one(
            ".article-content, .post-content, .entry-content, article, main"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 200:
            return None
        # Date from URL /YYYY-MM-DD-
        date = ""
        date_match = re.search(r"/(\d{4}-\d{2}-\d{2})-", url)
        if date_match:
            date = date_match.group(1)
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": "Lilian Weng",
        }


class ColahScraper(BaseScraper):
    """Colah's Blog (Chris Olah) — neural net visualization + intuitive ML explanations."""

    def __init__(self):
        super().__init__("colah", "https://colah.github.io", rate_limit=1.5)

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        # Strip "-- colah's blog" suffix if present
        title = re.sub(r"\s*[-–—]+\s*colah.*$", "", title, flags=re.IGNORECASE).strip()
        if not title:
            return None
        content_el = soup.select_one(
            "#content, .post-content, .entry-content, article, main"
        )
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        # Date from URL /YYYY-MM-
        date = ""
        date_match = re.search(r"/(\d{4})-(\d{2})-", url)
        if date_match:
            date = f"{date_match.group(1)}-{date_match.group(2)}"
        return {
            "title": title,
            "date": date,
            "url": url,
            "content": content,
            "author": "Chris Olah",
        }


class ModernStatsBioScraper(BaseScraper):
    """Modern Statistics for Modern Biology (Holmes & Huber) — advanced stats textbook."""

    def __init__(self):
        super().__init__(
            "modern-stats-bio", "https://www.huber.embl.de/msmb", rate_limit=1.0
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # bookdown: second h1 is chapter title
        h1s = soup.find_all("h1")
        if len(h1s) >= 2:
            title = h1s[1].get_text(strip=True)
        elif h1s:
            title = h1s[0].get_text(strip=True)
        else:
            return None
        title = re.sub(r"^Chapter\s+\d+\s*", "", title).strip()
        title = re.sub(r"^\d+(\.\d+)*\s*", "", title).strip()
        if not title:
            return None
        content_el = soup.select_one(".book-body, .page-inner, section, main")
        content = md(str(content_el)) if content_el else ""
        if len(content) < 100:
            return None
        return {
            "title": title,
            "date": "2022",
            "url": url,
            "content": content,
            "author": "Susan Holmes, Wolfgang Huber",
        }


class NISTHandbookScraper(BaseScraper):
    """NIST/SEMATECH e-Handbook of Statistical Methods — US govt reference."""

    def __init__(self):
        super().__init__(
            "nist-handbook",
            "https://www.itl.nist.gov/div898/handbook",
            rate_limit=0.5,
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # Title is in <title> tag: "1.3.5. Quantitative Techniques"
        title_el = soup.select_one("title")
        title = title_el.get_text(strip=True) if title_el else ""
        # Strip leading section number
        title = re.sub(r"^\d+(\.\d+)*\.?\s*", "", title).strip()
        if not title:
            return None
        body = soup.select_one("body")
        content = md(str(body)) if body else ""
        if len(content) < 300:
            return None
        return {
            "title": title,
            "date": "",
            "url": url,
            "content": content,
            "author": "NIST/SEMATECH",
        }


class CrossValidatedScraper(BaseScraper):
    """Cross Validated (stats.stackexchange.com) — top-voted Q&A."""

    def __init__(self):
        super().__init__(
            "cross-validated",
            "https://stats.stackexchange.com",
            rate_limit=2.0,
        )

    def parse_article(self, url: str) -> dict | None:
        resp = self.fetch(url)
        if not resp:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("#question-header h1, h1[itemprop=name], h1")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None
        # Question body
        q_body = soup.select_one(
            ".question .js-post-body, .question .s-prose, .question .post-text"
        )
        q_text = md(str(q_body)) if q_body else ""
        # Top answers (up to 3)
        answers = soup.select(
            ".answer .js-post-body, .answer .s-prose, .answer .post-text"
        )
        a_texts = []
        for a in answers[:3]:
            a_texts.append(md(str(a)))
        content = f"## Question\n\n{q_text}\n\n"
        for i, at in enumerate(a_texts, 1):
            content += f"## Answer {i}\n\n{at}\n\n"
        if len(content) < 300:
            return None
        return {
            "title": title,
            "date": "",
            "url": url,
            "content": content,
            "author": "Cross Validated Community",
        }


# ── Registry ──────────────────────────────────────────────────────

SCRAPERS = {
    "flowingdata": FlowingDataScraper,
    "pudding": PuddingScraper,
    "data-sketches": DataSketchesScraper,
    "nightingale": NightingaleScraper,
    "storytelling-with-data": StorytellingWithDataScraper,
    "andrew-gelman": AndrewGelmanScraper,
    "simply-statistics": SimplyStatisticsScraper,
    "statistical-thinking": StatisticalThinkingScraper,
    "observable-blog": ObservableBlogScraper,
    "plotly-blog": PlotlyBlogScraper,
    "info-is-beautiful": InfoIsBeautifulScraper,
    # Enterprise
    "datawrapper": DatawrapperScraper,
    "dbt-blog": DbtBlogScraper,
    "metabase": MetabaseScraper,
    # Academic
    "distill-pub": DistillPubScraper,
    "variance-explained": VarianceExplainedScraper,
    "kozyrkov-decision": KozyrkovScraper,
    # Textbooks + Preeminent Minds
    "wilke-dataviz": WilkeDatavizScraper,
    "data-to-viz": DataToVizScraper,
    "seeing-theory": SeeingTheoryScraper,
    "r4ds": R4DSScraper,
    "python-ds-handbook": PythonDSHandbookScraper,
    "think-bayes": ThinkBayesScraper,
    "andy-kirk": AndyKirkScraper,
    "alberto-cairo": AlbertoCairoScraper,
    # Advanced Techniques
    "fpp3": FPP3Scraper,
    "causal-mixtape": CausalMixtapeScraper,
    "the-effect": TheEffectScraper,
    "feat-engineering": FeatEngineeringScraper,
    "lilian-weng": LilianWengScraper,
    "colah": ColahScraper,
    "modern-stats-bio": ModernStatsBioScraper,
    # Reference + Community
    "nist-handbook": NISTHandbookScraper,
    "cross-validated": CrossValidatedScraper,
}

PRIORITY_1 = ["flowingdata", "pudding", "data-sketches"]
PRIORITY_2 = ["andrew-gelman", "statistical-thinking", "simply-statistics"]
PRIORITY_3 = [
    "storytelling-with-data",
    "observable-blog",
    "plotly-blog",
    "nightingale",
    "info-is-beautiful",
]
PRIORITY_4 = [
    "datawrapper",
    "dbt-blog",
    "metabase",
    "distill-pub",
    "variance-explained",
    "kozyrkov-decision",
]
PRIORITY_5 = [
    "wilke-dataviz",
    "data-to-viz",
    "seeing-theory",
    "r4ds",
    "python-ds-handbook",
    "think-bayes",
    "andy-kirk",
    "alberto-cairo",
]
PRIORITY_6 = [
    "fpp3",
    "causal-mixtape",
    "the-effect",
    "feat-engineering",
    "lilian-weng",
    "colah",
    "modern-stats-bio",
]
PRIORITY_7 = [
    "nist-handbook",
    "cross-validated",
]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Data Analyst KB Scraper")
    parser.add_argument(
        "--source",
        required=False,
        help="Source to scrape (or all, all-priority-1, all-priority-2, all-priority-3)",
    )
    parser.add_argument("--list", action="store_true", help="List available sources")
    args = parser.parse_args()

    if args.list:
        print("Available sources:")
        for name, cls in SCRAPERS.items():
            tier = (
                "P1"
                if name in PRIORITY_1
                else "P2"
                if name in PRIORITY_2
                else "P3"
                if name in PRIORITY_3
                else "P4"
                if name in PRIORITY_4
                else "P5"
                if name in PRIORITY_5
                else "P6"
            )
            existing = (
                len(list((KB_BASE / name / "articles").glob("*.md")))
                if (KB_BASE / name / "articles").exists()
                else 0
            )
            print(f"  [{tier}] {name:30s} ({existing} articles)")
        return

    if not args.source:
        parser.print_help()
        return

    sources_to_run = []
    if args.source == "all":
        sources_to_run = (
            PRIORITY_1 + PRIORITY_2 + PRIORITY_3 + PRIORITY_4 + PRIORITY_5 + PRIORITY_6
        )
    elif args.source == "all-priority-1":
        sources_to_run = PRIORITY_1
    elif args.source == "all-priority-2":
        sources_to_run = PRIORITY_2
    elif args.source == "all-priority-3":
        sources_to_run = PRIORITY_3
    elif args.source == "all-priority-4":
        sources_to_run = PRIORITY_4
    elif args.source == "all-priority-5":
        sources_to_run = PRIORITY_5
    elif args.source == "all-priority-6":
        sources_to_run = PRIORITY_6
    elif args.source in SCRAPERS:
        sources_to_run = [args.source]
    else:
        print(f"Unknown source: {args.source}")
        print(f"Available: {', '.join(SCRAPERS.keys())}")
        return

    total = 0
    for source in sources_to_run:
        print(f"\n{'=' * 60}")
        scraper = SCRAPERS[source]()
        count = scraper.run()
        total += count
        print(f"{'=' * 60}\n")

    print(f"\nTotal new articles: {total}")


if __name__ == "__main__":
    main()
