#!/usr/bin/env python3
"""KB Refresh — registry-driven refresh runner for all knowledge-base sources.

Single entry point that reads ~/.claude/data-sources.json and refreshes every
active source, dispatching on the declared `method`. Replaces scrape-all.sh,
which hardcoded 24 of the (now) 153 active sources and let the rest drift.

Generic methods are handled in-process (rss, podcast_rss, substack, sitemap,
wp-api, git). Sources with a bespoke `scraper` field are shelled out to.
Incremental by default: existing article URLs are read from disk and skipped.

Usage:
    python3 kb_refresh.py --summary                 # what's stale, no network
    python3 kb_refresh.py --tier 1                  # refresh all tier-1
    python3 kb_refresh.py --source lenny-podcast    # one source
    python3 kb_refresh.py --all --stale-days 30     # everything >30d stale
    python3 kb_refresh.py --all --dry-run           # plan only
    python3 kb_refresh.py --all --jobs 4            # parallel

Exit code is 0 if every attempted source succeeded, 1 otherwise.
"""

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import html2text
import requests
from bs4 import BeautifulSoup

from kb_urls import norm, url_of

REGISTRY = Path.home() / ".claude" / "data-sources.json"
REPORT_DIR = Path.home() / "Development" / "tools" / "logs"
DEFAULT_DELAY = 1.0
TIMEOUT = 30
ADHOC_TIMEOUT = 10800  # big archives (lithub, its-nice-that) need hours

HEADERS = {
    "User-Agent": "Claude-Code-KB-Scraper/1.0 (Knowledge Base Builder; +popchaoslabs.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

H2T = html2text.HTML2Text()
H2T.ignore_links = False
H2T.ignore_images = True
H2T.body_width = 0
H2T.unicode_snob = True


# ── Utilities ──────────────────────────────────────────────────────────────


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", (text or "").lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")[:80] or "untitled"


def article_dir(source: dict) -> Path:
    """Resolve where articles live. Registry paths sometimes point at the
    collection root and sometimes at the articles/ subdir; normalise to the
    subdir so dedup and writes agree."""
    p = Path(source["local_path"].replace("~", str(Path.home())))
    if p.name == "articles":
        return p
    if (p / "articles").exists():
        return p / "articles"
    # Brand-new collection: kb_loader.py discovers KBs by globbing */articles,
    # so anything written to the collection root is invisible to retrieval.
    # Only fall back to the root when it already holds the articles.
    if p.exists() and any(p.glob("*.md")):
        return p
    return p / "articles"


def scraped_urls(outdir: Path) -> set:
    """Normalized URLs already on disk (url: front matter OR **URL:** lines).
    Drives incremental mode. Compare with `norm(link) in seen`: exact-string
    matching re-saved maggie-appleton's whole feed on 2026-11-05."""
    urls = set()
    if not outdir.exists():
        return urls
    for f in outdir.rglob("*.md"):
        u = url_of(f)
        if u:
            urls.add(norm(u))
    return urls


def save_article(
    outdir: Path,
    title: str,
    content: str,
    url: str,
    date_str: str = "",
    author: str = "",
    source_id: str = "",
) -> bool:
    """Write one article. Returns False if content is too thin to be useful."""
    if not content or len(content.strip()) < 200:
        return False
    # Extractors usually keep the page's own <h1>; we add one from the title,
    # so drop the leading duplicate rather than shipping it twice.
    content = content.lstrip()
    first, _, rest = content.partition("\n")
    if first.startswith("#") and slugify(first.lstrip("# ")) == slugify(title):
        content = rest.lstrip()
    outdir.mkdir(parents=True, exist_ok=True)
    fname = f"{slugify(title)}.md"
    path = outdir / fname
    if path.exists():
        path = outdir / f"{slugify(title)}-{abs(hash(url)) % 10000:04d}.md"
    fm = (
        "---\n"
        f'title: "{(title or "").replace(chr(34), chr(39))}"\n'
        f'url: "{url}"\n'
        f'date: "{date_str}"\n'
        f'author: "{author}"\n'
        f'source: "{source_id}"\n'
        f'scraped: "{datetime.now().isoformat()}"\n'
        "---\n\n"
        f"# {title}\n\n"
    )
    path.write_text(fm + content, encoding="utf-8")
    return True


