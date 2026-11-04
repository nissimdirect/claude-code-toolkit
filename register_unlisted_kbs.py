#!/usr/bin/env python3
"""register_unlisted_kbs.py: one-off, idempotent registration of KB collections that no refresh job knew about
(2026-10-28 /propagate sweep). Adds the 34 knowledge-bases/data-analyst/* collections (scraper:
data_analyst_scraper.py --source <name>), brian-eno-moredarkthanshark, david-lynch-lynchnet (paused: site down),
unpauses texte-zur-kunst (TLS fixed), and adds the site url to three adhoc entries so stub folders match them.
Safe to re-run: existing ids/paths are left alone. Backup of the pre-change registry: data-sources.json.bak-2026-10-28.
"""

import glob
import json
import os

P = os.path.expanduser("~/.claude/data-sources.json")
BASE = os.path.expanduser("~/Development/knowledge-bases/data-analyst")
BOOKS = {
    "wilke-dataviz",
    "data-to-viz",
    "seeing-theory",
    "r4ds",
    "python-ds-handbook",
    "think-bayes",
    "fpp3",
    "causal-mixtape",
    "the-effect",
    "feat-engineering",
    "modern-stats-bio",
    "nist-handbook",
    "colah",
    "distill-pub",
}
URLS = {
    "the-brand-identity": "https://the-brand-identity.com",
    "fonts-in-use": "https://fontsinuse.com",
    "creative-boom": "https://www.creativeboom.com",
}

ds = json.load(open(P))
L = ds["sources"]
ids = {s.get("id") for s in L}
paths = {s.get("local_path") for s in L}
added = []
for name in sorted(os.listdir(BASE)):
    lp = f"~/Development/knowledge-bases/data-analyst/{name}"
    if not os.path.isdir(os.path.join(BASE, name, "metadata")) or lp in paths:
        continue
    tier = 3 if name in BOOKS else 2
    L.append(
        {
            "id": name if name not in ids else "da-" + name,
            "skill": "data-analyst",
            "type": "scraped-collection",
            "local_path": lp,
            "refresh_tier": tier,
            "refresh_interval_days": 90 if tier == 3 else 30,
            "method": "adhoc_script",
            "scraper": "~/Development/tools/data_analyst_scraper.py",
            "scraper_args": ["--source", name],
            "article_count": len(
                glob.glob(os.path.join(BASE, name, "articles", "*.md"))
            ),
            "content_newest": None,
            "last_checked": None,
            "status": "active",
            "path_verified": "2026-10-28",
            "registered": "2026-10-28 propagate sweep (was unregistered, last scraped 2026-03-06)",
        }
    )
    added.append(L[-1]["id"])
extra = [
    {
        "id": "brian-eno-moredarkthanshark",
        "skill": "creative-interviews",
        "type": "website",
        "url": "https://www.moredarkthanshark.org",
        "local_path": "~/Development/creative-interviews/brian-eno",
        "status": "active",
    },
    {
        "id": "david-lynch-lynchnet",
        "skill": "creative-interviews",
        "type": "website",
        "url": "https://www.lynchnet.com",
        "local_path": "~/Development/creative-interviews/david-lynch",
        "status": "paused",
        "paused_reason": "2026-10-28: registered paused; www.lynchnet.com did not answer (curl 000). Previous scrape got "
        "1 file. Re-enable if the site returns.",
    },
]
for e in extra:
    if e["id"] in ids:
        continue
    e.update(
        {
            "refresh_tier": 3,
            "refresh_interval_days": 90,
            "method": "forge_scrape",
            "content_newest": None,
            "last_checked": None,
            "path_verified": "2026-10-28",
            "registered": "2026-10-28 propagate sweep",
        }
    )
    L.append(e)
    added.append(e["id"])
for s in L:
    if s.get("id") == "texte-zur-kunst" and s.get("status") == "paused":
        s["status"] = "active"
        s["unpaused"] = (
            "2026-10-28: TLS fixed (https://www.textezurkunst.de returns 200)"
        )
        s["paused_reason_was"] = s.pop("paused_reason", "")
        added.append("texte-zur-kunst (unpaused)")
    if s.get("id") in URLS and not s.get("url"):
        s["url"] = URLS[s["id"]]
ds["_meta"]["last_updated"] = "2026-10-28"
open(P, "w").write(json.dumps(ds, indent=2) + "\n")
print(f"{len(added)} changes: {' '.join(added) or 'none (already registered)'}")
