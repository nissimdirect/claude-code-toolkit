#!/usr/bin/env python3
"""Offline test: forge scrapers must skip URLs already saved in articles/.

Run: python3 -I ~/Development/tools/tests/test_forge_dedup.py
Third-party deps (requests/bs4/markdownify) are stubbed; no network.
"""

import sys
import json
import tempfile
import types
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent

# Stub third-party modules before importing scraper.
_req = types.ModuleType("requests")
_req.RequestException = Exception


class _Session:
    def __init__(self):
        self.headers = {}

    def get(self, *a, **k):
        raise AssertionError("network fetch attempted in offline test")


_req.Session = _Session
sys.modules.setdefault("requests", _req)
_bs4 = types.ModuleType("bs4")
_bs4.BeautifulSoup = object
sys.modules.setdefault("bs4", _bs4)
_mdf = types.ModuleType("markdownify")
_mdf.markdownify = lambda s, **k: s
sys.modules.setdefault("markdownify", _mdf)
# Keep the real sanitizer out so the test doesn't depend on it.
sys.modules["content_sanitizer"] = None

sys.path.insert(0, str(TOOLS))
import scraper  # noqa: E402

EXISTING = [
    "https://alistapart.com/article/one/",
    "https://alistapart.com/article/two",
    "https://www.alistapart.com/article/three/",
]
FETCHED = [
    "https://alistapart.com/article/one",  # no trailing slash
    "HTTPS://AListApart.com/article/two/",  # case + slash
    "https://alistapart.com/article/three/",  # www dropped
    "https://alistapart.com/article/four/",  # genuinely new
]


class StubScraper(scraper.AdvisorScraper):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fetched = []

    def extract_article_urls(self, archive_url):
        return list(FETCHED)

    def extract_article_content(self, url):
        self.fetched.append(url)
        return {
            "title": url.rstrip("/").rsplit("/", 1)[-1],
            "url": url,
            "date": "",
            "author": "x",
            "content": "body",
        }


class ForgeDedupTest(unittest.TestCase):
    def test_skips_known_urls(self):
        with tempfile.TemporaryDirectory() as td:
            art = Path(td) / "articles"
            art.mkdir()
            for i, u in enumerate(EXISTING, 1):
                (art / f"{i:03d}-old-{i}.md").write_text(
                    f"# T{i}\n\n**Author:** a\n**Date:** d\n**URL:** {u}\n\n---\n\nx\n"
                )
            before = set(art.glob("*.md"))
            s = StubScraper("https://alistapart.com", td, rate_limit=0)
            s.run()
            new = set(art.glob("*.md")) - before
            self.assertEqual(len(new), 1, f"expected 1 new file, got {sorted(new)}")
            self.assertIn(
                "**URL:** https://alistapart.com/article/four/",
                next(iter(new)).read_text(),
            )
            self.assertEqual(s.fetched, ["https://alistapart.com/article/four/"])
            # Second run is a no-op.
            s2 = StubScraper("https://alistapart.com", td, rate_limit=0)
            s2.run()
            self.assertEqual(len(list(art.glob("*.md"))), len(before) + 1)
            self.assertEqual(s2.fetched, [])
            # A no-new-content run must not wipe the index built by earlier runs.
            meta = json.loads((Path(td) / "metadata" / "metadata.json").read_text())
            urls = [a["url"] for a in meta["articles"]]
            self.assertIn("https://alistapart.com/article/four/", urls)
            self.assertEqual(meta["total_articles"], len(urls))
            self.assertEqual(len(urls), len(set(urls)))

    def test_normalize(self):
        n = scraper.AdvisorScraper.normalize_url
        self.assertEqual(n("HTTPS://WWW.X.com/a/"), n("https://x.com/a"))
        self.assertNotEqual(n("https://x.com/a?p=1"), n("https://x.com/a?p=2"))


if __name__ == "__main__":
    unittest.main()
