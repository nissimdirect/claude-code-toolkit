#!/usr/bin/env python3
"""
Plugin Documentation Scraper
Extracts technical docs, product catalogs, and developer resources from plugin companies
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

class PluginDocScraper:
    def __init__(self, company_name, base_url, output_dir, rate_limit=2.0):
        """
        Args:
            company_name: Name of plugin company (e.g., "FabFilter", "Valhalla DSP")
            base_url: Company website URL
            output_dir: Where to save markdown files
            rate_limit: Seconds between requests (default 2.0 to be respectful)
        """
        self.company_name = company_name
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        # Create directory structure
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / 'products').mkdir(exist_ok=True)
        (self.output_dir / 'documentation').mkdir(exist_ok=True)
        (self.output_dir / 'metadata').mkdir(exist_ok=True)

        self.products = []
        self.docs = []
        self.errors = []

    def fetch_page(self, url, retry=3):
        """Fetch page with retry logic"""
        for attempt in range(retry):
            try:
                time.sleep(self.rate_limit)
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt == retry - 1:
                    self.errors.append({'url': url, 'error': str(e)})
                    return None
                time.sleep(2 ** attempt)
        return None

    def find_products_page(self):
        """Find the products/plugins page - multiple strategies"""
        common_paths = [
            '/products', '/plugins', '/shop', '/store',
            '/products.html', '/plugins.html',
            '/all-products', '/all-plugins'
        ]

        for path in common_paths:
            url = urljoin(self.base_url, path)
            response = self.fetch_page(url)
            if response and response.status_code == 200:
                print(f"   ✅ Found products page: {url}")
                return url

        # Fallback: try homepage
        print(f"   ⚠️  No dedicated products page found, using homepage")
        return self.base_url

    def extract_product_list(self, products_url):
        """Extract all products from products page"""
        response = self.fetch_page(products_url)
        if not response:
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        products = []

        # Strategy 1: Find links with "product" or "plugin" in href
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)

            # Filter for product links
            if any(keyword in href.lower() for keyword in ['product', 'plugin', '/p/', 'shop']):
                if text and len(text) > 2:  # Avoid empty or single-char links
                    product_url = urljoin(self.base_url, href)
                    products.append({
                        'name': text,
                        'url': product_url,
                        'href': href
                    })

        # Strategy 2: Look for common product container classes
        for container_class in ['product-card', 'plugin-card', 'product-item', 'shop-item']:
            containers = soup.find_all(class_=lambda x: x and container_class in x)
            for container in containers:
                link = container.find('a')
                if link:
                    product_url = urljoin(self.base_url, link['href'])
                    name = container.find(['h2', 'h3', 'h4'])
                    if name:
                        products.append({
                            'name': name.get_text(strip=True),
                            'url': product_url,
                            'href': link['href']
                        })

        # Deduplicate by URL
        seen_urls = set()
        unique_products = []
        for product in products:
            if product['url'] not in seen_urls:
                seen_urls.add(product['url'])
                unique_products.append(product)

        return unique_products

    def extract_product_details(self, product_url, product_name):
        """Extract detailed info from product page"""
        response = self.fetch_page(product_url)
        if not response:
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract key information
        details = {
            'name': product_name,
            'url': product_url,
            'scraped_at': datetime.now().isoformat()
        }

        # Price (multiple strategies)
        price_patterns = ['price', 'cost', 'buy']
        for pattern in price_patterns:
            price_elem = soup.find(class_=lambda x: x and pattern in x.lower())
            if not price_elem:
                price_elem = soup.find(string=lambda x: x and '$' in str(x) and 'USD' in str(x))
            if price_elem:
                details['price'] = price_elem.get_text(strip=True)
                break

        # Description
        desc_elem = soup.find('meta', attrs={'name': 'description'})
        if desc_elem:
            details['description'] = desc_elem.get('content', '')

        # Main content - convert to markdown
        main_content = soup.find('main') or soup.find('article') or soup.find(id='content')
        if main_content:
            details['content_markdown'] = md(str(main_content))
        else:
            # Fallback: find largest text container
            candidates = soup.find_all(['div', 'section'])
            max_length = 0
            best_candidate = None
            for candidate in candidates:
                text_length = len(candidate.get_text(strip=True))
                if text_length > max_length:
                    max_length = text_length
                    best_candidate = candidate
            if best_candidate and max_length > 200:
                details['content_markdown'] = md(str(best_candidate))

        # Features (look for lists)
        features = []
        feature_sections = soup.find_all(['ul', 'ol'])
        for section in feature_sections[:3]:  # Top 3 lists
            items = section.find_all('li')
            for item in items:
                text = item.get_text(strip=True)
                if text and len(text) > 10:
                    features.append(text)
        if features:
            details['features'] = features[:15]  # Limit to 15

        # Technical specs (look for tables)
        specs_table = soup.find('table')
        if specs_table:
            specs = {}
            rows = specs_table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    specs[key] = value
            if specs:
                details['technical_specs'] = specs

        return details

    def find_documentation_links(self):
        """Find documentation, developer, support pages"""
        doc_keywords = [
            '/documentation', '/docs', '/manual', '/guide', '/support',
            '/developers', '/dev', '/api', '/resources', '/help'
        ]

        doc_urls = []

        # Check homepage for doc links
        response = self.fetch_page(self.base_url)
        if response:
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                if any(keyword in href for keyword in doc_keywords):
                    doc_urls.append(urljoin(self.base_url, link['href']))

        # Also try direct URLs
        for keyword in doc_keywords[:5]:  # Top 5
            url = urljoin(self.base_url, keyword)
            response = self.fetch_page(url)
            if response and response.status_code == 200:
                doc_urls.append(url)

        return list(set(doc_urls))

    def save_product(self, product_details):
        """Save product information as markdown"""
        slug = self.slugify(product_details['name'])
        filename = f"products/{slug}.md"
        filepath = self.output_dir / filename

        # Build markdown content
        content = f"""# {product_details['name']}

