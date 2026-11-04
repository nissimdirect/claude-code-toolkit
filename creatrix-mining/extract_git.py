#!/usr/bin/env python3
"""Extract incident candidates from git history (all refs incl. wip-backup/*, worktrees share the object DB).

Writes raw/git_commits.jsonl (every commit, compact) and raw/git_candidates.jsonl (fix/revert/regression-ish).
Read-only: uses only `git log` / `git show --stat`.
"""

import json
import os
import re
import subprocess
import sys

REPOS = {  # label -> path
    "v2": os.path.expanduser("~/Development/entropic-v2challenger"),
    "v1": os.path.expanduser("~/Development/entropic"),
}
SINCE = "2026-02-01"
OUT = os.path.expanduser("~/Development/creatrix-lessons/raw")
CAND = re.compile(
    r"\b(fix(e[sd])?|hotfix|bug|revert(s|ed)?|regress\w*|broke(n)?|crash\w*|restore[sd]?|roll ?back|undo|"
    r"wrong|incorrect|actually|oops|was not|wasn't|didn't|doesn't|not working|workaround|flak\w*|"
    r"repair|correct(s|ed|ion)?|missing|stale|leak\w*|race|deadlock|hang|freeze|blank|black screen)\b",
    re.I,
)
SEP, END = "\x1e", "\x1f"


def area_of(paths):
    tags = []
    rules = [
        ("timeline", r"timeline|clip|track|playhead|arrange"),
        ("effects", r"effects?/|fx|shader|glsl|effect"),
        ("routing", r"rout|modulat|signal|lfo|operator|patch"),
        ("ipc", r"ipc|zmq|bridge|preload|sidecar/.*server|protocol"),
        ("export", r"export|render|encode|ffmpeg"),
        ("perf", r"perf|bench|cache|worker"),
        (
            "build/ci",
            r"\.github/|package\.json|vite|electron-builder|pyproject|requirements|Makefile|build",
        ),
        ("audio", r"audio|midi|sound"),
        ("ui-shell", r"components/|\.css|layout|panel|ui/|renderer"),
        ("tests", r"test|spec|e2e|playwright"),
        ("docs/process", r"^docs/|\.md$"),
    ]
    for p in paths:
        for name, rx in rules:
            if re.search(rx, p, re.I) and name not in tags:
                tags.append(name)
    return tags


def main():
    os.makedirs(OUT, exist_ok=True)
    allf = open(os.path.join(OUT, "git_commits.jsonl"), "w")
    cf = open(os.path.join(OUT, "git_candidates.jsonl"), "w")
    n = c = 0
    for label, repo in REPOS.items():
        fmt = f"{SEP}%H%x00%ad%x00%D%x00%s%x00%b{END}"
        p = subprocess.run(
            [
                "git",
                "-C",
                repo,
                "log",
                "--all",
                f"--since={SINCE}",
                "--date=short",
                f"--format={fmt}",
                "--name-only",
            ],
            capture_output=True,
            text=True,
            errors="replace",
        )
        for chunk in p.stdout.split(SEP)[1:]:
            head, _, files = chunk.partition(END)
            sha, date, refs, subj, body = (head.split("\x00") + [""] * 5)[:5]
            paths = [x for x in files.strip().splitlines() if x.strip()]
            body = body.strip()
            rec = {
                "repo": label,
                "sha": sha,
                "date": date,
                "subject": subj,
                "refs": refs,
            }
            allf.write(json.dumps(rec) + "\n")
            n += 1
            revert_of = re.findall(r"This reverts commit ([0-9a-f]{7,40})", body)
            prefix = (re.match(r"^(\w+)(\([^)]*\))?!?:", subj) or [None, None])[1]
            if (
                CAND.search(subj)
                or CAND.search(body[:2000])
                or revert_of
                or (prefix or "").lower() in ("fix", "hotfix", "revert")
            ):
                rec.update(
                    {
                        "prefix": prefix,
                        "body": body[:1500],
                        "files": paths[:25],
                        "nfiles": len(paths),
                        "revert_of": revert_of,
                        "area_hint": area_of(paths),
                        "pr": re.findall(r"\(#(\d+)\)|#(\d+)", subj),
                    }
                )
                rec["pr"] = [a or b for a, b in rec["pr"]]
                rec["source_ref"] = f"{'' if label == 'v2' else 'entropic@'}{sha[:10]}"
                cf.write(json.dumps(rec) + "\n")
                c += 1
    print(f"commits={n} candidates={c}")


if __name__ == "__main__":
    main()
