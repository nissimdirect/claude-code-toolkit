#!/usr/bin/env python3
"""Compress raw/gh_prs.jsonl + gh_issues.jsonl into classifier candidates (raw/gh_candidates.jsonl).

Per PR: title, state, merged?, body head (400 chars) + body lines with defect language (<=900 chars), owner comments
(<=3 x 300), bot comments only for lines mentioning failure. Closed-unmerged PRs are always kept (possible
abandonment / design reversal). Issues are kept whole (truncated).
"""

import json
import re
from schema import LESSONS
from extract_docs import DEFECT


def defect_lines(text, cap):
    out, n = [], 0
    for l in (text or "").splitlines():
        if DEFECT.search(l) and len(l.strip()) > 8:
            out.append(l.strip()[:300])
            n += len(out[-1])
            if n > cap:
                break
    return "\n".join(out)


def main():
    n = 0
    with open(f"{LESSONS}/raw/gh_candidates.jsonl", "w") as out:
        for l in open(f"{LESSONS}/raw/gh_prs.jsonl"):
            p = json.loads(l)
            body = p.get("body") or ""
            human = [
                c["body"][:300]
                for c in p["comments"] + p["reviews"]
                if c.get("user") != "github-actions" and c.get("body")
            ][:3]
            bot = defect_lines(
                "\n".join(
                    c["body"] or ""
                    for c in p["comments"]
                    if c.get("user") == "github-actions"
                ),
                300,
            )
            rec = {
                "cand_id": f"P-{p['number']}",
                "ref": f"PR#{p['number']}",
                "date": (p.get("createdAt") or "")[:10],
                "title": p["title"],
                "state": p["state"],
                "merged": bool(p.get("mergedAt")),
                "branch": p.get("headRefName"),
                "merge_commit": (p.get("mergeCommit") or "")[:10] or None,
                "body_head": body[:400],
                "body_defects": defect_lines(body[400:], 900),
                "owner_comments": human,
                "ci_fail_lines": bot,
                "files": p.get("files", [])[:6],
            }
            if not (
                DEFECT.search(p["title"] + body)
                or human
                or bot
                or p["state"] == "CLOSED"
            ):
                continue
            out.write(json.dumps(rec) + "\n")
            n += 1
        for l in open(f"{LESSONS}/raw/gh_issues.jsonl"):
            i = json.loads(l)
            out.write(
                json.dumps(
                    {
                        "cand_id": f"I-{i['number']}",
                        "ref": f"issue#{i['number']}",
                        "date": i["createdAt"][:10],
                        "title": i["title"],
                        "state": i["state"],
                        "body_head": (i.get("body") or "")[:1200],
                        "owner_comments": [c["body"][:300] for c in i["comments"]][:3],
                    }
                )
                + "\n"
            )
            n += 1
    print(f"gh candidates={n}")


if __name__ == "__main__":
    main()
