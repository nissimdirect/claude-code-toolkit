#!/usr/bin/env python3
"""
Universal Web Scraper for Advisor Training Data
Runs independently, no token burn, saves structured markdown
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

class AdvisorScraper:
    def __init__(self, base_url, output_dir, rate_limit=1.0):
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.rate_limit = rate_limit  # seconds between requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Claude Code Advisor Builder'
        })

        # Create directory structure
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / 'articles').mkdir(exist_ok=True)
        (self.output_dir / 'metadata').mkdir(exist_ok=True)

        self.articles = []
        self.errors = []

    def fetch_page(self, url, retry=3):
        """Fetch page with retry logic"""
        for attempt in range(retry):
            try:
                time.sleep(self.rate_limit)  # Rate limiting
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt == retry - 1:
                    self.errors.append({'url': url, 'error': str(e)})
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
        return None

    def extract_article_urls(self, archive_url):
        """Extract all article URLs from archive page(s)"""
        raise NotImplementedError("Override in subclass")

    def extract_article_content(self, url):
        """Extract article content and metadata"""
        raise NotImplementedError("Override in subclass")

    def auto_tag_concepts(self, text):
        """Auto-tag key concepts with [[wiki-links]] for Obsidian knowledge graph"""
        import re

        # Key concepts to auto-tag (audio production, music business, creative tools)
        concepts = [
            # Audio Production
            'LUFS', 'loudness', 'saturation', 'granulation', 'reverb', 'delay',
            'compression', 'EQ', 'equalization', 'mastering', 'mixing',
            'transient', 'sidechain', 'stereo imaging', 'bit depth', 'sample rate',
            'clipping', 'distortion', 'harmonics', 'frequency', 'resonance',
            'envelope', 'ADSR', 'LFO', 'modulation', 'automation',

            # Music Business
            'streaming', 'Spotify', 'Apple Music', 'distribution', 'sync licensing',
            'royalties', 'publishing', 'PRO', 'ASCAP', 'BMI', 'mechanicals',
            'playlist', 'algorithm', 'TikTok', 'Instagram', 'social media',
            'NFT', 'Web3', 'blockchain', 'fan engagement', 'monetization',

            # Creative Tools & Concepts
            'JUCE', 'VST', 'AU', 'AAX', 'plugin', 'DAW', 'Ableton', 'Logic',
            'Pro Tools', 'FL Studio', 'Reaper', 'synthesizer', 'sampler',
            'drum machine', 'MIDI', 'audio interface', 'microphone',

            # Business & Strategy
            'indie hacker', 'bootstrapping', 'revenue', 'MRR', 'ARR',
            'product-market fit', 'MVP', 'iteration', 'launch', 'marketing',
            'SEO', 'content marketing', 'email list', 'funnel', 'conversion',
            'pricing', 'positioning', 'competitive analysis', 'differentiation',

            # Creative Process
            'workflow', 'productivity', 'creativity', 'inspiration', 'iteration',
            'feedback', 'collaboration', 'remote work', 'async', 'documentation'
        ]

        # Sort by length (longest first) to avoid partial matches
        concepts.sort(key=len, reverse=True)

        # Tag each concept if not already tagged
        for concept in concepts:
            # Case-insensitive search, but preserve original case
            pattern = re.compile(r'\b(' + re.escape(concept) + r')\b', re.IGNORECASE)

            # Don't tag if already in [[brackets]] or inside a link
            def replace_if_not_tagged(match):
                # Check if already inside [[...]] or [...](...)
                start_pos = match.start()
                context_before = text[max(0, start_pos-3):start_pos]
                context_after = text[start_pos+len(match.group(0)):start_pos+len(match.group(0))+3]

                if '[[' in context_before or ']]' in context_after:
                    return match.group(0)  # Already tagged
                if context_before.endswith('[') or '](' in context_after:
                    return match.group(0)  # Inside markdown link

                return f"[[{match.group(0)}]]"

            text = pattern.sub(replace_if_not_tagged, text)

        return text

    def save_article(self, article_data):
        """Save article as markdown with metadata"""
        # Generate filename
        slug = self.slugify(article_data['title'])
        filename = f"articles/{article_data['id']:03d}-{slug}.md"
        filepath = self.output_dir / filename

        # Auto-tag content with [[wiki-links]] for Obsidian
        tagged_content = self.auto_tag_concepts(article_data['content'])

        # Create markdown content
        content = f"""# {article_data['title']}

