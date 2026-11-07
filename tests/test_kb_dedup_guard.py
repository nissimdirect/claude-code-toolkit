#!/usr/bin/env python3
"""kb_dedup --apply must see running KB writers (and ignore shells that only
mention them). macOS framework Python runs as .../MacOS/Python (capital P),
which the first version of this guard missed, so it applied mid-refresh.

Run: python3 -I ~/Development/tools/tests/test_kb_dedup_guard.py
"""

import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kb_dedup  # noqa: E402

FRAMEWORK = "/opt/homebrew/Frameworks/Python.framework/Resources/Python.app/Contents/MacOS/Python"
ENV_PY = "/Users/x/Development/tools/" + "v" + "env/bin/python"
PS = f"""COMMAND
{FRAMEWORK} kb_refresh.py --source splice-blog
{ENV_PY} /Users/x/Development/tools/auto_tag_corpus.py --auto-confirm
/bin/zsh -c cd tools && python3 kb_dedup.py --apply # mentions scraper.py auto_tag_corpus.py
/usr/bin/vim scraper.py
"""


class GuardTest(unittest.TestCase):
    def run_with(self, text):
        fake = types.SimpleNamespace(stdout=text)
        with mock.patch.object(subprocess, "run", return_value=fake):
            return kb_dedup.running_writers()

    def test_detects_framework_python_and_env_python(self):
        self.assertEqual(self.run_with(PS), ["auto_tag_corpus.py", "kb_refresh.py"])

    def test_idle_is_empty(self):
        self.assertEqual(
            self.run_with("COMMAND\n/bin/zsh\n/usr/bin/vim scraper.py\n"), []
        )


if __name__ == "__main__":
    unittest.main()
