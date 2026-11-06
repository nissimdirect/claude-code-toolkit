#!/usr/bin/env python3
"""Offline tests for kb_urls + the five bespoke scrapers that use it.

Run: python3 -I ~/Development/tools/tests/test_kb_urls.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import kb_urls  # noqa: E402

HOME = Path.home() / "Development"
SCRAPERS = [
    HOME / "literary-criticism/scrape_literary.py",
    HOME / "music-marketing/ari-herstand/scrape_ari.py",
    HOME / "music-production/attack-magazine/scrape_attack.py",
    HOME / "music-production/splice/scrape_splice.py",
    TOOLS / "data_analyst_scraper.py",
    HOME / "art-direction/the-brand-identity/scrape_brand_identity.py",
]


class KbUrlsTest(unittest.TestCase):
    def test_norm(self):
        n = kb_urls.norm
        self.assertEqual(n("HTTPS://WWW.Lithub.com/a/"), n("https://lithub.com/a"))
        self.assertEqual(n("https://x.com/a#frag"), n("https://x.com/a"))
        self.assertNotEqual(n("https://x.com/a?p=1"), n("https://x.com/a?p=2"))
        self.assertNotEqual(n("https://x.com/a"), n("https://x.com/b"))

    def test_known_urls_reads_every_format(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "a.md").write_text(
                '---\ntitle: "A"\nurl: "https://lithub.com/a/"\n---\nx'
            )
            (d / "001-b.md").write_text("# B\n\n**URL:** https://www.lithub.com/b\n\nx")
            (d / "c.md").write_text("---\nsource_url: https://lithub.com/c\n---\n")
            (d / "d.md").write_text("# no url here\n\nbody mentions url: nothing")
            (d / "e.txt").write_text("**URL:** https://lithub.com/e")
            got = kb_urls.known_urls(d)
            want = {kb_urls.norm(f"https://lithub.com/{s}") for s in "abc"}
            self.assertEqual(got, want)

    def test_missing_dir_is_empty(self):
        self.assertEqual(kb_urls.known_urls("/nonexistent/kb/dir"), set())

    def test_url_on_line_31_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "x.md"
            f.write_text("\n" * 30 + "**URL:** https://x.com/late\n")
            self.assertIsNone(kb_urls.url_of(f))


class ScrapersWiredTest(unittest.TestCase):
    """Each scraper must seed its skip set from disk and compare normalized URLs."""

    def test_each_scraper_uses_kb_urls(self):
        for p in SCRAPERS:
            src = p.read_text()
            with self.subTest(scraper=p.name):
                self.assertIn("known_urls(", src)
                self.assertRegex(src, r"\bnorm\(")


if __name__ == "__main__":
    unittest.main()