**Author:** {article_data.get('author', 'Unknown')}
**Date:** {article_data.get('date', 'Unknown')}
**URL:** {article_data['url']}

---

{tagged_content}
"""

        filepath.write_text(content, encoding='utf-8')

        # Update article record
        article_data['file'] = str(filename)
        article_data['word_count'] = len(article_data['content'].split())
        self.articles.append(article_data)

        return filepath

    def save_metadata(self):
        """Save metadata.json and INDEX.md"""
        # Save JSON
        metadata = {
            'advisor': self.output_dir.name,
            'source': self.base_url,
            'scraped_at': datetime.now().isoformat(),
            'total_articles': len(self.articles),
            'errors': len(self.errors),
            'articles': self.articles
        }

        json_path = self.output_dir / 'metadata' / 'metadata.json'
        json_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')

        # Generate INDEX.md with wiki-links to related concepts
        index_content = f"""# {self.output_dir.name.title()} - Knowledge Base

**Source:** {self.base_url}
**Scraped:** {datetime.now().strftime('%Y-%m-%d')}
**Total Articles:** {len(self.articles)}
**Errors:** {len(self.errors)}

**Related Concepts:** [[audio production]] | [[music business]] | [[plugin development]] | [[JUCE]] | [[marketing]] | [[indie hacker]] | [[distribution]] | [[workflow]]

## Articles

