#!/usr/bin/env python3
"""KB duplicate planner. Default = dry run (writes plan CSV only). --apply moves dupes.

Background (2026-11-04): forge scrapers re-saved every article on every run
(fixed in scraper.py), leaving ~57% of KB files as duplicates.

Safety rules, each one learned from a full verification of the first plan:
- A file is only planned as a duplicate if its CONTENT matches the keeper
  (same normalized title, or >=60% word overlap). Same-URL-only is not enough:
  yc-library/pmf-show record one landing-page URL for many different articles.
- The keeper is the copy with the MOST content (10% bins); front matter, a
  known date, and age only break ties. "Front matter first" kept truncated
  copies (its-nice-that: 202-word keeper vs 839-word dupe).
- Dupes move OUTSIDE ~/Development (ARCHIVE_ROOT, mirrored paths): kb_loader,
  kb_quality_gate and kb_refresh all rglob article dirs, so an in-tree
  _dupes_archive/ would still be loaded and counted.
"""

import argparse
import csv
import json
import math
import os
import re
import shutil
import sys
import time
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

REG = os.path.expanduser("~/.claude/data-sources.json")
LOGS = os.path.expanduser("~/Development/tools/logs")
HOME = os.path.expanduser("~")
# One folder per apply run, so a second pass never collides with the first.
ARCHIVE_ROOT = os.path.join(
    HOME, "KB-dupes-archive", datetime.now().strftime("%Y-%m-%d-%H%M")
)
# Anything that writes KB files from an in-memory list must not overlap an
# apply: auto_tag_corpus.py did, and wrote 59,998 moved files back.
KB_WRITERS = ("auto_tag_corpus.py", "kb_refresh.py", "scraper.py")
URL_RE = re.compile(r"^\*\*URL:\*\*\s*(\S+)")
FM_RE = re.compile(r'^(?:url|source_url):\s*["\']?(\S+?)["\']?\s*$', re.I)
NUM_RE = re.compile(r"^(\d+)")
DATE_RE = re.compile(
    r'^(?:\*\*Date:\*\*|date:)\s*["\']?(\d{4}-\d{2}-\d{2})', re.I | re.M
)
TITLE_FM = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.M)
TITLE_H1 = re.compile(r"^# (.+)$", re.M)
TAG = re.compile(r"\[\[|\]\]")
MATCH_JACCARD = 0.6


def norm(u):
    try:
        p = urlsplit(u.strip())
        return urlunsplit(
            (p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), p.query, "")
        )
    except Exception:
        return u.strip()


