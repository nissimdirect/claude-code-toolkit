#!/usr/bin/env python3
"""Source Heartbeat Monitor — checks all KB source URLs are reachable.

Reads URLs from ~/.claude/data-sources.json (active sources only).
Sends HEAD requests in parallel, reports UP/DOWN status.

Usage:
    python3 source_heartbeat.py           # check all active sources
    python3 source_heartbeat.py --json    # output as JSON
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def load_sources():
    """Load active sources from data-sources.json, deduplicate by domain."""
    path = os.path.expanduser("~/.claude/data-sources.json")
    with open(path) as f:
        data = json.load(f)

    sources = data.get("sources", [])
    active = [s for s in sources if s.get("status") == "active"]

    # Deduplicate by domain (keep first occurrence)
    seen_domains = {}
    for s in active:
        url = s.get("url", "")
        if not url or not url.startswith("http"):
            continue
        domain = urlparse(url).netloc.replace("www.", "")
        if domain not in seen_domains:
            seen_domains[domain] = {
                "id": s["id"],
                "url": url,
                "skill": s.get("skill", "unknown"),
                "domain": domain,
            }

    return list(seen_domains.values())


def check_url(source, timeout=10):
    """HEAD request to a single URL. Returns source dict with status."""
    url = source["url"]
    try:
        req = Request(
            url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 (Macintosh)"}
        )
        resp = urlopen(req, timeout=timeout)
        source["status_code"] = resp.status
        source["alive"] = True
        source["error"] = None
    except HTTPError as e:
        # 403/405 = site is up but blocks HEAD. Try GET with range.
        if e.code in (403, 405):
            try:
                req2 = Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh)",
                        "Range": "bytes=0-0",
                    },
                )
                resp2 = urlopen(req2, timeout=timeout)
                source["status_code"] = resp2.status
                source["alive"] = True
                source["error"] = None
            except Exception:
                source["status_code"] = e.code
                source["alive"] = True  # server responded, just blocked
                source["error"] = f"HTTP {e.code} (blocks automated requests)"
        else:
            source["status_code"] = e.code
            source["alive"] = e.code < 500  # 4xx = up but restricted, 5xx = down
            source["error"] = f"HTTP {e.code}"
    except URLError as e:
        source["status_code"] = None
        source["alive"] = False
        source["error"] = str(e.reason)[:80]
    except Exception as e:
        source["status_code"] = None
        source["alive"] = False
        source["error"] = str(e)[:80]

    return source


def main():
    json_output = "--json" in sys.argv

    sources = load_sources()
    start = time.time()

    # Check all URLs in parallel (max 10 threads)
    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(check_url, s): s for s in sources}
        for future in as_completed(futures):
            results.append(future.result())

    elapsed = time.time() - start

    # Sort: DOWN first, then alphabetical
    results.sort(key=lambda r: (r["alive"], r["domain"]))

    up = sum(1 for r in results if r["alive"])
    down = [r for r in results if not r["alive"]]

    if json_output:
        print(
            json.dumps(
                {
                    "date": time.strftime("%Y-%m-%d"),
                    "total": len(results),
                    "up": up,
                    "down": len(down),
                    "elapsed_s": round(elapsed, 1),
                    "sources": results,
                },
                indent=2,
            )
        )
        return

    # Human-readable output
    print(f"Source Heartbeat: {up}/{len(results)} UP ({elapsed:.1f}s)")
    print()

    if down:
        print("DOWN:")
        for r in down:
            print(f"  {r['id']:40s} {r['url']}")
            print(f"  {'':40s} Error: {r['error']}")
        print()

    print("UP:")
    for r in results:
        if r["alive"]:
            code = r["status_code"] or "?"
            note = f" ({r['error']})" if r.get("error") else ""
            print(f"  {r['id']:40s} {code}{note}")

    # Exit code: 0 if all up, 1 if any down
    sys.exit(0 if not down else 1)


if __name__ == "__main__":
    main()