"""
        for article in sorted(self.articles, key=lambda x: x.get('date', ''), reverse=True):
            # Auto-tag article titles with wiki-links
            tagged_title = self.auto_tag_concepts(article['title'])
            index_content += f"- [{tagged_title}]({article['file']}) - {article.get('date', 'Unknown')}\n"

        if self.errors:
            index_content += f"\n## Errors ({len(self.errors)})\n\n"
            for error in self.errors[:10]:  # Show first 10
                index_content += f"- {error['url']}: {error['error']}\n"

        index_path = self.output_dir / 'INDEX.md'
        index_path.write_text(index_content, encoding='utf-8')

        return metadata

    @staticmethod
    def slugify(text):
        """Create URL-safe slug"""
        import re
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text[:50]  # Limit length

    def run(self):
        """Main scraping workflow"""
        print(f"🕷️  Starting scrape: {self.base_url}")
        print(f"📁 Output: {self.output_dir}")

        # Extract URLs
        print("\n1️⃣  Extracting article URLs...")
        urls = self.extract_article_urls(self.base_url)
        print(f"   Found {len(urls)} articles")

        # Scrape articles
        print("\n2️⃣  Scraping articles...")
        for i, url in enumerate(urls, 1):
            print(f"   [{i}/{len(urls)}] {url}")
            article_data = self.extract_article_content(url)
            if article_data:
                article_data['id'] = i
                self.save_article(article_data)

        # Save metadata
        print("\n3️⃣  Saving metadata...")
        metadata = self.save_metadata()

        # Report
        print(f"\n✅ Complete!")
        print(f"   Articles: {len(self.articles)}")
        print(f"   Errors: {len(self.errors)}")
        print(f"   Output: {self.output_dir}")

        return metadata


class BeehiivScraper(AdvisorScraper):
    """Scraper for Beehiiv newsletters (Jesse Cannon, etc.)"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from Beehiiv archive pages"""
        urls = []
        base_archive = archive_url.rstrip('/') + '/archive'

        # Beehiiv uses pagination: /archive?page=1, /archive?page=2, etc.
        # First, determine total pages
        response = self.fetch_page(base_archive)
        if not response:
            return urls

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all article links on all pages
        # (Beehiiv structure: links with /p/ pattern)
        page = 1
        max_pages = 20  # Safety limit

        while page <= max_pages:
            page_url = f"{base_archive}?page={page}"
            print(f"   Checking page {page}...")

            response = self.fetch_page(page_url)
            if not response:
                break

            soup = BeautifulSoup(response.content, 'html.parser')

            # Find article links (Beehiiv uses /p/ pattern)
            article_links = soup.find_all('a', href=lambda x: x and '/p/' in x)

            if not article_links:
                break  # No more articles

            for link in article_links:
                url = urljoin(self.base_url, link['href'])
                if url not in urls:
                    urls.append(url)

            page += 1

        return urls

    def extract_article_content(self, url):
        """Extract content from Beehiiv article - production-grade with fallbacks"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract title - multiple strategies
        title = None
        for selector in ['h1', 'title', '.post-title', '#post-title']:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                title = elem.text.strip()
                break
        if not title:
            title = 'Untitled'

        # Extract date - Beehiiv specific, then general
        date = ''
        # Strategy 1: Beehiiv byline
        byline = soup.find('div', class_='bh__byline_wrapper')
        if byline:
            date_span = byline.find('span', style=lambda x: x and 'opacity:0.75' in x)
            if date_span:
                date = date_span.text.strip()
        # Strategy 2: Standard time element
        if not date:
            time_elem = soup.find('time')
            if time_elem:
                date = time_elem.get('datetime', time_elem.text.strip())
        # Strategy 3: Meta tags
        if not date:
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                date = meta_date.get('content', '')

        # Extract author - multiple strategies
        author = 'Jesse Cannon'  # Default for this newsletter
        # Strategy 1: Beehiiv byline
        if byline:
            author_link = byline.find('a', href=lambda x: x and 'twitter.com' in x)
            if author_link:
                author = author_link.text.strip() or author
        # Strategy 2: Meta tags
        if author == 'Jesse Cannon':  # Still default
            meta_author = soup.find('meta', property='article:author')
            if meta_author:
                author = meta_author.get('content', author)

        # Extract main content - MULTIPLE STRATEGIES
        content = None

        # Strategy 1: Beehiiv specific (#content-blocks)
        content_div = soup.find('div', id='content-blocks')
        if content_div:
            content = md(str(content_div))

        # Strategy 2: Rendered post wrapper
        if not content:
            content_div = soup.find('div', class_='rendered-post')
            if content_div:
                content = md(str(content_div))

        # Strategy 3: Article tag
        if not content:
            content_div = soup.find('article')
            if content_div:
                content = md(str(content_div))

        # Strategy 4: Main content area
        if not content:
            content_div = soup.find('main')
            if content_div:
                content = md(str(content_div))

        # Strategy 5: Find largest text block (heuristic)
        if not content:
            candidates = soup.find_all(['div', 'section', 'article'])
            max_length = 0
            best_candidate = None
            for candidate in candidates:
                text_length = len(candidate.get_text(strip=True))
                if text_length > max_length:
                    max_length = text_length
                    best_candidate = candidate
            if best_candidate and max_length > 500:  # Minimum threshold
                content = md(str(best_candidate))

        # Last resort
        if not content:
            content = "Content extraction failed - HTML structure not recognized"

        # Parse date to YYYY-MM-DD format
        parsed_date = ''
        if date:
            # Try parsing various formats
            for fmt in ['%B %d, %Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S']:
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(date[:20], fmt).strftime('%Y-%m-%d')
                    break
                except:
                    continue
            if not parsed_date:
                parsed_date = date[:10]  # First 10 chars fallback

        return {
            'title': title,
            'url': url,
            'date': parsed_date,
            'author': author,
            'content': content
        }


class ChatPRDScraper(AdvisorScraper):
    """Scraper for ChatPRD blog"""

    def extract_article_urls(self, archive_url):
        """Extract all ChatPRD blog URLs"""
        urls = []

        # ChatPRD blog structure
        response = self.fetch_page(archive_url)
        if not response:
            return urls

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all blog post links
        # (ChatPRD uses /blog/ and /how-i-ai/ patterns)
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/blog/' in href or '/how-i-ai/' in href:
                url = urljoin(self.base_url, href)
                if url not in urls and url != archive_url:
                    urls.append(url)

        return list(set(urls))  # Deduplicate

    def extract_article_content(self, url):
        """Extract ChatPRD article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title
        title = soup.find('h1')
        title = title.text.strip() if title else 'Untitled'

        # Date
        date_elem = soup.find('time') or soup.find('span', class_='date')
        date = date_elem.get('datetime', '') if date_elem else ''

        # Author
        author = 'Claire Vo'  # Default for ChatPRD

        # Main content
        article = soup.find('article') or soup.find('main')
        if article:
            content = md(str(article))
        else:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


