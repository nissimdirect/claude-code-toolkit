#!/usr/bin/env python3
"""Test Obsidian scraper with 5 sample URLs"""
import re
import requests

BASE_URL = "https://help.obsidian.md"
PUBLISH_BASE = "https://publish-01.obsidian.md/access/f786db9fac45774fa4f0d8112e232d67"

# Test 5 URLs (mix of working and previously failed)
test_urls = [
    f"{BASE_URL}/Home",
    f"{BASE_URL}/Editing+and+formatting/HTML+content",
    f"{BASE_URL}/vault",  # Failed before (maps to Getting started/Create a vault.md)
    f"{BASE_URL}/properties",  # Failed before
    f"{BASE_URL}/plugins/properties"  # Failed before
]

print("Testing Obsidian scraper approach on 5 URLs\n")
print("="*60)

success_count = 0
fail_count = 0

for url in test_urls:
    print(f"\n[TEST] {url}")

    # Step 1: Fetch HTML and extract markdown path
    try:
        html_response = requests.get(url, timeout=10)
        html_response.raise_for_status()

        # Extract preloadPage path from JavaScript
        match = re.search(r'window\.preloadPage=f\("([^"]+)"\)', html_response.text)

        if not match:
            print(f"  ❌ Could not find preloadPage in HTML")
            fail_count += 1
            continue

        markdown_url = match.group(1)
        print(f"  📍 Markdown path: {markdown_url}")

        # Step 2: Fetch actual markdown
        md_response = requests.get(markdown_url, timeout=10)
        md_response.raise_for_status()

        content = md_response.text

        if "## Not Found" in content:
            print(f"  ❌ 404 - File does not exist")
            fail_count += 1
        else:
            # Check for YAML frontmatter
            has_yaml = content.strip().startswith("---")
            content_preview = content[:200].replace("\n", " ")

            print(f"  ✅ SUCCESS")
            print(f"     YAML: {'Yes' if has_yaml else 'No'}")
            print(f"     Preview: {content_preview}...")
            success_count += 1

    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        fail_count += 1

print("\n" + "="*60)
print(f"\nRESULTS:")
print(f"  Success: {success_count}/{len(test_urls)} ({success_count/len(test_urls)*100:.0f}%)")
print(f"  Failed:  {fail_count}/{len(test_urls)}")

if success_count >= 4:  # 80% threshold
    print(f"\n✅ SUCCESS RATE >80% - Safe to build full scraper")
else:
    print(f"\n⚠️  SUCCESS RATE <80% - Investigate further")