def extract_html(html: str, url: str) -> tuple:
    """Pull (title, body-markdown, date) out of an article page."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    elif soup.title:
        title = soup.title.get_text(strip=True)
    date_str = ""
    t = soup.find("time")
    if t:
        date_str = t.get("datetime", "") or t.get_text(strip=True)
    body = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=re.compile(r"post|content|entry|article"))
        or soup.body
    )
    return title, H2T.handle(str(body)).strip() if body else "", date_str


# ── Method handlers ────────────────────────────────────────────────────────
# Each returns dict(added=int, skipped=int, note=str). Raise on hard failure.


def do_rss(s: dict, limit: int) -> dict:
    import feedparser

    outdir = article_dir(s)
    seen = scraped_urls(outdir)
    feed_url = s.get("rss_url") or s["url"]
    resp = requests.get(feed_url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if not feed.entries:
        # The registry often holds the site URL rather than the feed URL, so
        # don't give up on it: try the page's declared feed, then the usual
        # feed paths under both the given URL and its domain root.
        feed = None
        soup = BeautifulSoup(resp.text, "html.parser")
        link = soup.find("link", type=re.compile(r"rss|atom"))
        if link and link.get("href"):
            href = str(link["href"])
            if href.startswith("/"):
                href = (
                    f"{urlparse(feed_url).scheme}://{urlparse(feed_url).netloc}{href}"
                )
            try:
                cand = feedparser.parse(
                    requests.get(href, headers=HEADERS, timeout=60).content
                )
                if cand.entries:
                    feed = cand
            except requests.RequestException:
                pass
        if feed is None:
            u = urlparse(feed_url)
            bases = [feed_url.rstrip("/"), f"{u.scheme}://{u.netloc}"]
            for base in dict.fromkeys(bases):
                for path in FEED_PATHS:
                    try:
                        r = requests.get(base + path, headers=HEADERS, timeout=20)
                    except requests.RequestException:
                        continue
                    if not r.ok:
                        continue
                    cand = feedparser.parse(r.content)
                    if cand.entries:
                        feed = cand
                        break
                if feed is not None:
                    break
        if feed is None:
            raise RuntimeError(
                f"no feed entries and no discoverable feed at {feed_url}"
            )

    added = skipped = 0
    for e in feed.entries[:limit]:
        link = str(e.get("link", "") or "")
        if not link or norm(link) in seen:
            skipped += 1
            continue
        body = ""
        if e.get("content"):
            body = H2T.handle(str(e["content"][0].get("value", "") or "")).strip()
        elif e.get("summary"):
            body = H2T.handle(str(e["summary"] or "")).strip()
        if len(body) < 400:  # feed gave a stub — fetch the real page
            try:
                r = requests.get(link, headers=HEADERS, timeout=TIMEOUT)
                if r.ok:
                    _, full, _ = extract_html(r.text, link)
                    if len(full) > len(body):
                        body = full
                time.sleep(DEFAULT_DELAY)
            except requests.RequestException:
                pass
        if save_article(
            outdir,
            str(e.get("title", "Untitled") or "Untitled"),
            body,
            link,
            str(e.get("published", "") or ""),
            str(e.get("author", "") or ""),
            s["id"],
        ):
            added += 1
        else:
            skipped += 1
    return {"added": added, "skipped": skipped, "note": f"{len(feed.entries)} in feed"}


def do_substack(s: dict, limit: int) -> dict:
    outdir = article_dir(s)
    seen = scraped_urls(outdir)
    base = s["url"].rstrip("/")
    added = skipped = 0
    offset = 0
    while added + skipped < limit:
        api = f"{base}/api/v1/archive?sort=new&limit=50&offset={offset}"
        r = requests.get(api, headers=HEADERS, timeout=TIMEOUT)
        if not r.ok:
            break
        posts = r.json()
        if not posts:
            break
        for p in posts:
            link = p.get("canonical_url", "")
            if not link or norm(link) in seen:
                skipped += 1
                continue
            try:
                pr = requests.get(link, headers=HEADERS, timeout=TIMEOUT)
                _, body, _ = extract_html(pr.text, link)
                if save_article(
                    outdir,
                    p.get("title", "Untitled"),
                    body,
                    link,
                    p.get("post_date", ""),
                    "",
                    s["id"],
                ):
                    added += 1
                else:
                    skipped += 1
                time.sleep(DEFAULT_DELAY)
            except requests.RequestException:
                skipped += 1
        offset += 50
        if len(posts) < 50:
            break
    return {"added": added, "skipped": skipped, "note": f"offset {offset}"}


def do_sitemap(s: dict, limit: int) -> dict:
    outdir = article_dir(s)
    seen = scraped_urls(outdir)
    sm = s.get("sitemap_url") or s["url"].rstrip("/") + "/sitemap.xml"
    r = requests.get(sm, headers=HEADERS, timeout=60)
    if not r.ok:
        # /sitemap.xml is a convention, not a rule. robots.txt is where a site
        # actually declares its sitemap, so ask there before giving up.
        u = urlparse(s["url"])
        root = f"{u.scheme}://{u.netloc}"
        found = []
        try:
            rb = requests.get(root + "/robots.txt", headers=HEADERS, timeout=20)
            if rb.ok:
                found = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rb.text)
        except requests.RequestException:
            pass
        for cand in found + [root + "/sitemap.xml", root + "/sitemap_index.xml"]:
            try:
                rc = requests.get(cand, headers=HEADERS, timeout=30)
            except requests.RequestException:
                continue
            if rc.ok and b"<" in rc.content[:200]:
                r = rc
                break
    r.raise_for_status()
    root = ET.fromstring(r.content)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [u.text for u in root.findall(".//s:loc", ns) if u.text]
    # Nested sitemap index — follow the first few children.
    if urls and urls[0].endswith(".xml"):
        child = []
        for cu in urls[:5]:
            try:
                cr = requests.get(cu, headers=HEADERS, timeout=60)
                child += [
                    u.text
                    for u in ET.fromstring(cr.content).findall(".//s:loc", ns)
                    if u.text
                ]
            except (requests.RequestException, ET.ParseError):
                pass
        urls = child
    if s.get("url_filter"):
        urls = [u for u in urls if s["url_filter"] in u]
    added = skipped = 0
    for u in urls:
        if added + skipped >= limit:
            break
        if norm(u) in seen:
            skipped += 1
            continue
        try:
            pr = requests.get(u, headers=HEADERS, timeout=TIMEOUT)
            if not pr.ok:
                skipped += 1
                continue
            title, body, dt = extract_html(pr.text, u)
            if save_article(outdir, title, body, u, dt, "", s["id"]):
                added += 1
            else:
                skipped += 1
            time.sleep(DEFAULT_DELAY)
        except requests.RequestException:
            skipped += 1
    return {"added": added, "skipped": skipped, "note": f"{len(urls)} urls in sitemap"}


def do_wp_api(s: dict, limit: int) -> dict:
    outdir = article_dir(s)
    seen = scraped_urls(outdir)
    api = s.get("api_url") or s["url"].rstrip("/") + "/wp-json/wp/v2/posts"
    added = skipped = 0
    page = 1
    while added + skipped < limit:
        r = requests.get(
            api, headers=HEADERS, timeout=TIMEOUT, params={"per_page": 50, "page": page}
        )
        if not r.ok:
            break
        posts = r.json()
        if not isinstance(posts, list) or not posts:
            break
        for p in posts:
            link = p.get("link", "")
            if not link or norm(link) in seen:
                skipped += 1
                continue
            body = H2T.handle(p.get("content", {}).get("rendered", "")).strip()
            title = BeautifulSoup(
                p.get("title", {}).get("rendered", ""), "html.parser"
            ).get_text()
            if save_article(outdir, title, body, link, p.get("date", ""), "", s["id"]):
                added += 1
            else:
                skipped += 1
        page += 1
        time.sleep(DEFAULT_DELAY)
    return {"added": added, "skipped": skipped, "note": f"{page - 1} pages"}


def do_git(s: dict, limit: int) -> dict:
    p = Path(s["local_path"].replace("~", str(Path.home())))
    if p.name == "articles":
        p = p.parent
    repo = p if (p / ".git").exists() else p.parent
    if repo.exists() and not (repo / ".git").exists() and any(repo.iterdir()):
        # Never clone into a populated non-repo directory — that is how a
        # scraped collection gets clobbered by an unrelated checkout.
        raise RuntimeError(
            f"{p} holds content but is not a git repo; it is a flattened "
            "extract, not a working copy — set method=manual or re-extract"
        )
    if not (repo / ".git").exists():
        if not s.get("url"):
            raise RuntimeError(f"no git repo at {repo} and no clone url in registry")
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", s["url"], str(repo)],
            check=True,
            capture_output=True,
            timeout=ADHOC_TIMEOUT,
        )
        return {"added": 0, "skipped": 0, "note": "cloned"}
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    r = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=ADHOC_TIMEOUT,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git pull failed: {r.stderr.strip()[:200]}")
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    ).stdout.strip()
    return {
        "added": 0,
        "skipped": 0,
        "note": "up to date" if before == after else f"{before[:7]}..{after[:7]}",
    }


def do_adhoc(s: dict, limit: int) -> dict:
    """Shell out to a source's bespoke scraper. These predate the registry and
    each has its own CLI; we just run them and measure the delta on disk."""
    script = Path(s["scraper"].replace("~", str(Path.home())))
    if not script.exists():
        raise RuntimeError(f"scraper not found: {script}")
    outdir = article_dir(s)
    before = len(list(outdir.rglob("*.md"))) if outdir.exists() else 0
    py = Path.home() / "Development" / "tools" / ("v" + "env") / "bin" / "python"
    interp = str(py) if py.exists() else sys.executable
    # Several bespoke scrapers serve multiple collections from one file and
    # need a subcommand (e.g. scrape_literary.py lithub). The registry entry
    # carries those args so one script can back many sources.
    try:
        r = subprocess.run(
            [interp, str(script)] + list(s.get("scraper_args") or []),
            cwd=script.parent,
            capture_output=True,
            text=True,
            timeout=ADHOC_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        # Big archives (lithub, its-nice-that) legitimately outrun the cap.
        # Whatever landed before the kill is real content, so report it as
        # partial progress instead of throwing the whole run away as a failure.
        after = len(list(outdir.rglob("*.md"))) if outdir.exists() else 0
        if after > before:
            return {
                "added": after - before,
                "skipped": 0,
                "note": f"PARTIAL: timed out at {ADHOC_TIMEOUT}s, resume to continue",
            }
        raise
    after = len(list(outdir.rglob("*.md"))) if outdir.exists() else 0
    if r.returncode != 0 and after <= before:
        raise RuntimeError(
            f"exit {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}"
        )
    return {"added": after - before, "skipped": 0, "note": f"exit {r.returncode}"}


def do_forge(s: dict, limit: int) -> dict:
    """Drive the legacy per-site scrapers in scraper.py. Each declares a
    `forge_type` naming one of that module's 33 site-specific classes; they
    write into <collection>/articles themselves, so we measure the delta."""
    outdir = article_dir(s)
    before = len(list(outdir.rglob("*.md"))) if outdir.exists() else 0
    root = Path(s["local_path"].replace("~", str(Path.home())))
    if root.name == "articles":
        root = root.parent
    tools = Path.home() / "Development" / "tools"
    py = tools / ("v" + "env") / "bin" / "python"
    interp = str(py) if py.exists() else sys.executable
    r = subprocess.run(
        [interp, str(tools / "scraper.py"), s["forge_type"], s["url"], str(root)],
        capture_output=True,
        text=True,
        timeout=ADHOC_TIMEOUT,
    )
    after = len(list(outdir.rglob("*.md"))) if outdir.exists() else 0
    if r.returncode != 0 and after <= before:
        raise RuntimeError(
            f"exit {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}"
        )
    return {"added": after - before, "skipped": 0, "note": f"forge:{s['forge_type']}"}


def vtt_to_text(vtt: str) -> str:
    """Flatten a WebVTT caption track to prose, dropping cue timings and the
    duplicate rolling lines auto-captions emit."""
    out, last = [], None
    for ln in vtt.splitlines():
        ln = ln.strip()
        if (
            not ln
            or ln.startswith("WEBVTT")
            or "-->" in ln
            or ln.startswith(("Kind:", "Language:"))
        ):
            continue
        ln = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>|</?c>|<[^>]+>", "", ln).strip()
        if not ln or ln == last:
            continue
        out.append(ln)
        last = ln
    return "\n".join(out)


def do_youtube(s: dict, limit: int) -> dict:
    """Pull auto-caption transcripts for a channel's newest videos via yt-dlp.
    Dedup is by video id read back from frontmatter, so already-transcribed
    videos cost nothing on a re-run."""
    outdir = article_dir(s)
    outdir.mkdir(parents=True, exist_ok=True)
    have = set()
    for f in outdir.rglob("*.md"):
        m = re.search(r"^video_id:\s*(\S+)", f.read_text(errors="ignore")[:400], re.M)
        if m:
            have.add(m.group(1))
    cap = min(limit, 100)
    listing = subprocess.run(
        [
            "yt-dlp",
            "--flat-playlist",
            "--playlist-end",
            str(cap),
            "--print",
            "%(id)s\t%(title)s\t%(upload_date)s",
            s["url"],
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    rows = [ln.split("\t") for ln in listing.stdout.splitlines() if "\t" in ln]
    if not rows:
        raise RuntimeError(
            f"yt-dlp returned no videos: {listing.stderr.strip()[-200:]}"
        )
    tmp = Path("/tmp") / f"kbrefresh-vtt-{s['id']}"
    tmp.mkdir(parents=True, exist_ok=True)
    added = skipped = 0
    for row in rows:
        vid, title = row[0].strip(), row[1].strip()
        date_raw = row[2].strip() if len(row) > 2 else ""
        if vid in have:
            skipped += 1
            continue
        for old in tmp.glob(f"{vid}*.vtt"):
            old.unlink(missing_ok=True)
        subprocess.run(
            [
                "yt-dlp",
                "--skip-download",
                "--write-auto-sub",
                "--sub-lang",
                "en",
                "--sub-format",
                "vtt",
                "-o",
                str(tmp / f"{vid}.%(ext)s"),
                f"https://www.youtube.com/watch?v={vid}",
            ],
            capture_output=True,
            timeout=120,
        )
        vtts = list(tmp.glob(f"{vid}*.vtt"))
        if not vtts:
            skipped += 1
            continue
        text = vtt_to_text(vtts[0].read_text(errors="ignore"))
        if len(text) < 200:
            skipped += 1
            continue
        iso = (
            f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
            if len(date_raw) == 8 and date_raw.isdigit()
            else ""
        )
        path = outdir / f"{slugify(title)}.md"
        path.write_text(
            f'---\ntitle: "{title.replace(chr(34), chr(39))}"\n'
            f"video_id: {vid}\nyoutube_url: https://www.youtube.com/watch?v={vid}\n"
            f"upload_date: {iso or 'NA'}\nsource: {s['id']}-youtube-auto-caption\n"
            f'channel_url: {s["url"]}\nscraped: "{datetime.now().isoformat()}"\n'
            f"---\n\n# {title}\n\n## Transcript (auto-captioned)\n\n{text}\n",
            encoding="utf-8",
        )
        added += 1
        for f in tmp.glob(f"{vid}*"):
            f.unlink(missing_ok=True)
    return {"added": added, "skipped": skipped, "note": f"{len(rows)} videos listed"}


FEED_PATHS = [
    "/feed",
    "/rss",
    "/feed.xml",
    "/index.xml",
    "/atom.xml",
    "/rss.xml",
    "/feed/",
    "/blog/feed",
    "/feed/rss",
]


def do_auto(s: dict, limit: int) -> dict:
    """Fallback for sources with no bespoke scraper: probe the usual feed
    locations, then the declared <link rel=alternate>, then the sitemap.
    Most personal blogs in the registry are plain RSS behind a site URL."""
    import feedparser

    base = s["url"].rstrip("/")
    for path in FEED_PATHS:
        try:
            r = requests.get(base + path, headers=HEADERS, timeout=20)
            if r.ok and feedparser.parse(r.content).entries:
                return do_rss({**s, "rss_url": base + path}, limit)
        except requests.RequestException:
            continue
    try:
        r = requests.get(base, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        link = soup.find("link", type=re.compile(r"rss|atom"))
        if link and link.get("href"):
            href = str(link["href"])
            if href.startswith("/"):
                href = base + href
            return do_rss({**s, "rss_url": href}, limit)
    except requests.RequestException:
        pass
    return do_sitemap(s, limit)


HANDLERS = {
    "rss_scrape": do_rss,
    "podcast_rss": do_rss,
    "substack_archive": do_substack,
    "sitemap_scrape": do_sitemap,
    "wp_api": do_wp_api,
    "git_pull": do_git,
    "git_clone": do_git,
    "adhoc_script": do_adhoc,
    "youtube_transcript": do_youtube,
}


def resolve_handler(s: dict):
    """forge_scrape is a legacy catch-all: route it to a bespoke scraper when
    the source declares one, otherwise report it as unrunnable rather than
    silently doing nothing."""
    m = s.get("method")
    if m in HANDLERS:
        return HANDLERS[m]
    if m == "forge_scrape":
        if s.get("forge_type"):
            return do_forge
        if s.get("scraper"):
            return do_adhoc
        return do_auto if s.get("url") else None
    return None


# ── Runner ─────────────────────────────────────────────────────────────────


def staleness(s: dict) -> int:
    newest = s.get("content_newest")
    if not newest:
        return 9999
    try:
        return (date.today() - date.fromisoformat(newest)).days
    except ValueError:
        return 9999


def select(sources: list, args) -> list:
    sel = [s for s in sources if s.get("status") == "active"]
    if args.source:
        want = set(args.source.split(","))
        return [s for s in sel if s.get("id") in want]
    if args.tier:
        sel = [s for s in sel if s.get("refresh_tier") == args.tier]
    if args.method:
        sel = [s for s in sel if s.get("method") == args.method]
    if args.stale_days:
        sel = [s for s in sel if staleness(s) >= args.stale_days]
    if args.skill:
        sel = [s for s in sel if s.get("skill") == args.skill]
    return sel


def run_quality_gate(s: dict) -> str:
    """Sanitize and dead-article-check what we just wrote. A scraper that
    silently starts returning nav chrome looks like success without this."""
    gate = Path.home() / "Development" / "tools" / "kb_quality_gate.py"
    if not gate.exists():
        return "no-gate"
    try:
        r = subprocess.run(
            [sys.executable, str(gate), str(article_dir(s)), "--fix"],
            capture_output=True,
            text=True,
            timeout=900,
        )
        m = re.search(r"VERDICT:\s*(\w+)", r.stdout)
        return m.group(1) if m else "unknown"
    except (subprocess.SubprocessError, OSError):
        return "gate-error"


def refresh_one(s: dict, limit: int) -> dict:
    started = time.time()
    res = {
        "id": s["id"],
        "method": s.get("method"),
        "tier": s.get("refresh_tier"),
        "stale_days": staleness(s),
    }
    handler = resolve_handler(s)
    if handler is None:
        res.update(
            status="NO_HANDLER",
            added=0,
            note=f"method={s.get('method')} with no scraper declared",
        )
        return res
    try:
        out = handler(s, limit)
        res.update(status="OK", elapsed=round(time.time() - started, 1), **out)
        if out.get("added"):
            res["gate"] = run_quality_gate(s)
    except Exception as exc:  # noqa: BLE001 — one bad source must not kill the run
        res.update(
            status="FAIL",
            added=0,
            elapsed=round(time.time() - started, 1),
            note=f"{type(exc).__name__}: {str(exc)[:200]}",
        )
    return res


def main():
    ap = argparse.ArgumentParser(description="Registry-driven KB refresh")
    ap.add_argument("--source", help="comma-separated source ids")
    ap.add_argument("--tier", type=int, choices=[1, 2, 3, 4])
    ap.add_argument("--method")
    ap.add_argument("--skill")
    ap.add_argument("--stale-days", type=int, help="only sources at least this stale")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=500, help="max articles per source")
    ap.add_argument("--jobs", type=int, default=3, help="parallel sources")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--summary", action="store_true", help="staleness table, no network"
    )
    ap.add_argument("--no-registry-update", action="store_true")
    args = ap.parse_args()

    reg = json.loads(REGISTRY.read_text())
    sources = reg["sources"]

    if args.summary:
        act = [s for s in sources if s.get("status") == "active"]
        act.sort(key=lambda s: (-staleness(s), s.get("refresh_tier") or 9))
        print(f"{'id':<30}{'T':<3}{'method':<18}{'files':>7}{'stale':>7}  handler")
        for s in act:
            h = "yes" if resolve_handler(s) else "NONE"
            print(
                f"{s['id']:<30}{s.get('refresh_tier'):<3}{str(s.get('method')):<18}"
                f"{s.get('article_count', 0):>7}{staleness(s):>7}  {h}"
            )
        runnable = sum(1 for s in act if resolve_handler(s))
        print(
            f"\n{len(act)} active | {runnable} runnable | {len(act) - runnable} need a scraper"
        )
        return 0

    if not (args.all or args.source or args.tier or args.method or args.skill):
        ap.error("specify --all, --source, --tier, --method, --skill, or --summary")

    targets = select(sources, args)
    if not targets:
        print("no sources matched")
        return 0

    runnable = [s for s in targets if resolve_handler(s)]
    blocked = [s for s in targets if not resolve_handler(s)]
    print(
        f"selected {len(targets)} | runnable {len(runnable)} | no handler {len(blocked)}"
    )
    if blocked:
        print("  no handler: " + ", ".join(s["id"] for s in blocked))
    if args.dry_run:
        for s in runnable:
            print(
                f"  would refresh {s['id']:<28} {s.get('method'):<18} stale={staleness(s)}d"
            )
        return 0

    results = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(refresh_one, s, args.limit): s for s in runnable}
        for i, f in enumerate(concurrent.futures.as_completed(futs), 1):
            r = f.result()
            results.append(r)
            print(
                f"[{i}/{len(runnable)}] {r['status']:<10}{r['id']:<30}"
                f"+{r.get('added', 0):<6}{r.get('note', '')[:70]}"
            )
    results += [
        {
            "id": s["id"],
            "status": "NO_HANDLER",
            "added": 0,
            "method": s.get("method"),
            "tier": s.get("refresh_tier"),
            "note": "no scraper declared",
        }
        for s in blocked
    ]

    if not args.no_registry_update:
        by_id = {r["id"]: r for r in results}
        today = date.today().isoformat()
        # Re-read before writing: a run lasts hours, and writing back the copy loaded at start erased
        # sources registered in the meantime (2026-10-28). Only this run's own fields are merged in.
        reg = json.loads(REGISTRY.read_text())
        sources = reg["sources"] if isinstance(reg, dict) else reg
        for s in sources:
            r = by_id.get(s.get("id"))
            if not r or r["status"] != "OK":
                continue
            s["last_checked"] = today
            d = article_dir(s)
            if d.exists():
                s["article_count"] = len(list(d.rglob("*.md")))
                s["content_newest"] = (
                    today if r.get("added") else s.get("content_newest")
                )
        REGISTRY.write_text(json.dumps(reg, indent=2))

    # Keep the disaster-recovery manifest in step with reality. It used to be
    # hand-maintained, which is why it sat 4 months stale describing a
    # 46-source world; regenerating here means it cannot drift again.
    gen = Path(__file__).with_name("kb_manifest_gen.py")
    if gen.exists() and not args.no_registry_update:
        try:
            subprocess.run([sys.executable, str(gen)], capture_output=True, timeout=900)
        except (subprocess.SubprocessError, OSError):
            pass

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = REPORT_DIR / f"kb-refresh-{stamp}.json"
    report.write_text(json.dumps(results, indent=2))

    ok = [r for r in results if r["status"] == "OK"]
    fail = [r for r in results if r["status"] == "FAIL"]
    nh = [r for r in results if r["status"] == "NO_HANDLER"]
    print(f"\n{'=' * 66}")
    print(
        f"OK {len(ok)} | FAIL {len(fail)} | NO_HANDLER {len(nh)} "
        f"| +{sum(r.get('added', 0) for r in results)} articles "
        f"| {round(time.time() - t0)}s"
    )
    if fail:
        print("\nfailures:")
        for r in fail:
            print(f"  {r['id']:<30}{r['note']}")
    print(f"report: {report}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