**Company:** {self.company_name}
**URL:** {product_details['url']}
**Scraped:** {product_details['scraped_at']}

---

## Overview

"""

        if 'description' in product_details:
            content += f"{product_details['description']}\n\n"

        if 'price' in product_details:
            content += f"**Price:** {product_details['price']}\n\n"

        if 'features' in product_details:
            content += "## Features\n\n"
            for feature in product_details['features']:
                content += f"- {feature}\n"
            content += "\n"

        if 'technical_specs' in product_details:
            content += "## Technical Specifications\n\n"
            for key, value in product_details['technical_specs'].items():
                content += f"- **{key}:** {value}\n"
            content += "\n"

        if 'content_markdown' in product_details:
            content += "## Full Documentation\n\n"
            content += product_details['content_markdown']
            content += "\n"

        filepath.write_text(content, encoding='utf-8')

        # Update products list
        product_details['file'] = str(filename)
        self.products.append(product_details)

        return filepath

    def save_metadata(self):
        """Save metadata.json and INDEX.md"""
        metadata = {
            'company': self.company_name,
            'base_url': self.base_url,
            'scraped_at': datetime.now().isoformat(),
            'total_products': len(self.products),
            'total_docs': len(self.docs),
            'errors': len(self.errors),
            'products': self.products,
            'docs': self.docs
        }

        # Save JSON
        json_path = self.output_dir / 'metadata' / 'metadata.json'
        json_path.write_text(json.dumps(metadata, indent=2), encoding='utf-8')

        # Create INDEX
        index_content = f"""# {self.company_name} - Plugin Documentation

**Website:** {self.base_url}
**Scraped:** {datetime.now().strftime('%Y-%m-%d')}
**Products Found:** {len(self.products)}
**Documentation Pages:** {len(self.docs)}
**Errors:** {len(self.errors)}

---

## Products

"""

        for product in self.products:
            index_content += f"- [{product['name']}]({product['file']})"
            if 'price' in product:
                index_content += f" - {product['price']}"
            index_content += "\n"

        if self.docs:
            index_content += "\n## Documentation\n\n"
            for doc in self.docs:
                index_content += f"- [{doc['title']}]({doc['file']})\n"

        if self.errors:
            index_content += f"\n## Errors ({len(self.errors)})\n\n"
            for error in self.errors[:10]:
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
        return text[:50]

    def run(self):
        """Main scraping workflow"""
        print(f"\n🕷️  Scraping {self.company_name}")
        print(f"🌐 URL: {self.base_url}")
        print(f"📁 Output: {self.output_dir}")

        # Find products page
        print("\n1️⃣  Finding products page...")
        products_url = self.find_products_page()

        # Extract product list
        print("\n2️⃣  Extracting product list...")
        product_list = self.extract_product_list(products_url)
        print(f"   Found {len(product_list)} products")

        # Scrape each product
        print("\n3️⃣  Scraping product details...")
        for i, product in enumerate(product_list, 1):
            print(f"   [{i}/{len(product_list)}] {product['name']}")
            details = self.extract_product_details(product['url'], product['name'])
            if details:
                self.save_product(details)

        # Find documentation
        print("\n4️⃣  Finding documentation pages...")
        doc_urls = self.find_documentation_links()
        print(f"   Found {len(doc_urls)} documentation URLs")

        # Save metadata
        print("\n5️⃣  Saving metadata...")
        metadata = self.save_metadata()

        # Report
        print(f"\n✅ Complete!")
        print(f"   Products: {len(self.products)}")
        print(f"   Docs: {len(self.docs)}")
        print(f"   Errors: {len(self.errors)}")

        return metadata


def main():
    """CLI entry point"""
    if len(sys.argv) < 4:
        print("Usage: python plugin_doc_scraper.py <company_name> <base_url> <output_dir>")
        print("\nExample:")
        print('  python plugin_doc_scraper.py "FabFilter" https://www.fabfilter.com ~/Documents/Obsidian/VST-Research/FabFilter')
        print('  python plugin_doc_scraper.py "Valhalla DSP" https://valhalladsp.com ~/Documents/Obsidian/VST-Research/Valhalla-DSP')
        sys.exit(1)

    company_name = sys.argv[1]
    base_url = sys.argv[2]
    output_dir = sys.argv[3]

    scraper = PluginDocScraper(company_name, base_url, output_dir)
    metadata = scraper.run()

    print(f"\n📊 Metadata: {output_dir}/metadata/metadata.json")
    print(f"📋 Index: {output_dir}/INDEX.md")


if __name__ == '__main__':
    main()
