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
                except (ValueError, TypeError):
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


class JNDScraper(AdvisorScraper):
    """Scraper for jnd.org (Don Norman essays/articles) - WordPress"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from jnd.org/essay-articles/ with pagination"""
        urls = []
        base_archive = archive_url.rstrip('/') + '/essay-articles/'
        page = 1
        max_pages = 30

        while page <= max_pages:
            page_url = f"{base_archive}page/{page}/" if page > 1 else base_archive
            print(f"   Checking page {page}...")

            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0

            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('https://jnd.org/') and href != 'https://jnd.org/' \
                   and '/essay-articles/' not in href and '/category/' not in href \
                   and '/tag/' not in href and '/page/' not in href \
                   and '/books/' not in href and '/videos/' not in href \
                   and '/about' not in href and '#' not in href \
                   and href not in urls:
                    # Check it looks like an article slug
                    path = urlparse(href).path.strip('/')
                    if path and '/' not in path:
                        urls.append(href)
                        found += 1

            if found == 0:
                break
            page += 1

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Don Norman article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title: use <title> tag and strip site suffix
        title = None
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.text.strip()
            # Strip common suffixes
            for suffix in [" – Don Norman's JND.org", " - Don Norman", " | jnd.org"]:
                if suffix in title:
                    title = title.split(suffix)[0].strip()
        if not title or title.lower() == 'jnd.org':
            title = 'Untitled'

        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        if not date:
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                date = meta_date.get('content', '')

        author = 'Don Norman'

        # Content: use editor-content div (JND-specific) then fallbacks
        content = None
        content_div = soup.find('div', class_='editor-content')
        if content_div:
            content = md(str(content_div))
        if not content:
            # Fallback: category-tab-content
            content_div = soup.find('div', class_='category-tab-content')
            if content_div:
                content = md(str(content_div))
        if not content:
            main = soup.find('main', class_='site-main')
            if main:
                content = md(str(main))
        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


class NNGroupScraper(AdvisorScraper):
    """Scraper for nngroup.com articles (Nielsen Norman Group)"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from nngroup.com/articles/ with pagination"""
        urls = []
        base_archive = 'https://www.nngroup.com/articles/'
        page = 1
        max_pages = 50

        while page <= max_pages:
            page_url = f"{base_archive}?page={page}" if page > 1 else base_archive
            print(f"   Checking page {page}...")

            response = self.fetch_page(page_url)
            if not response:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0

            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://www.nngroup.com', href)
                if '/articles/' in href and href != '/articles/' \
                   and '?page=' not in href and full_url not in urls:
                    path = urlparse(full_url).path
                    parts = [p for p in path.split('/') if p]
                    if len(parts) == 2 and parts[0] == 'articles':
                        urls.append(full_url)
                        found += 1

            if found == 0:
                break
            page += 1

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract NNGroup article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        title = None
        h1 = soup.find('h1')
        if h1:
            title = h1.text.strip()
        if not title:
            title = 'Untitled'

        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        if not date:
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                date = meta_date.get('content', '')

        author = 'Nielsen Norman Group'
        author_elem = soup.find('span', class_='article-author') or soup.find('a', rel='author')
        if author_elem:
            author = author_elem.text.strip()

        content = None
        article = soup.find('article')
        if article:
            content = md(str(article))
        if not content or len(content) < 100:
            main = soup.find('main')
            if main:
                content = md(str(main))
        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


class ValhallaScraper(AdvisorScraper):
    """Scraper for Valhalla DSP blog (Sean Costello)"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from valhalladsp.com/blog/"""
        urls = []
        page = 1
        max_pages = 20

        while page <= max_pages:
            page_url = f"{self.base_url}/blog/page/{page}/" if page > 1 else f"{self.base_url}/blog/"
            print(f"   Checking page {page}...")

            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0

            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'valhalladsp.com/' in href and '/blog/' not in href \
                   and '/category/' not in href and '/tag/' not in href \
                   and '/page/' not in href and '/author/' not in href \
                   and '#' not in href:
                    # Match date-based WordPress URLs: /YYYY/MM/DD/slug/
                    path = urlparse(href).path.strip('/')
                    parts = path.split('/')
                    if len(parts) >= 4:
                        try:
                            int(parts[0])  # year
                            int(parts[1])  # month
                            int(parts[2])  # day
                            if href not in urls:
                                urls.append(href)
                                found += 1
                        except (ValueError, IndexError):
                            pass

            if found == 0:
                break
            page += 1

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Valhalla DSP article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        title = None
        for selector in ['h1', 'h2.entry-title', 'h1.entry-title']:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                title = elem.text.strip()
                break
        if not title:
            title = 'Untitled'

        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        if not date:
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                date = meta_date.get('content', '')

        author = 'Sean Costello'

        content = None
        for cls in ['entry-content', 'post-content', 'hentry']:
            content_div = soup.find('div', class_=cls)
            if content_div:
                content = md(str(content_div))
                break
        if not content:
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


