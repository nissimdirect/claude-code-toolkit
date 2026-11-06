"""Shared "which articles do we already have?" for every KB scraper.

Background (2026-11-04): five bespoke scrapers re-saved their whole archive on
each kb_refresh run (~20k duplicate files) because each one decided "already
scraped" from a different, incomplete signal:
  - progress.json, only honored with --resume (kb_refresh never passes it)
  - metadata.json, which each run overwrites with only that run's articles
  - `**URL:**` lines only, missing older files that carry `url:` front matter
  - exact string compare, so `/slug` vs `/slug/` or `www.` looked new
The files on disk are the only durable truth, so scrapers seed from them.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_URL_LINE = re.compile(
    r"""^(?:\*\*URL:\*\*\s*|(?:url|source_url|link):\s*)["']?(https?://[^\s"']+)""",
    re.I,
)


def norm(url: str) -> str:
    """Canonical form for "same article": lowercase scheme/host, no www.,
    no trailing slash, no fragment. Query is kept (?p=1 vs ?p=2 differ)."""
    try:
        p = urlsplit(url.strip())
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return urlunsplit((p.scheme.lower(), host, p.path.rstrip("/"), p.query, ""))
    except Exception:
        return url.strip()


def url_of(path, max_lines: int = 30):
    """The article URL recorded in a saved .md file, or None."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                m = _URL_LINE.match(line.strip())
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


def known_urls(articles_dir) -> set:
    """Normalized URLs of every article already saved in articles_dir."""
    d = Path(articles_dir).expanduser()
    if not d.is_dir():
        return set()
    out = set()
    for f in d.glob("*.md"):
        u = url_of(f)
        if u:
            out.add(norm(u))
    return out
