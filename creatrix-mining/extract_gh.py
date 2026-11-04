#!/usr/bin/env python3
"""Dump Creatrix PRs (body, comments, reviews, review comments) and issues to raw/gh_*.jsonl.

Read-only against GitHub. Resumable: skips PR numbers already in the output file.
Usage: extract_gh.py [--repo nissimdirect/entropic-v2challenger] [--out ~/Development/creatrix-lessons/raw]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor


def gh(args, retries=3):
    for i in range(retries):
        p = subprocess.run(["gh", *args], capture_output=True, text=True)
        if p.returncode == 0:
            return p.stdout
        time.sleep(2 * (i + 1))
    print(f"gh failed: {args}: {p.stderr[:300]}", file=sys.stderr)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="nissimdirect/entropic-v2challenger")
    ap.add_argument(
        "--out", default=os.path.expanduser("~/Development/creatrix-lessons/raw")
    )
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    fields = "number,title,body,state,createdAt,mergedAt,closedAt,headRefName,labels,comments,reviews,mergeCommit,files"
    nums = json.loads(gh(["pr", "list", "-R", a.repo, "--state", "all", "--limit", "2000", "--json", "number"]) or "[]")

    def fetch(n):
        raw = gh(["pr", "view", str(n), "-R", a.repo, "--json", fields])
        return json.loads(raw) if raw else None

    out = os.path.join(a.out, "gh_prs.jsonl")
    done = set()
    if os.path.exists(out):
        with open(out) as f:
            done = {json.loads(l)["number"] for l in f if l.strip()}
    with open(out, "a") as f:
        todo = sorted(x["number"] for x in nums if x["number"] not in done)
        with ThreadPoolExecutor(8) as ex:
            prs = [p for p in ex.map(fetch, todo) if p]
        for pr in prs:
            rc = gh(
                ["api", "--paginate", f"repos/{a.repo}/pulls/{pr['number']}/comments"]
            )
            try:
                rcs = json.loads(rc) if rc else []
            except json.JSONDecodeError:  # --paginate concatenates arrays
                rcs = json.loads("[" + rc.replace("][", "],[") + "]")
                rcs = [c for page in rcs for c in page]
            pr["review_comments"] = [
                {
                    "path": c.get("path"),
                    "line": c.get("line"),
                    "body": c.get("body"),
                    "user": (c.get("user") or {}).get("login"),
                }
                for c in rcs
            ]
            pr["files"] = [x["path"] for x in (pr.get("files") or [])]
            pr["comments"] = [
                {"body": c.get("body"), "user": (c.get("author") or {}).get("login")}
                for c in pr.get("comments") or []
            ]
            pr["reviews"] = [
                {
                    "body": r.get("body"),
                    "state": r.get("state"),
                    "user": (r.get("author") or {}).get("login"),
                }
                for r in pr.get("reviews") or []
            ]
            pr["mergeCommit"] = (pr.get("mergeCommit") or {}).get("oid")
            f.write(json.dumps(pr) + "\n")
            f.flush()
    issues = json.loads(
        gh(
            [
                "issue",
                "list",
                "-R",
                a.repo,
                "--state",
                "all",
                "--limit",
                "500",
                "--json",
                "number,title,body,state,createdAt,closedAt,labels,comments",
            ]
        )
    )
    with open(os.path.join(a.out, "gh_issues.jsonl"), "w") as f:
        for i in issues:
            i["comments"] = [
                {"body": c.get("body"), "user": (c.get("author") or {}).get("login")}
                for c in i.get("comments") or []
            ]
            f.write(json.dumps(i) + "\n")
    print(f"prs_listed={len(nums)} fetched_now={len(prs)} issues={len(issues)}")


if __name__ == "__main__":
    main()