class WaterAndMusicScraper(AdvisorScraper):
    """Scraper for Water & Music research platform (Cherie Hu)"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from Water & Music archive"""
        urls = []
        archive_page = urljoin(self.base_url, '/archive')

        response = self.fetch_page(archive_page)
        if not response:
            return urls

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all article links
        # Water & Music uses pattern: /<article-slug>
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Filter for article links (exclude nav, social, etc.)
            if href.startswith('/') and not href.startswith(('/archive', '/data', '/services', '/membership', '/event-recaps', '#')):
                # Skip common utility pages
                if href in ['/', '/about', '/contact', '/newsletter']:
                    continue
                url = urljoin(self.base_url, href)
                if url not in urls:
                    urls.append(url)

        return list(set(urls))  # Deduplicate

    def extract_article_content(self, url):
        """Extract Water & Music article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title - try multiple strategies
        title = None
        for selector in ['h1', 'title', '.post-title', '.article-title']:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                title = elem.text.strip()
                # Clean up if it's from <title> tag
                if ' | Water & Music' in title:
                    title = title.split(' | Water & Music')[0]
                break
        if not title:
            title = 'Untitled'

        # Date - try multiple strategies
        date = ''
        # Strategy 1: <time> element
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        # Strategy 2: meta tags
        if not date:
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                date = meta_date.get('content', '')

        # Author - Water & Music articles may have multiple authors
        author = 'Water & Music'  # Default
        author_elem = soup.find('span', class_='author') or soup.find('a', rel='author')
        if author_elem:
            author = author_elem.text.strip()
        # Check if Cherie Hu is mentioned
        if soup.find(string=lambda text: text and 'Cherie Hu' in text):
            author = 'Cherie Hu'

        # Main content - multiple fallback strategies
        content = None

        # Strategy 1: article tag
        article = soup.find('article')
        if article:
            content = md(str(article))

        # Strategy 2: main content div
        if not content or len(content) < 100:
            main = soup.find('main')
            if main:
                content = md(str(main))

        # Strategy 3: Find largest text block
        if not content or len(content) < 100:
            candidates = soup.find_all(['div', 'section'])
            max_length = 0
            best_candidate = None
            for candidate in candidates:
                text_length = len(candidate.get_text(strip=True))
                if text_length > max_length:
                    max_length = text_length
                    best_candidate = candidate
            if best_candidate and max_length > 500:
                content = md(str(best_candidate))

        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


class LevelsIOScraper(AdvisorScraper):
    """Scraper for levels.io blog (Pieter Levels)"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from levels.io/archive"""
        urls = []
        archive_page = urljoin(self.base_url, '/archive/')

        response = self.fetch_page(archive_page)
        if not response:
            return urls

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all article links (pattern: /[slug]/)
        for link in soup.find_all('a', href=True):
            href = link['href']
            # Filter for article links (starts with /, not external, not nav links)
            if href.startswith('/') and not href.startswith(('/archive', '/about', '#')) and href.endswith('/'):
                url = urljoin(self.base_url, href)
                if url not in urls:
                    urls.append(url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract levels.io article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title
        title = None
        for selector in ['h1', 'title', '.post-title']:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                title = elem.text.strip()
                # Clean up if from <title> tag
                if ' - levels.io' in title:
                    title = title.split(' - levels.io')[0]
                break
        if not title:
            title = 'Untitled'

        # Date
        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        # Fallback: meta tag
        if not date:
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                date = meta_date.get('content', '')

        # Author
        author = 'Pieter Levels'

        # Main content
        content = None
        # Strategy 1: article tag
        article = soup.find('article')
        if article:
            content = md(str(article))
        # Strategy 2: main content div
        if not content or len(content) < 100:
            main = soup.find('main') or soup.find('div', class_='post-content')
            if main:
                content = md(str(main))
        # Strategy 3: Find largest text block
        if not content or len(content) < 100:
            candidates = soup.find_all(['div', 'section'])
            max_length = 0
            best_candidate = None
            for candidate in candidates:
                text_length = len(candidate.get_text(strip=True))
                if text_length > max_length:
                    max_length = text_length
                    best_candidate = candidate
            if best_candidate and max_length > 500:
                content = md(str(best_candidate))

        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


class JustinWelshScraper(AdvisorScraper):
    """Scraper for Justin Welsh articles"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from justinwelsh.me"""
        urls = []
        articles_page = urljoin(self.base_url, '/articles')

        response = self.fetch_page(articles_page)
        if not response:
            return urls

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all article links (pattern: /article/[slug])
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/article/' in href:
                url = urljoin(self.base_url, href)
                if url not in urls:
                    urls.append(url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Justin Welsh article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title
        title = None
        for selector in ['h1', 'title']:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                title = elem.text.strip()
                if '|' in title:
                    title = title.split('|')[0].strip()
                break
        if not title:
            title = 'Untitled'

        # Date
        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())

        # Author
        author = 'Justin Welsh'

        # Main content
        content = None
        article = soup.find('article') or soup.find('main')
        if article:
            content = md(str(article))
        else:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


class SmallBetsScraper(AdvisorScraper):
    """Scraper for Small Bets newsletter (Daniel Vassallo - Substack)"""

    def extract_article_urls(self, archive_url):
        """Extract URLs from Small Bets Substack archive"""
        urls = []
        archive_page = urljoin(self.base_url, '/archive')

        response = self.fetch_page(archive_page)
        if not response:
            return urls

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all post links (Substack pattern: /p/[slug])
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/p/' in href:
                url = urljoin(self.base_url, href)
                if url not in urls:
                    urls.append(url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Small Bets newsletter content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title
        title = None
        for selector in ['h1.post-title', 'h1', 'title']:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                title = elem.text.strip()
                # Clean Substack title format
                if '|' in title:
                    title = title.split('|')[0].strip()
                break
        if not title:
            title = 'Untitled'

        # Date
        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())

        # Author
        author = 'Daniel Vassallo'

        # Main content (Substack structure)
        content = None
        # Substack uses specific class for post content
        post_content = soup.find('div', class_='available-content')
        if post_content:
            content = md(str(post_content))
        # Fallback: article tag
        if not content or len(content) < 100:
            article = soup.find('article')
            if article:
                content = md(str(article))

        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


def main():
    """CLI entry point"""
    if len(sys.argv) < 3:
        print("Usage: python scraper.py <source-type> <base-url> <output-dir>")
        print("\nSource types:")
        print("  beehiiv       - Beehiiv newsletters (Jesse Cannon, etc.)")
        print("  chatprd       - ChatPRD blog")
        print("  waterandmusic - Water & Music research platform (Cherie Hu)")
        print("  levelsio      - levels.io blog (Pieter Levels)")
        print("  justinwelsh   - Justin Welsh articles")
        print("  smallbets     - Small Bets newsletter (Daniel Vassallo)")
        print("\nExample:")
        print("  python scraper.py beehiiv https://musicmarketingtrends.beehiiv.com ~/Development/jesse-cannon")
        print("  python scraper.py levelsio https://levels.io ~/Development/indie-hackers/pieter-levels")
        sys.exit(1)

    source_type = sys.argv[1]
    base_url = sys.argv[2]
    output_dir = sys.argv[3]

    # Select scraper
    scrapers = {
        'beehiiv': BeehiivScraper,
        'chatprd': ChatPRDScraper,
        'waterandmusic': WaterAndMusicScraper,
        'levelsio': LevelsIOScraper,
        'justinwelsh': JustinWelshScraper,
        'smallbets': SmallBetsScraper,
    }

    if source_type not in scrapers:
        print(f"❌ Unknown source type: {source_type}")
        print(f"   Available: {', '.join(scrapers.keys())}")
        sys.exit(1)

    # Run scraper
    scraper = scrapers[source_type](base_url, output_dir)
    metadata = scraper.run()

    print(f"\n📊 Metadata saved to: {output_dir}/metadata/metadata.json")
    print(f"📋 Index saved to: {output_dir}/INDEX.md")


if __name__ == '__main__':
    main()
