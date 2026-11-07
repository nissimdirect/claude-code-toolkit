#!/usr/bin/env python3
"""auto_tag_corpus must never recreate a file that was moved after load.

Run: python3 -I ~/Development/tools/tests/test_auto_tag_guard.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import auto_tag_corpus  # noqa: E402


class AutoTagGuardTest(unittest.TestCase):
    def test_moved_file_stays_gone(self):
        with tempfile.TemporaryDirectory() as td:
            kept, moved = Path(td) / "kept.md", Path(td) / "moved.md"
            for p in (kept, moved):
                p.write_text("growth growth growth")
            t = auto_tag_corpus.TFIDFTagger([])
            t.documents = [
                {"path": p, "content": "growth growth growth"} for p in (kept, moved)
            ]
            t.num_docs = 2
            moved.unlink()  # archived between load_corpus() and tag_corpus()
            t.tag_corpus(["growth"], dry_run=False)
            self.assertFalse(moved.exists(), "tagger resurrected an archived file")
            self.assertIn("[[growth]]", kept.read_text())

    def test_never_tags_header_or_urls(self):
        t = auto_tag_corpus.TFIDFTagger([])
        doc = (
            "# ChatPRD workflows\n\n**URL:** https://chatprd.ai/blog/x\n\n---\n\n"
            "Listen on https://open.spotify.com/ep/1 or [here](https://chatprd.ai/y). "
            "ChatPRD and Spotify both matter.\n"
        )
        out = t.tag_document(doc, ["chatprd", "spotify"])
        self.assertIn("**URL:** https://chatprd.ai/blog/x", out)
        self.assertIn("# ChatPRD workflows", out)
        self.assertIn("https://open.spotify.com/ep/1", out)
        self.assertIn("(https://chatprd.ai/y)", out)
        self.assertIn("[[ChatPRD]] and [[Spotify]] both matter", out)


if __name__ == "__main__":
    unittest.main()