class KiloheartsScraper(AdvisorScraper):
    """Scraper for kilohearts.com/blog (plugin development + sound design)"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from kilohearts.com/blog - single page, all posts"""
        urls = []
        response = self.fetch_page(f"{self.base_url}/blog")
        if not response:
            return urls

        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('/blog/') and href != '/blog/' and href != '/blog':
                full_url = f"{self.base_url}{href}" if not href.startswith('http') else href
                if full_url not in urls:
                    urls.append(full_url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Kilohearts blog post content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        title = None
        for selector in ['h1', 'h2']:
            elem = soup.select_one(selector)
            if elem and elem.text.strip():
                title = elem.text.strip()
                break
        if not title:
            title = 'Untitled'

        date = ''
        meta_date = soup.find('meta', property='article:published_time')
        if meta_date:
            date = meta_date.get('content', '')
        if not date:
            time_elem = soup.find('time')
            if time_elem:
                date = time_elem.get('datetime', time_elem.text.strip())

        author = 'Kilohearts'

        content = None
        for cls in ['article-content', 'post-content', 'entry-content', 'blog-content']:
            content_div = soup.find('div', class_=cls)
            if content_div:
                content = md(str(content_div))
                break
        if not content:
            article = soup.find('article')
            if article:
                content = md(str(article))
        if not content:
            main = soup.find('main')
            if main:
                content = md(str(main))
        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


class AirwindowsScraper(AdvisorScraper):
    """Scraper for airwindows.com (Chris Johnson - open source plugins)"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from airwindows.com - WordPress with pagination"""
        urls = []
        page = 1
        max_pages = 100  # Large site, many posts

        while page <= max_pages:
            page_url = f"{self.base_url}/page/{page}/" if page > 1 else self.base_url
            print(f"   Checking page {page}...")

            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0

            # Airwindows uses h2 > a for post titles
            for h2 in soup.find_all('h2'):
                link = h2.find('a', href=True)
                if link:
                    href = link['href']
                    if 'airwindows.com/' in href and '/page/' not in href \
                       and '/category/' not in href and '/tag/' not in href \
                       and '#' not in href and href not in urls:
                        urls.append(href)
                        found += 1

            if found == 0:
                break
            page += 1

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Airwindows article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title: use <title> tag first (most reliable), strip site suffix
        title = None
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.text.strip()
            for suffix in [' | Airwindows', ' - Airwindows']:
                if suffix in title:
                    title = title.split(suffix)[0].strip()
        if not title or title.lower() in ['airwindows', '']:
            # Fallback: first h2 with a link
            h2 = soup.find('h2')
            if h2:
                title_link = h2.find('a')
                title = title_link.text.strip() if title_link else h2.text.strip()
        if not title:
            title = 'Untitled'

        # Date from metadata dl/dd/span list
        date = ''
        # Strategy 1: look for spans with date-like text
        for span in soup.find_all('span'):
            text = span.text.strip()
            if text and any(m in text for m in ['January', 'February', 'March', 'April',
                'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                if ',' in text and len(text) < 30:
                    date = text
                    break
        # Strategy 2: dl/dt/dd
        if not date:
            dt_elements = soup.find_all('dt')
            for dt in dt_elements:
                if 'Date' in dt.text:
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        date = dd.text.strip()
                        break
        if not date:
            time_elem = soup.find('time')
            if time_elem:
                date = time_elem.get('datetime', time_elem.text.strip())

        # Parse date
        parsed_date = ''
        if date:
            for fmt in ['%B %d, %Y', '%Y-%m-%d', '%b %d, %Y']:
                try:
                    parsed_date = datetime.strptime(date.strip(), fmt).strftime('%Y-%m-%d')
                    break
                except (ValueError, TypeError):
                    continue
            if not parsed_date:
                parsed_date = date[:10]

        author = 'Chris Johnson'

        # Extract content - stop before comments
        content = None
        for cls in ['entry-content', 'post-content']:
            content_div = soup.find('div', class_=cls)
            if content_div:
                content = md(str(content_div))
                break
        if not content:
            article = soup.find('article')
            if article:
                content = md(str(article))
        if not content:
            # Fallback: get all content between title and comments
            main = soup.find('main')
            if main:
                content = md(str(main))
        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': parsed_date,
            'author': author,
            'content': content
        }


class EFluxScraper(AdvisorScraper):
    """Scraper for e-flux Journal (art critical theory)"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from e-flux journal - issue-based"""
        urls = []

        # Scrape issues 1 through 160
        for issue_num in range(1, 161):
            issue_url = f"https://www.e-flux.com/journal/{issue_num}/"
            print(f"   Checking issue {issue_num}/160...")

            response = self.fetch_page(issue_url)
            if not response:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://www.e-flux.com', href)
                # Match pattern: /journal/NNN/NNNNNNN/slug
                if f'/journal/{issue_num}/' in full_url and full_url.count('/') >= 6:
                    path = urlparse(full_url).path.strip('/')
                    parts = path.split('/')
                    if len(parts) >= 3 and parts[0] == 'journal':
                        if full_url not in urls:
                            urls.append(full_url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract e-flux article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        title = None
        h1 = soup.find('h1', class_='article__header-title')
        if h1:
            title = h1.text.strip()
        if not title:
            h1 = soup.find('h1')
            if h1:
                title = h1.text.strip()
        if not title:
            title = 'Untitled'

        # Author
        author = 'e-flux'
        author_elem = soup.find('h2', class_='article__header-authors')
        if author_elem and author_elem.text.strip():
            author = author_elem.text.strip()

        # Date/Issue
        date = ''
        date_div = soup.find('div', class_='journalarticle__date')
        if date_div:
            date = date_div.text.strip()
        issue_div = soup.find('div', class_='journalarticle__issue')
        issue_info = issue_div.text.strip() if issue_div else ''

        # Content
        content = None
        body = soup.find('div', class_='article__body')
        if body:
            content = md(str(body))
        if not content:
            content_div = soup.find('div', class_='article__content')
            if content_div:
                content = md(str(content_div))
        if not content:
            article = soup.find('article')
            if article:
                content = md(str(article))
        if not content:
            content = "Content extraction failed"

        # Prepend issue info
        if issue_info:
            content = f"*{issue_info}*\n\n{content}"

        return {
            'title': title,
            'url': url,
            'date': date,
            'author': author,
            'content': content
        }


class HyperallegicScraper(AdvisorScraper):
    """Scraper for Hyperallergic (art criticism/news) - Ghost CMS"""

    def extract_article_urls(self, archive_url):
        """Extract article URLs from hyperallergic.com with pagination"""
        urls = []
        page = 1
        max_pages = 50  # ~500 articles

        while page <= max_pages:
            page_url = f"{self.base_url}/page/{page}/" if page > 1 else self.base_url
            print(f"   Checking page {page}...")

            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0

            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                # Skip tag, author, page links
                if 'hyperallergic.com/' in full_url \
                   and '/tag/' not in full_url \
                   and '/author/' not in full_url \
                   and '/page/' not in full_url \
                   and '#' not in full_url \
                   and full_url != self.base_url \
                   and full_url != self.base_url + '/':
                    path = urlparse(full_url).path.strip('/')
                    # Articles are slug-only (no nested paths)
                    if path and '/' not in path and len(path) > 5:
                        if full_url not in urls:
                            urls.append(full_url)
                            found += 1

            if found == 0:
                break
            page += 1

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Hyperallergic article content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        title = None
        h1 = soup.find('h1')
        if h1:
            title = h1.text.strip()
        if not title:
            title = 'Untitled'

        # Try JSON-LD structured data first
        date = ''
        author = 'Hyperallergic'
        script = soup.find('script', type='application/ld+json')
        if script:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                date = data.get('datePublished', '')[:10]
                author_data = data.get('author', {})
                if isinstance(author_data, dict):
                    author = author_data.get('name', author)
                elif isinstance(author_data, list) and author_data:
                    author = author_data[0].get('name', author)
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass

        if not date:
            time_elem = soup.find('time')
            if time_elem:
                date = time_elem.get('datetime', time_elem.text.strip())[:10]

        # Content - Ghost CMS uses gh-content class
        content = None
        for cls in ['gh-content', 'post-content', 'article-content', 'entry-content']:
            content_div = soup.find('div', class_=cls)
            if content_div:
                content = md(str(content_div))
                break
        if not content:
            article = soup.find('article')
            if article:
                content = md(str(article))
        if not content:
            main = soup.find('main')
            if main:
                content = md(str(main))
        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date,
            'author': author,
            'content': content
        }


class FabFilterScraper(AdvisorScraper):
    """Scraper for FabFilter Learn (audio education)"""

    def extract_article_urls(self, archive_url):
        """Extract tutorial URLs from fabfilter.com/learn - spider all categories"""
        urls = []
        categories = [
            'equalization', 'compression', 'reverb', 'mixing',
            'science-of-sound', 'synthesis-and-sound-design'
        ]

        # Spider each category page for article links
        for cat in categories:
            cat_url = f'https://www.fabfilter.com/learn/{cat}/'
            print(f"   Checking category: {cat}...")

            response = self.fetch_page(cat_url)
            if not response:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://www.fabfilter.com', href)
                if f'/learn/{cat}/' in full_url and full_url != cat_url:
                    path = urlparse(full_url).path.strip('/')
                    parts = [p for p in path.split('/') if p]
                    if len(parts) == 3 and parts[0] == 'learn':
                        if full_url not in urls:
                            urls.append(full_url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract FabFilter tutorial content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title: use <title> tag and strip site/prefix names
        title = None
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.text.strip()
            # Strip prefixes and suffixes
            for pattern in [' | FabFilter', ' - FabFilter']:
                if pattern in title:
                    title = title.split(pattern)[0].strip()
            # Strip "FabFilter Learn - Category - " prefix
            if title.startswith('FabFilter Learn'):
                parts = title.split(' - ')
                if len(parts) >= 3:
                    title = ' - '.join(parts[2:]).strip()
                elif len(parts) >= 2:
                    title = parts[-1].strip()
        if not title or title == 'FabFilter' or title == 'FabFilter Learn':
            # Try h2 elements (skip "menu" and category headers)
            for h2 in soup.find_all('h2'):
                text = h2.text.strip()
                if text.lower() not in ['menu', 'equalization', 'compression',
                    'reverb', 'mixing', 'science of sound', 'synthesis and sound design']:
                    title = text
                    break
        if not title:
            title = 'Untitled'

        # Category from URL
        path_parts = urlparse(url).path.strip('/').split('/')
        category = path_parts[1] if len(path_parts) >= 2 else 'general'

        author = 'FabFilter'
        date = ''

        # Content: use main-content div (FabFilter-specific)
        content = None
        content_div = soup.find('div', class_='main-content')
        if content_div:
            content = md(str(content_div))
        if not content:
            content_div = soup.find('div', class_='article-page')
            if content_div:
                content = md(str(content_div))
        if not content:
            main = soup.find('main')
            if main:
                content = md(str(main))
        if not content:
            content = "Content extraction failed"

        # Prepend category
        content = f"*Category: {category.replace('-', ' ').title()}*\n\n{content}"

        return {
            'title': title,
            'url': url,
            'date': date,
            'author': author,
            'content': content
        }


class CreativeCapitalScraper(AdvisorScraper):
    """Scraper for Creative Capital awardees (grant data for Atrium skill)"""

    def extract_article_urls(self, archive_url):
        """Extract awardee/event URLs from creative-capital.org"""
        urls = []

        # Try awardee index
        for page_path in ['/awardee-index/', '/explore-stories/', '/explore-stories/events/']:
            page_url = urljoin(self.base_url, page_path)
            print(f"   Checking {page_path}...")

            response = self.fetch_page(page_url)
            if not response:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                if 'creative-capital.org/' in full_url:
                    path = urlparse(full_url).path.strip('/')
                    # Match event or awardee pages
                    if path.startswith('events/') or path.startswith('awardees/') \
                       or path.startswith('projects/'):
                        if full_url not in urls:
                            urls.append(full_url)

        # Paginate through events
        page = 2
        max_pages = 20
        while page <= max_pages:
            page_url = f"{self.base_url}/explore-stories/events/page/{page}/"
            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                if 'creative-capital.org/events/' in full_url and full_url not in urls:
                    urls.append(full_url)
                    found += 1
            if found == 0:
                break
            page += 1

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Creative Capital awardee/event content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        title = None
        h1 = soup.find('h1')
        if h1:
            title = h1.text.strip()
        if not title:
            title = 'Untitled'

        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())

        author = 'Creative Capital'

        content = None
        article = soup.find('article')
        if article:
            content = md(str(article))
        if not content:
            main = soup.find('main')
            if main:
                content = md(str(main))
        if not content:
            # Largest text block fallback
            candidates = soup.find_all(['div', 'section'])
            max_length = 0
            best = None
            for c in candidates:
                length = len(c.get_text(strip=True))
                if length > max_length:
                    max_length = length
                    best = c
            if best and max_length > 200:
                content = md(str(best))
        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date[:10] if date else '',
            'author': author,
            'content': content
        }


class BaymardScraper(AdvisorScraper):
    """Scraper for Baymard Institute (e-commerce UX research) - single archive page"""

    def extract_article_urls(self, archive_url):
        urls = []
        response = self.fetch_page('https://baymard.com/blog/archive')
        if not response:
            return urls
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('/blog/') and href != '/blog/' and href != '/blog/archive':
                full_url = urljoin('https://baymard.com', href)
                if full_url not in urls:
                    urls.append(full_url)
        return list(set(urls))

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1')
        title = title.text.strip() if title else 'Untitled'
        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        if not date:
            meta = soup.find('meta', property='article:published_time')
            if meta: date = meta.get('content', '')
        author = 'Baymard Institute'
        content = None
        for cls in ['article-body', 'article__body', 'post-content', 'entry-content']:
            div = soup.find('div', class_=cls)
            if div:
                content = md(str(div))
                break
        if not content:
            article = soup.find('article')
            if article: content = md(str(article))
        if not content:
            main = soup.find('main')
            if main: content = md(str(main))
        if not content: content = "Content extraction failed"
        return {'title': title, 'url': url, 'date': date[:10] if date else '', 'author': author, 'content': content}


class LukeWScraper(AdvisorScraper):
    """Scraper for LukeW (lukew.com) - sequential entry IDs"""

    def extract_article_urls(self, archive_url):
        urls = []
        # Sequential IDs from 1 to ~2141
        for i in range(1, 2142):
            urls.append(f'https://www.lukew.com/ff/entry.asp?{i}')
        return urls

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1') or soup.find('h2')
        title = title.text.strip() if title else 'Untitled'
        if title == 'Untitled':
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text.strip()
                for suffix in [' | LukeW', ' - LukeW']:
                    if suffix in title: title = title.split(suffix)[0].strip()
        date = ''
        # Look for date patterns in the page
        for elem in soup.find_all(['span', 'p', 'div']):
            text = elem.text.strip()
            if len(text) < 30 and any(m in text for m in ['January','February','March','April','May','June','July','August','September','October','November','December']):
                if ',' in text:
                    date = text
                    break
        author = 'Luke Wroblewski'
        content = None
        # LukeW uses simple HTML structure
        main = soup.find('div', id='content') or soup.find('td', class_='bodytd')
        if main: content = md(str(main))
        if not content:
            article = soup.find('article') or soup.find('main')
            if article: content = md(str(article))
        if not content:
            # Largest text block
            candidates = soup.find_all(['div', 'td'])
            best, max_len = None, 0
            for c in candidates:
                l = len(c.get_text(strip=True))
                if l > max_len: max_len, best = l, c
            if best and max_len > 200: content = md(str(best))
        if not content: content = "Content extraction failed"
        parsed_date = ''
        if date:
            for fmt in ['%B %d, %Y', '%b %d, %Y', '%Y-%m-%d']:
                try:
                    parsed_date = datetime.strptime(date.strip(), fmt).strftime('%Y-%m-%d')
                    break
                except (ValueError, TypeError): continue
            if not parsed_date: parsed_date = date[:10]
        return {'title': title, 'url': url, 'date': parsed_date, 'author': author, 'content': content}


class LawsOfUXScraper(AdvisorScraper):
    """Scraper for Laws of UX (lawsofux.com) - 31 laws + articles"""

    def extract_article_urls(self, archive_url):
        urls = []
        response = self.fetch_page('https://lawsofux.com/')
        if not response:
            return urls
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin('https://lawsofux.com', href)
            path = urlparse(full_url).path.strip('/')
            if path and '/' not in path and path not in ['articles', 'about', 'book'] \
               and not path.startswith('http') and full_url not in urls:
                urls.append(full_url)
        # Also get articles
        response2 = self.fetch_page('https://lawsofux.com/articles/')
        if response2:
            soup2 = BeautifulSoup(response2.content, 'html.parser')
            for link in soup2.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://lawsofux.com', href)
                if '/articles/' in full_url and full_url.rstrip('/') != 'https://lawsofux.com/articles' \
                   and full_url not in urls:
                    urls.append(full_url)
        return list(set(urls))

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1')
        title = title.text.strip() if title else 'Untitled'
        author = 'Jon Yablonski'
        content = None
        main = soup.find('main') or soup.find('article')
        if main: content = md(str(main))
        if not content:
            candidates = soup.find_all(['div', 'section'])
            best, max_len = None, 0
            for c in candidates:
                l = len(c.get_text(strip=True))
                if l > max_len: max_len, best = l, c
            if best and max_len > 100: content = md(str(best))
        if not content: content = "Content extraction failed"
        return {'title': title, 'url': url, 'date': '', 'author': author, 'content': content}


class UXMythsScraper(AdvisorScraper):
    """Scraper for UX Myths (uxmyths.com) - Tumblr-based, 34 myths"""

    def extract_article_urls(self, archive_url):
        urls = []
        response = self.fetch_page('https://uxmyths.com/')
        if not response:
            return urls
        soup = BeautifulSoup(response.content, 'html.parser')
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/post/' in href:
                full_url = urljoin('https://uxmyths.com', href)
                if full_url not in urls:
                    urls.append(full_url)
        return list(set(urls))

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1') or soup.find('h2')
        title = title.text.strip() if title else 'Untitled'
        author = 'Zoltan Kollin'
        content = None
        post = soup.find('div', class_='post') or soup.find('article')
        if post: content = md(str(post))
        if not content:
            main = soup.find('main') or soup.find('body')
            if main: content = md(str(main))
        if not content: content = "Content extraction failed"
        return {'title': title, 'url': url, 'date': '', 'author': author, 'content': content}


class DeceptiveDesignScraper(AdvisorScraper):
    """Scraper for Deceptive Design (deceptive.design) - dark patterns"""

    def extract_article_urls(self, archive_url):
        urls = []
        # Get all 16 pattern type pages
        response = self.fetch_page('https://www.deceptive.design/types')
        if response:
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://www.deceptive.design', href)
                if '/types/' in full_url and full_url.rstrip('/') != 'https://www.deceptive.design/types':
                    if full_url not in urls:
                        urls.append(full_url)
        # Get reading list
        response2 = self.fetch_page('https://www.deceptive.design/reading-list')
        if response2:
            urls.append('https://www.deceptive.design/reading-list')
        # Get laws page
        response3 = self.fetch_page('https://www.deceptive.design/laws')
        if response3:
            urls.append('https://www.deceptive.design/laws')
        return list(set(urls))

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1')
        title = title.text.strip() if title else 'Untitled'
        author = 'Harry Brignull'
        content = None
        main = soup.find('main') or soup.find('article')
        if main: content = md(str(main))
        if not content:
            candidates = soup.find_all(['div', 'section'])
            best, max_len = None, 0
            for c in candidates:
                l = len(c.get_text(strip=True))
                if l > max_len: max_len, best = l, c
            if best and max_len > 100: content = md(str(best))
        if not content: content = "Content extraction failed"
        return {'title': title, 'url': url, 'date': '', 'author': author, 'content': content}


class AListApartScraper(AdvisorScraper):
    """Scraper for A List Apart (alistapart.com) - UX thought leadership"""

    def extract_article_urls(self, archive_url):
        urls = []
        page = 1
        max_pages = 40

        while page <= max_pages:
            page_url = f'https://alistapart.com/articles/page/{page}/' if page > 1 else 'https://alistapart.com/articles/'
            print(f"   Checking page {page}...")
            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break
            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://alistapart.com', href)
                if '/article/' in full_url and full_url not in urls:
                    urls.append(full_url)
                    found += 1
            if found == 0:
                break
            page += 1
        return list(set(urls))

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1')
        title = title.text.strip() if title else 'Untitled'
        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        author = 'A List Apart'
        author_elem = soup.find('a', rel='author') or soup.find('span', class_='author')
        if author_elem: author = author_elem.text.strip()
        content = None
        for cls in ['entry-content', 'article-content', 'post-content']:
            div = soup.find('div', class_=cls)
            if div:
                content = md(str(div))
                break
        if not content:
            article = soup.find('article')
            if article: content = md(str(article))
        if not content:
            main = soup.find('main')
            if main: content = md(str(main))
        if not content: content = "Content extraction failed"
        return {'title': title, 'url': url, 'date': date[:10] if date else '', 'author': author, 'content': content}


class SmashingMagScraper(AdvisorScraper):
    """Scraper for Smashing Magazine UX section"""

    def extract_article_urls(self, archive_url):
        urls = []
        page = 1
        max_pages = 10
        while page <= max_pages:
            page_url = f'https://www.smashingmagazine.com/category/ux-design/page/{page}/' if page > 1 \
                else 'https://www.smashingmagazine.com/category/ux-design/'
            print(f"   Checking page {page}...")
            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break
            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://www.smashingmagazine.com', href)
                path = urlparse(full_url).path.strip('/')
                parts = path.split('/')
                # Match /YYYY/MM/slug/ pattern
                if len(parts) == 3:
                    try:
                        int(parts[0])
                        int(parts[1])
                        if full_url not in urls:
                            urls.append(full_url)
                            found += 1
                    except ValueError:
                        pass
            if found == 0:
                break
            page += 1
        return list(set(urls))

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1')
        title = title.text.strip() if title else 'Untitled'
        date = ''
        time_elem = soup.find('time')
        if time_elem: date = time_elem.get('datetime', time_elem.text.strip())
        author = 'Smashing Magazine'
        author_elem = soup.find('a', rel='author')
        if author_elem: author = author_elem.text.strip()
        content = None
        div = soup.find('div', class_='c-garfield-the-cat')
        if div: content = md(str(div))
        if not content:
            article = soup.find('article')
            if article: content = md(str(article))
        if not content: content = "Content extraction failed"
        return {'title': title, 'url': url, 'date': date[:10] if date else '', 'author': author, 'content': content}


class BrandNewScraper(AdvisorScraper):
    """Scraper for Brand New / Under Consideration (brand identity critique)"""

    def extract_article_urls(self, archive_url):
        urls = set()
        base = 'https://www.underconsideration.com'
        # Step 1: Get all category pages from the /archives/complete page
        response = self.fetch_page(f'{base}/brandnew/archives/complete')
        if not response:
            return []
        soup = BeautifulSoup(response.content, 'html.parser')
        categories = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/category/industry/' in href:
                full = urljoin(base, href)
                if full not in categories:
                    categories.append(full)
        print(f"   Found {len(categories)} categories")
        # Step 2: Crawl each category to collect article .php links
        for i, cat_url in enumerate(categories):
            print(f"   Category {i+1}/{len(categories)}: {cat_url.split('/')[-1]}")
            resp = self.fetch_page(cat_url)
            if not resp:
                continue
            cat_soup = BeautifulSoup(resp.content, 'html.parser')
            for link in cat_soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(base, href)
                if '/brandnew/archives/' in full_url and full_url.endswith('.php') \
                   and '#' not in full_url:
                    urls.add(full_url)
            print(f"   Running total: {len(urls)} unique articles")
        # Step 3: Also grab from homepage for latest
        resp = self.fetch_page(f'{base}/brandnew/')
        if resp:
            home_soup = BeautifulSoup(resp.content, 'html.parser')
            for link in home_soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(base, href)
                if '/brandnew/archives/' in full_url and full_url.endswith('.php') \
                   and '#' not in full_url:
                    urls.add(full_url)
        return list(urls)

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1') or soup.find('h2', class_='entry-title')
        title = title.text.strip() if title else 'Untitled'
        date = ''
        time_elem = soup.find('time')
        if time_elem: date = time_elem.get('datetime', time_elem.text.strip())
        if not date:
            # Look for date in spans
            for span in soup.find_all('span', class_='posted-on'):
                date = span.text.strip()
                break
        author = 'Armin Vit'
        content = None
        for cls in ['entry-content', 'post-content']:
            div = soup.find('div', class_=cls)
            if div:
                content = md(str(div))
                break
        if not content:
            article = soup.find('article')
            if article: content = md(str(article))
        if not content: content = "Content extraction failed"
        parsed_date = ''
        if date:
            for fmt in ['%B %d, %Y', '%Y-%m-%d', '%b %d, %Y']:
                try:
                    parsed_date = datetime.strptime(date.strip(), fmt).strftime('%Y-%m-%d')
                    break
                except (ValueError, TypeError): continue
            if not parsed_date: parsed_date = date[:10]
        return {'title': title, 'url': url, 'date': parsed_date, 'author': author, 'content': content}


class DesignObserverScraper(AdvisorScraper):
    """Scraper for Design Observer (designobserver.com) - design criticism"""

    def extract_article_urls(self, archive_url):
        urls = []
        # Use RSS first for recent articles
        response = self.fetch_page('https://designobserver.com/feed/')
        if response:
            soup = BeautifulSoup(response.content, 'xml')
            for item in soup.find_all('item'):
                link = item.find('link')
                if link and link.text:
                    urls.append(link.text.strip())
        # Then crawl main page and feature pages
        for path in ['/', '/categories/', '/archives/']:
            page_url = urljoin('https://designobserver.com', path)
            response = self.fetch_page(page_url)
            if not response: continue
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://designobserver.com', href)
                if 'designobserver.com/feature/' in full_url and full_url not in urls:
                    urls.append(full_url)
        return list(set(urls))

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1')
        title = title.text.strip() if title else 'Untitled'
        date = ''
        time_elem = soup.find('time')
        if time_elem: date = time_elem.get('datetime', time_elem.text.strip())
        author = 'Design Observer'
        author_elem = soup.find('a', rel='author') or soup.find('span', class_='author')
        if author_elem: author = author_elem.text.strip()
        content = None
        article = soup.find('article') or soup.find('main')
        if article: content = md(str(article))
        if not content:
            candidates = soup.find_all(['div', 'section'])
            best, max_len = None, 0
            for c in candidates:
                l = len(c.get_text(strip=True))
                if l > max_len: max_len, best = l, c
            if best and max_len > 200: content = md(str(best))
        if not content: content = "Content extraction failed"
        return {'title': title, 'url': url, 'date': date[:10] if date else '', 'author': author, 'content': content}


class CreativeReviewScraper(AdvisorScraper):
    """Scraper for Creative Review (creativereview.co.uk) via RSS"""

    def extract_article_urls(self, archive_url):
        urls = []
        response = self.fetch_page('https://www.creativereview.co.uk/feed/')
        if response:
            soup = BeautifulSoup(response.content, 'xml')
            for item in soup.find_all('item'):
                link = item.find('link')
                if link and link.text:
                    urls.append(link.text.strip())
        # Also crawl main pages
        for page in range(1, 20):
            page_url = f'https://www.creativereview.co.uk/page/{page}/' if page > 1 \
                else 'https://www.creativereview.co.uk/'
            response = self.fetch_page(page_url)
            if not response or response.status_code == 404: break
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin('https://www.creativereview.co.uk', href)
                path = urlparse(full_url).path.strip('/')
                parts = path.split('/')
                # Match /YYYY/MM/DD/slug/ pattern
                if len(parts) >= 4:
                    try:
                        int(parts[0]); int(parts[1]); int(parts[2])
                        if full_url not in urls:
                            urls.append(full_url)
                    except ValueError: pass
        return list(set(urls))

    def extract_article_content(self, url):
        response = self.fetch_page(url)
        if not response:
            return None
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1')
        title = title.text.strip() if title else 'Untitled'
        date = ''
        time_elem = soup.find('time')
        if time_elem: date = time_elem.get('datetime', time_elem.text.strip())
        author = 'Creative Review'
        author_elem = soup.find('a', rel='author')
        if author_elem: author = author_elem.text.strip()
        content = None
        for cls in ['entry-content', 'article-content', 'post-content']:
            div = soup.find('div', class_=cls)
            if div:
                content = md(str(div))
                break
        if not content:
            article = soup.find('article')
            if article: content = md(str(article))
        if not content: content = "Content extraction failed"
        return {'title': title, 'url': url, 'date': date[:10] if date else '', 'author': author, 'content': content}


class EnoScraper(AdvisorScraper):
    """Scraper for moredarkthanshark.org (Brian Eno interviews archive)"""

    def __init__(self, base_url, output_dir, rate_limit=1.5):
        super().__init__(base_url, output_dir, rate_limit)

    def extract_article_urls(self, archive_url):
        """Extract interview URLs from moredarkthanshark.org main page"""
        urls = []
        response = self.fetch_page(self.base_url)
        if not response:
            return urls

        soup = BeautifulSoup(response.content, 'html.parser')

        # Main page has links to interview pages (plain HTML archive)
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(self.base_url, href)
            # Skip external links, anchors, and non-content pages
            if 'moredarkthanshark.org' not in full_url and not href.startswith('/'):
                continue
            full_url = urljoin(self.base_url, href)
            parsed = urlparse(full_url)
            # Only keep paths that look like content (HTML files or subpages)
            if parsed.path and parsed.path != '/' \
               and not parsed.path.endswith(('.jpg', '.png', '.gif', '.css', '.js')) \
               and '#' not in href \
               and 'mailto:' not in href \
               and full_url not in urls:
                # Filter for interview-like pages (skip index, about, etc.)
                path = parsed.path.strip('/')
                if path and path not in ['index.html', 'index.htm', 'links.html', 'links.htm']:
                    urls.append(full_url)

        # Also try known subpages that may contain interview links
        for subpage in ['interviews.html', 'interviews.htm', 'texts.html', 'texts.htm']:
            sub_url = urljoin(self.base_url, subpage)
            if sub_url in urls:
                continue
            response = self.fetch_page(sub_url)
            if not response:
                continue
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                if 'moredarkthanshark.org' in full_url or href.startswith('/') or not href.startswith('http'):
                    full_url = urljoin(self.base_url, href)
                    parsed = urlparse(full_url)
                    if parsed.path and parsed.path != '/' \
                       and not parsed.path.endswith(('.jpg', '.png', '.gif', '.css', '.js')) \
                       and '#' not in href \
                       and 'mailto:' not in href \
                       and full_url not in urls:
                        urls.append(full_url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract Brian Eno interview content from plain HTML pages"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title: try multiple strategies for old-school HTML
        title = None
        # Strategy 1: <title> tag
        title_tag = soup.find('title')
        if title_tag and title_tag.text.strip():
            title = title_tag.text.strip()
            # Clean common suffixes
            for suffix in [' - More Dark Than Shark', ' | More Dark Than Shark']:
                if suffix in title:
                    title = title.split(suffix)[0].strip()
        # Strategy 2: first h1 or h2
        if not title or title.lower() in ['', 'more dark than shark']:
            for tag in ['h1', 'h2', 'h3']:
                elem = soup.find(tag)
                if elem and elem.text.strip():
                    title = elem.text.strip()
                    break
        # Strategy 3: derive from URL
        if not title or title.lower() in ['', 'more dark than shark']:
            path = urlparse(url).path.strip('/')
            title = path.replace('.html', '').replace('.htm', '').replace('-', ' ').replace('_', ' ').title()
        if not title:
            title = 'Untitled'

        # Date: old HTML archives rarely have structured dates
        date = ''
        # Look for year mentions in the page
        import re
        for elem in soup.find_all(['p', 'span', 'div', 'i', 'em', 'b', 'strong']):
            text = elem.text.strip()
            if len(text) < 80:
                # Look for patterns like "1978", "January 1995", "Interview from 1983"
                year_match = re.search(r'\b(19[6-9]\d|20[0-2]\d)\b', text)
                if year_match and any(kw in text.lower() for kw in ['interview', 'published', 'date', 'year', 'from', ',']):
                    date = text
                    break

        author = 'Brian Eno'  # Default, interviews are about/with Eno

        # Content: plain HTML - use body or largest text block
        content = None
        # Strategy 1: <body> minus nav elements
        body = soup.find('body')
        if body:
            # Remove nav/header/footer if present
            for tag in body.find_all(['nav', 'header', 'footer']):
                tag.decompose()
            content = md(str(body))

        # Strategy 2: largest text block
        if not content or len(content) < 200:
            candidates = soup.find_all(['div', 'td', 'article', 'section', 'blockquote'])
            max_length = 0
            best_candidate = None
            for candidate in candidates:
                text_length = len(candidate.get_text(strip=True))
                if text_length > max_length:
                    max_length = text_length
                    best_candidate = candidate
            if best_candidate and max_length > 200:
                content = md(str(best_candidate))

        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date,
            'author': author,
            'content': content
        }


class CreativeIndependentScraper(AdvisorScraper):
    """Scraper for thecreativeindependent.com (1,000+ creative interviews)"""

    def __init__(self, base_url, output_dir, rate_limit=1.5):
        super().__init__(base_url, output_dir, rate_limit)

    def extract_article_urls(self, archive_url):
        """Extract interview URLs from The Creative Independent archive pages"""
        urls = []
        page = 1
        max_pages = 100  # Large archive, 1000+ interviews

        while page <= max_pages:
            if page == 1:
                page_url = f"{self.base_url}/people"
            else:
                page_url = f"{self.base_url}/people?page={page}"
            print(f"   Checking page {page}...")

            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0

            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                # Interview URLs pattern: /people/[slug]
                if '/people/' in full_url and full_url != f"{self.base_url}/people" \
                   and full_url != f"{self.base_url}/people/" \
                   and '?page=' not in full_url \
                   and '#' not in full_url \
                   and full_url not in urls:
                    path = urlparse(full_url).path.strip('/')
                    parts = path.split('/')
                    if len(parts) == 2 and parts[0] == 'people':
                        urls.append(full_url)
                        found += 1

            if found == 0:
                break
            page += 1

        # Also try /guides and /essays for additional content
        for section in ['/guides', '/essays']:
            section_url = f"{self.base_url}{section}"
            response = self.fetch_page(section_url)
            if not response:
                continue
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                if (f'{section}/' in full_url or '/people/' in full_url) \
                   and full_url not in urls \
                   and '#' not in full_url \
                   and '?page=' not in full_url:
                    path = urlparse(full_url).path.strip('/')
                    parts = path.split('/')
                    if len(parts) == 2:
                        urls.append(full_url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract The Creative Independent interview content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title
        title = None
        h1 = soup.find('h1')
        if h1:
            title = h1.text.strip()
        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text.strip()
                for suffix in [' | The Creative Independent', ' — The Creative Independent',
                               ' - The Creative Independent']:
                    if suffix in title:
                        title = title.split(suffix)[0].strip()
        if not title:
            title = 'Untitled'

        # Date
        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        if not date:
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                date = meta_date.get('content', '')

        # Author / Interviewee
        author = 'The Creative Independent'
        # Try to extract from meta or byline
        meta_author = soup.find('meta', attrs={'name': 'author'})
        if meta_author:
            author = meta_author.get('content', author)
        # Check for byline element
        byline = soup.find('span', class_='byline') or soup.find('div', class_='byline') \
                 or soup.find('p', class_='byline')
        if byline:
            author = byline.text.strip()

        # Content
        content = None
        # Strategy 1: interview/article body div
        for cls in ['interview-body', 'article-body', 'entry-content',
                     'post-content', 'guide-body', 'essay-body']:
            content_div = soup.find('div', class_=cls)
            if content_div:
                content = md(str(content_div))
                break
        # Strategy 2: article tag
        if not content or len(content) < 200:
            article = soup.find('article')
            if article:
                content = md(str(article))
        # Strategy 3: main tag
        if not content or len(content) < 200:
            main = soup.find('main')
            if main:
                content = md(str(main))
        # Strategy 4: largest text block
        if not content or len(content) < 200:
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


class LynchNetScraper(AdvisorScraper):
    """Scraper for lynchnet.com (David Lynch interviews archive)"""

    def __init__(self, base_url, output_dir, rate_limit=1.5):
        super().__init__(base_url, output_dir, rate_limit)

    def extract_article_urls(self, archive_url):
        """Extract interview URLs from lynchnet.com"""
        urls = []

        # Start with the main page and known sections
        pages_to_crawl = [
            self.base_url,
            urljoin(self.base_url, '/lif/'),
            urljoin(self.base_url, '/lif/lif.html'),
        ]

        visited = set()

        for page_url in pages_to_crawl:
            if page_url in visited:
                continue
            visited.add(page_url)

            response = self.fetch_page(page_url)
            if not response:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(page_url, href)
                parsed = urlparse(full_url)

                # Only keep lynchnet.com URLs
                if 'lynchnet.com' not in parsed.netloc and parsed.netloc != '':
                    continue

                full_url = urljoin(self.base_url, parsed.path)

                # Skip non-content files
                if parsed.path.endswith(('.jpg', '.png', '.gif', '.css', '.js', '.ico')):
                    continue
                if '#' in href or 'mailto:' in href:
                    continue
                if parsed.path in ['/', '', '/index.html', '/index.htm']:
                    continue

                # Keep HTML pages that look like interviews
                path = parsed.path.strip('/')
                if path and full_url not in urls:
                    # Add interview-like pages
                    if any(kw in path.lower() for kw in ['lif/', 'interview', 'press', 'article']):
                        urls.append(full_url)
                    # Also add HTML files in subdirectories
                    elif path.endswith(('.html', '.htm')):
                        urls.append(full_url)

        # Second pass: crawl discovered interview index pages for deeper links
        interview_indexes = [u for u in urls if any(kw in u.lower() for kw in ['index', 'lif.html', 'lif/'])]
        for idx_url in interview_indexes[:5]:  # Limit to prevent infinite crawl
            if idx_url in visited:
                continue
            visited.add(idx_url)
            response = self.fetch_page(idx_url)
            if not response:
                continue
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(idx_url, href)
                parsed = urlparse(full_url)
                if parsed.path.endswith(('.jpg', '.png', '.gif', '.css', '.js', '.ico')):
                    continue
                if '#' in href or 'mailto:' in href:
                    continue
                full_url = urljoin(self.base_url, parsed.path)
                if full_url not in urls and parsed.path.strip('/'):
                    urls.append(full_url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract David Lynch interview content from plain HTML"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title
        title = None
        title_tag = soup.find('title')
        if title_tag and title_tag.text.strip():
            title = title_tag.text.strip()
            for suffix in [' - LynchNet', ' | LynchNet', ' - Lynch Net']:
                if suffix in title:
                    title = title.split(suffix)[0].strip()
        if not title or title.lower() in ['', 'lynchnet', 'lynch net']:
            for tag in ['h1', 'h2', 'h3']:
                elem = soup.find(tag)
                if elem and elem.text.strip():
                    title = elem.text.strip()
                    break
        if not title:
            path = urlparse(url).path.strip('/')
            title = path.replace('.html', '').replace('.htm', '').replace('/', ' - ').replace('-', ' ').replace('_', ' ').title()
        if not title:
            title = 'Untitled'

        # Date: look for year mentions in old HTML
        date = ''
        import re
        for elem in soup.find_all(['p', 'span', 'div', 'i', 'em', 'b', 'strong', 'font']):
            text = elem.text.strip()
            if len(text) < 80:
                year_match = re.search(r'\b(19[6-9]\d|20[0-2]\d)\b', text)
                if year_match and any(kw in text.lower() for kw in ['interview', 'published', 'date', 'from', ',']):
                    date = text
                    break

        author = 'David Lynch'

        # Content: plain HTML
        content = None
        body = soup.find('body')
        if body:
            # Remove nav elements if present
            for tag in body.find_all(['nav', 'header', 'footer', 'script', 'style']):
                tag.decompose()
            content = md(str(body))

        if not content or len(content) < 200:
            candidates = soup.find_all(['div', 'td', 'article', 'section', 'blockquote'])
            max_length = 0
            best_candidate = None
            for candidate in candidates:
                text_length = len(candidate.get_text(strip=True))
                if text_length > max_length:
                    max_length = text_length
                    best_candidate = candidate
            if best_candidate and max_length > 200:
                content = md(str(best_candidate))

        if not content:
            content = "Content extraction failed"

        return {
            'title': title,
            'url': url,
            'date': date,
            'author': author,
            'content': content
        }


class BombMagazineScraper(AdvisorScraper):
    """Scraper for bombmagazine.org (interviews section, paginated)"""

    def __init__(self, base_url, output_dir, rate_limit=1.5):
        super().__init__(base_url, output_dir, rate_limit)

    def extract_article_urls(self, archive_url):
        """Extract interview URLs from BOMB Magazine interviews section"""
        urls = []
        page = 1
        max_pages = 80  # BOMB has a deep archive

        while page <= max_pages:
            if page == 1:
                page_url = f"{self.base_url}/interviews"
            else:
                page_url = f"{self.base_url}/interviews?page={page}"
            print(f"   Checking page {page}...")

            response = self.fetch_page(page_url)
            if not response or response.status_code == 404:
                break

            soup = BeautifulSoup(response.content, 'html.parser')
            found = 0

            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                # Interview articles pattern: /articles/[slug] or /[slug]
                if 'bombmagazine.org' in full_url or href.startswith('/'):
                    full_url = urljoin(self.base_url, href)
                    parsed = urlparse(full_url)
                    path = parsed.path.strip('/')

                    # Match article paths (skip nav, tags, categories)
                    if path.startswith('articles/') and len(path.split('/')) == 2:
                        if full_url not in urls and '#' not in href:
                            urls.append(full_url)
                            found += 1

            if found == 0:
                break
            page += 1

        # Also try direct archive sections
        for section_path in ['/interviews/', '/articles/']:
            section_url = urljoin(self.base_url, section_path)
            response = self.fetch_page(section_url)
            if not response:
                continue
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                parsed = urlparse(full_url)
                path = parsed.path.strip('/')
                if path.startswith('articles/') and len(path.split('/')) == 2 \
                   and full_url not in urls and '#' not in href:
                    urls.append(full_url)

        return list(set(urls))

    def extract_article_content(self, url):
        """Extract BOMB Magazine interview content"""
        response = self.fetch_page(url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Title
        title = None
        h1 = soup.find('h1')
        if h1:
            title = h1.text.strip()
        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text.strip()
                for suffix in [' - BOMB Magazine', ' | BOMB Magazine', ' - BOMB', ' | BOMB']:
                    if suffix in title:
                        title = title.split(suffix)[0].strip()
        if not title:
            title = 'Untitled'

        # Date
        date = ''
        time_elem = soup.find('time')
        if time_elem:
            date = time_elem.get('datetime', time_elem.text.strip())
        if not date:
            meta_date = soup.find('meta', property='article:published_time')
            if meta_date:
                date = meta_date.get('content', '')
        # BOMB often shows issue number/season, try to find that
        if not date:
            for elem in soup.find_all(['span', 'div', 'p']):
                text = elem.text.strip()
                if len(text) < 60 and ('BOMB' in text or 'Issue' in text or 'No.' in text):
                    import re
                    if re.search(r'\b(19[89]\d|20[0-2]\d)\b', text):
                        date = text
                        break

        # Author - BOMB interviews typically list both interviewer and interviewee
        author = 'BOMB Magazine'
        # Try JSON-LD
        script = soup.find('script', type='application/ld+json')
        if script:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                author_data = data.get('author', {})
                if isinstance(author_data, dict):
                    author = author_data.get('name', author)
                elif isinstance(author_data, list) and author_data:
                    author = ', '.join(a.get('name', '') for a in author_data if a.get('name'))
            except (json.JSONDecodeError, AttributeError, TypeError):
                pass
        # Fallback: look for author elements
        if author == 'BOMB Magazine':
            author_elem = soup.find('a', rel='author') or soup.find('span', class_='author') \
                          or soup.find('div', class_='author')
            if author_elem:
                author = author_elem.text.strip()

        # Content
        content = None
        # Strategy 1: article body classes
        for cls in ['article-body', 'article__body', 'article-content',
                     'entry-content', 'post-content', 'interview-body']:
            content_div = soup.find('div', class_=cls)
            if content_div:
                content = md(str(content_div))
                break
        # Strategy 2: article tag
        if not content or len(content) < 200:
            article = soup.find('article')
            if article:
                content = md(str(article))
        # Strategy 3: main tag
        if not content or len(content) < 200:
            main = soup.find('main')
            if main:
                content = md(str(main))
        # Strategy 4: largest text block
        if not content or len(content) < 200:
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


def main():
    """CLI entry point"""
    if len(sys.argv) < 3:
        print("Usage: python scraper.py <source-type> <base-url> <output-dir>")
        print("\nSource types:")
        print("  beehiiv          - Beehiiv newsletters (Jesse Cannon, etc.)")
        print("  chatprd          - ChatPRD blog")
        print("  waterandmusic    - Water & Music research platform (Cherie Hu)")
        print("  levelsio         - levels.io blog (Pieter Levels)")
        print("  justinwelsh      - Justin Welsh articles")
        print("  smallbets        - Small Bets newsletter (Daniel Vassallo)")
        print("  jnd              - Don Norman essays (jnd.org)")
        print("  nngroup          - Nielsen Norman Group articles")
        print("  valhalla         - Valhalla DSP blog (Sean Costello)")
        print("  airwindows       - Airwindows plugins blog (Chris Johnson)")
        print("  eflux            - e-flux Journal (art critical theory)")
        print("  hyperallergic    - Hyperallergic (art criticism)")
        print("  fabfilter        - FabFilter Learn (audio education)")
        print("  creativecapital  - Creative Capital awardees (grants)")
        print("  baymard          - Baymard Institute (e-commerce UX)")
        print("  lukew            - LukeW (mobile/forms UX pioneer)")
        print("  lawsofux         - Laws of UX (UX psychology principles)")
        print("  uxmyths          - UX Myths (myth-busting)")
        print("  deceptive        - Deceptive Design (dark patterns)")
        print("  alistapart       - A List Apart (UX thought leadership)")
        print("  smashingmag      - Smashing Magazine (UX section)")
        print("  brandnew         - Brand New (brand identity critique)")
        print("  designobserver   - Design Observer (design criticism)")
        print("  creativereview   - Creative Review (advertising/branding)")
        print("  eno              - Brian Eno interviews (moredarkthanshark.org)")
        print("  creative-independent - The Creative Independent (1,000+ interviews)")
        print("  lynchnet         - David Lynch interviews (lynchnet.com)")
        print("  bomb-magazine    - BOMB Magazine interviews (bombmagazine.org)")
        print("\nExample:")
        print("  python scraper.py beehiiv https://musicmarketingtrends.beehiiv.com ~/Development/jesse-cannon")
        print("  python scraper.py valhalla https://valhalladsp.com ~/Development/valhalla-dsp")
        print("  python scraper.py eflux https://www.e-flux.com ~/Development/e-flux-journal")
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
        'jnd': JNDScraper,
        'nngroup': NNGroupScraper,
        'valhalla': ValhallaScraper,
        'airwindows': AirwindowsScraper,
        'eflux': EFluxScraper,
        'hyperallergic': HyperallegicScraper,
        'fabfilter': FabFilterScraper,
        'creativecapital': CreativeCapitalScraper,
        # UX Frontier sources
        'baymard': BaymardScraper,
        'lukew': LukeWScraper,
        'lawsofux': LawsOfUXScraper,
        'uxmyths': UXMythsScraper,
        'deceptive': DeceptiveDesignScraper,
        'alistapart': AListApartScraper,
        'smashingmag': SmashingMagScraper,
        # Art Director sources
        'brandnew': BrandNewScraper,
        'designobserver': DesignObserverScraper,
        'creativereview': CreativeReviewScraper,
        # Plugin dev blogs
        'kilohearts': KiloheartsScraper,
        # Creative interview sources
        'eno': EnoScraper,
        'creative-independent': CreativeIndependentScraper,
        'lynchnet': LynchNetScraper,
        'bomb-magazine': BombMagazineScraper,
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