def find_url(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= 30:
                    break
                m = URL_RE.match(line) or FM_RE.match(line.strip())
                if m:
                    return m.group(1)
    except OSError:
        pass
    return None


def profile(fp, name):
    """Content fingerprint + keeper sort key for one article file."""
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            t = f.read()
    except OSError:
        t = ""
    head = t[:3000]
    m = TITLE_FM.search(head) or TITLE_H1.search(head)
    title = re.sub(r"[\W_]+", "", TAG.sub("", m.group(1)).lower()) if m else ""
    words = re.findall(r"\w+", TAG.sub("", t.split("\n---\n", 2)[-1]).lower())
    num = NUM_RE.match(name)
    key = (
        -int(math.log(len(words) + 1, 1.1)),  # more content first (10% bins)
        not head.startswith("---"),  # then front matter
        not bool(DATE_RE.search(head)),  # then a known date
        int(num.group(1)) if num else float("inf"),
        os.path.getmtime(fp) if os.path.exists(fp) else 0,
        name,
    )
    return {"fp": fp, "key": key, "title": title, "words": set(words[:400])}


def same_article(a, b):
    if a["title"] and a["title"] == b["title"]:
        return True
    union = a["words"] | b["words"]
    return bool(union) and len(a["words"] & b["words"]) / len(union) >= MATCH_JACCARD


def article_dir(lp):
    p = os.path.expanduser(lp)
    a = os.path.join(p, "articles")
    return a if os.path.isdir(a) else p


def plan_source(sid, d):
    groups, no_url, files = {}, 0, 0
    for name in os.listdir(d):
        fp = os.path.join(d, name)
        if not name.endswith(".md") or not os.path.isfile(fp):
            continue
        files += 1
        u = find_url(fp)
        if not u:
            no_url += 1
            continue
        groups.setdefault(norm(u), []).append(profile(fp, name))
    rows, unverified = [], 0
    for u, items in groups.items():
        items.sort(key=lambda x: x["key"])
        keeper = items[0]
        for it in items[1:]:
            if same_article(keeper, it):
                rows.append((sid, keeper["fp"], it["fp"], u))
            else:
                unverified += 1  # shares a URL but not content: never moved
    return dict(
        id=sid,
        files=files,
        unique=len(groups),
        dupes=len(rows),
        unverified=unverified,
        no_url=no_url,
    ), rows


def archive_path(src):
    rel = os.path.relpath(os.path.realpath(src), HOME)
    if rel.startswith(".."):
        raise ValueError(f"refusing to archive a file outside home: {src}")
    return os.path.join(ARCHIVE_ROOT, rel)


def running_writers():
    import subprocess

    out = subprocess.run(["ps", "-axo", "command"], capture_output=True, text=True)
    busy = set()
    for line in out.stdout.splitlines():
        argv = line.split()
        # Only real interpreter processes: a shell whose command text merely
        # mentions a writer (e.g. this session's own bash) is not a writer.
        if argv and "python" in os.path.basename(argv[0]).lower():
            busy |= {w for w in KB_WRITERS for a in argv[1:3] if a.endswith(w)}
    return sorted(busy)


def apply(csvp, source):
    if not os.path.exists(csvp) or time.time() - os.path.getmtime(csvp) > 3600:
        sys.exit(f"Refusing: plan {csvp} missing or older than 1 hour. Re-run dry run.")
    busy = running_writers()
    if busy:
        sys.exit(f"Refusing: KB writers running ({', '.join(busy)}). Wait for them.")
    moved = skipped = 0
    log = os.path.join(LOGS, f"kb-dedup-moves-{datetime.now():%Y%m%d-%H%M%S}.tsv")
    with open(log, "w") as lf:
        for r in csv.DictReader(open(csvp)):
            if source and r["source_id"] != source:
                continue
            src, keep = r["dupe_path"], r["keeper_path"]
            if not os.path.isfile(src) or not os.path.isfile(keep):
                skipped += 1  # never orphan an article: keeper must still exist
                continue
            dst = archive_path(src)
            if os.path.exists(dst):
                skipped += 1
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            lf.write(f"{src}\t{dst}\n")
            moved += 1
    print(f"moved {moved} files, skipped {skipped}; undo log: {log}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--source")
    a = ap.parse_args()
    os.makedirs(LOGS, exist_ok=True)
    csvp = os.path.join(LOGS, f"kb-dedup-plan-{datetime.now():%Y%m%d}.csv")
    if a.source:
        csvp = csvp.replace(".csv", f"-{a.source}.csv")  # never clobber the full plan
    if a.apply:
        return apply(csvp, a.source)
    srcs = json.load(open(REG))["sources"]
    seen, stats, allrows = set(), [], []
    for s in srcs:
        lp = s.get("local_path")
        if not lp or (a.source and s["id"] != a.source):
            continue
        d = article_dir(lp)
        if not os.path.isdir(d):
            continue
        rp = os.path.realpath(d)
        if rp in seen:
            continue  # shared dir already counted
        seen.add(rp)
        st, rows = plan_source(s["id"], d)
        stats.append(st)
        allrows += rows
    stats.sort(key=lambda x: -x["dupes"])
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "keeper_path", "dupe_path", "url"])
        w.writerows(allrows)
    cols = ("files", "unique", "dupes", "unverified", "no_url")
    print(f"{'id':32}" + "".join(f"{c:>11}" for c in cols))
    for s in stats[:25]:
        print(f"{s['id'][:32]:32}" + "".join(f"{s[c]:>11}" for c in cols))
    print(
        f"{'TOTAL (' + str(len(stats)) + ' sources)':32}"
        + "".join(f"{sum(s[c] for s in stats):>11}" for c in cols)
    )
    print("plan:", csvp)


if __name__ == "__main__":
    main()
