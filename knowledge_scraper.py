#!/usr/bin/env python3
"""Universal knowledge base scraper with metadata templates

Scrapes documentation sites and creates markdown files with YAML frontmatter.
Supports multiple source types with domain-specific metadata templates.
"""

import argparse
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional, Set
import requests
from bs4 import BeautifulSoup
import yaml

try:
    from content_sanitizer import sanitize_content
    SANITIZER_AVAILABLE = True
except ImportError:
    SANITIZER_AVAILABLE = False

# Rate limiting
DEFAULT_DELAY = 5  # seconds between requests
USER_AGENT = "PopChaosLabs/1.0 (Educational Research; nissim.direct@gmail.com)"

# Metadata templates by source type
METADATA_TEMPLATES = {
    "documentation": {
        "type": "documentation",
        "required_fields": ["title", "author", "source", "source_url", "date_published", "date_scraped", "skill"],
        "optional_fields": ["version", "category", "product"]
    },
    "blog": {
        "type": "article",
        "required_fields": ["title", "author", "source", "source_url", "date_published", "date_scraped", "skill"],
        "optional_fields": ["tags", "topics", "excerpt"]
    },
    "art-criticism": {
        "type": "review",
        "required_fields": ["title", "author", "source", "source_url", "date_published", "date_scraped", "skill"],
        "optional_fields": ["artist", "exhibition", "institution", "movement"]
    }
}

# Source configurations
SOURCE_CONFIGS = {
    "obsidian": {
        "base_url": "https://help.obsidian.md/",
        "template": "documentation",
        "skill": "cto",
        "author": "Obsidian Team",
        "output_dir": "~/Development/obsidian-docs"
    },
    "notion": {
        "base_url": "https://www.notion.so/help/",
        "template": "documentation",
        "skill": "cto",
        "author": "Notion Team",
        "output_dir": "~/Development/notion-docs"
    },
    "claude-api": {
        "base_url": "https://docs.anthropic.com/",
        "template": "documentation",
        "skill": "cto",
        "author": "Anthropic",
        "output_dir": "~/Development/claude-docs"
    },
    "claude-code": {
        "base_url": "https://docs.claude.ai/docs/claude-code",
        "template": "documentation",
        "skill": "cto",
        "author": "Anthropic",
        "output_dir": "~/Development/claude-code-docs"
    },
    "jnd": {
        "base_url": "https://jnd.org/",
        "template": "blog",
        "skill": "lenny",
        "author": "Don Norman",
        "output_dir": "~/Development/don-norman-jnd"
    },
    "nngroup": {
        "base_url": "https://www.nngroup.com/articles/author/don-norman/",
        "template": "blog",
        "skill": "lenny",
        "author": "Don Norman",
        "output_dir": "~/Development/don-norman-nngroup"
    }
}


