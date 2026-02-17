#!/usr/bin/env python3
"""Open a URL in the default browser. Works around sandbox restrictions."""
import subprocess
import sys

if len(sys.argv) < 2:
    print("Usage: open_url.py <url>")
    sys.exit(1)

url = sys.argv[1]
subprocess.run(["open", url])