class KnowledgeScraper:
    """Universal scraper with rate limiting and metadata generation"""

    def __init__(self, source_id: str, delay: int = DEFAULT_DELAY, verbose: bool = True):
        self.source_id = source_id
        self.delay = delay
        self.verbose = verbose
        self.visited_urls: Set[str] = set()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        # Load source configuration
        if source_id not in SOURCE_CONFIGS:
            raise ValueError(f"Unknown source: {source_id}. Available: {list(SOURCE_CONFIGS.keys())}")

        self.config = SOURCE_CONFIGS[source_id]
        self.template = METADATA_TEMPLATES[self.config["template"]]
        self.output_dir = Path(self.config["output_dir"]).expanduser()

        # Create output directories
        self.raw_dir = self.output_dir / "raw"
        self.analyzed_dir = self.output_dir / "analyzed"
        self.index_dir = self.output_dir / "index"

        for dir_path in [self.raw_dir, self.analyzed_dir, self.index_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def log(self, message: str):
        """Print if verbose"""
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL with rate limiting and error handling"""
        if url in self.visited_urls:
            self.log(f"Skipping already visited: {url}")
            return None

        self.log(f"Fetching: {url}")

        try:
            time.sleep(self.delay)  # Rate limiting
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            self.visited_urls.add(url)
            return response.text
        except requests.RequestException as e:
            self.log(f"ERROR fetching {url}: {e}")
            return None

    def extract_content(self, html: str, url: str) -> Optional[Dict]:
        """Extract title and main content from HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Try multiple strategies for title
        title = None
        for selector in ['h1', 'title', 'meta[property="og:title"]']:
            element = soup.select_one(selector)
            if element:
                title = element.get('content') if element.name == 'meta' else element.get_text().strip()
                break

        if not title:
            self.log(f"WARNING: No title found for {url}")
            title = urlparse(url).path.split('/')[-1] or "Untitled"

        # Try multiple strategies for main content
        content = None
        for selector in ['article', 'main', '.content', '#content', 'body']:
            element = soup.select_one(selector)
            if element:
                # Extract text while preserving structure
                content = self._html_to_markdown(element)
                break

        if not content:
            self.log(f"WARNING: No content found for {url}")
            return None

        return {
            "title": title,
            "content": content,
            "url": url
        }

    def _html_to_markdown(self, element) -> str:
        """Convert HTML element to markdown (basic implementation)"""
        # Simple conversion - could be enhanced with html2text library
        text_parts = []

        for child in element.descendants:
            if child.name == 'h1':
                text_parts.append(f"\n# {child.get_text().strip()}\n")
            elif child.name == 'h2':
                text_parts.append(f"\n## {child.get_text().strip()}\n")
            elif child.name == 'h3':
                text_parts.append(f"\n### {child.get_text().strip()}\n")
            elif child.name == 'p':
                text_parts.append(f"{child.get_text().strip()}\n\n")
            elif child.name == 'code':
                text_parts.append(f"`{child.get_text().strip()}`")
            elif child.name == 'pre':
                text_parts.append(f"\n```\n{child.get_text().strip()}\n```\n")

        return "".join(text_parts)

    def generate_metadata(self, extracted: Dict) -> Dict:
        """Generate YAML frontmatter metadata"""
        today = datetime.now().strftime("%Y-%m-%d")

        metadata = {
            "title": extracted["title"],
            "author": self.config["author"],
            "source": self.source_id,
            "source_url": extracted["url"],
            "date_published": today,  # Fallback - should extract from page
            "date_scraped": today,
            "type": self.template["type"],
            "skill": self.config["skill"],
            "tags": []  # Will be filled by LLM analysis
        }

        return metadata

    def save_article(self, metadata: Dict, content: str):
        """Save article with YAML frontmatter"""
        # Generate filename from URL (SECURITY: Prevent path traversal)
        url_hash = hashlib.md5(metadata["source_url"].encode()).hexdigest()[:8]

        # Sanitize title (remove path components and traversal attempts)
        title = os.path.basename(metadata["title"])  # Remove any path
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_'))[:50]
        safe_title = safe_title.replace('..', '').replace('/', '').replace('\\', '').strip()

        # Fallback if empty after sanitization
        if not safe_title:
            safe_title = "untitled"

        filename = f"{safe_title.replace(' ', '-').lower()}-{url_hash}.md"

        filepath = self.raw_dir / filename

        # Sanitize content before writing (strip injection patterns, filler)
        if SANITIZER_AVAILABLE:
            content, report = sanitize_content(content)
            if report.blocked:
                self.log(f"BLOCKED by sanitizer: {metadata['source_url']} ({report.patterns_matched})")
                return None
            if report.items_removed > 0:
                self.log(f"Sanitized: removed {report.items_removed} items ({report.patterns_matched})")

        # Build markdown with frontmatter
        frontmatter = yaml.dump(metadata, default_flow_style=False, allow_unicode=True)
        full_content = f"---\n{frontmatter}---\n\n{content}"

        filepath.write_text(full_content, encoding='utf-8')
        self.log(f"Saved: {filepath}")

        return filepath

    def scrape_url(self, url: str) -> Optional[Path]:
        """Scrape single URL and save to disk"""
        html = self.fetch_url(url)
        if not html:
            return None

        extracted = self.extract_content(html, url)
        if not extracted:
            return None

        metadata = self.generate_metadata(extracted)
        filepath = self.save_article(metadata, extracted["content"])

        return filepath

    def scrape_sitemap(self, sitemap_url: str):
        """Scrape all URLs from sitemap"""
        self.log(f"Fetching sitemap: {sitemap_url}")
        html = self.fetch_url(sitemap_url)
        if not html:
            return

        soup = BeautifulSoup(html, 'xml')
        urls = [loc.text for loc in soup.find_all('loc')]

        self.log(f"Found {len(urls)} URLs in sitemap")

        for url in urls:
            self.scrape_url(url)

    def discover_links(self, start_url: str, max_depth: int = 2, max_pages: int = 100) -> List[str]:
        """Discover documentation pages by following links"""
        to_visit = [(start_url, 0)]
        discovered = []
        base_domain = urlparse(start_url).netloc

        while to_visit and len(discovered) < max_pages:
            url, depth = to_visit.pop(0)

            if url in self.visited_urls or depth > max_depth:
                continue

            html = self.fetch_url(url)
            if not html:
                continue

            discovered.append(url)

            if depth < max_depth:
                soup = BeautifulSoup(html, 'html.parser')
                for link in soup.find_all('a', href=True):
                    absolute_url = urljoin(url, link['href'])
                    link_domain = urlparse(absolute_url).netloc

                    # Only follow links on same domain
                    if link_domain == base_domain and absolute_url not in self.visited_urls:
                        to_visit.append((absolute_url, depth + 1))

        return discovered


def main():
    parser = argparse.ArgumentParser(description="Universal knowledge base scraper")
    parser.add_argument("source", choices=list(SOURCE_CONFIGS.keys()), help="Source to scrape")
    parser.add_argument("--url", help="Specific URL to scrape (optional)")
    parser.add_argument("--sitemap", help="Sitemap URL to scrape")
    parser.add_argument("--discover", action="store_true", help="Auto-discover pages by following links")
    parser.add_argument("--max-pages", type=int, default=100, help="Max pages to discover")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY, help="Delay between requests (seconds)")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    scraper = KnowledgeScraper(args.source, delay=args.delay, verbose=not args.quiet)

    if args.url:
        scraper.scrape_url(args.url)
    elif args.sitemap:
        scraper.scrape_sitemap(args.sitemap)
    elif args.discover:
        base_url = SOURCE_CONFIGS[args.source]["base_url"]
        urls = scraper.discover_links(base_url, max_pages=args.max_pages)
        print(f"\nDiscovered {len(urls)} pages. Scraping...")
        for url in urls:
            scraper.scrape_url(url)
    else:
        print("ERROR: Must specify --url, --sitemap, or --discover")
        return 1

    print(f"\n✅ Complete! Articles saved to: {scraper.output_dir}")
    print(f"   Raw articles: {scraper.raw_dir}")
    print(f"   Next: Run knowledge_analyzer.py for LLM enrichment")


if __name__ == "__main__":
    main()
