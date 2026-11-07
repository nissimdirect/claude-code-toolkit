#!/usr/bin/env python3
"""Split incident docs (read from origin/main via `git show`, never the working tree) into line-numbered chunks.

Docs: raw/docs_list.txt (UAT-*, BUG-*, PENDING-BUG-FIXES, ADVERSARIAL-FINDINGS, RED-TEAM-*, audits/, solutions/,
decisions/, uat/, RATIFIED-FOUNDATIONS). A chunk = one heading section (split further at ~2200 chars), kept only if it
has defect/reversal language. Lines are prefixed `NNNN| ` so the classifier can cite repo:<path>:<line> exactly.
"""

import json
import re
import subprocess
import os
from schema import V2, LESSONS

DEFECT = re.compile(
    r"\b(bug|BUG-\d+|fail(ed|s|ure)?|FAIL|broken|regress\w*|crash\w*|wrong|missing|not working|"
    r"doesn'?t|didn'?t|isn'?t|blocker|P0|P1|severity|critical|AMENDED|reversed|superseded|"
    r"revert\w*|root cause|workaround|defect|gap|❌|⚠️|✗|finding|vulnerab\w*|leak|race)\b",
    re.I,
)
HEAD = re.compile(r"^#{1,4} ")
MAX = 2200


def git_show(path):
    return subprocess.run(
        ["git", "-C", V2, "show", f"origin/main:{path}"],
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout


def commit_date(path):
    out = subprocess.run(
        [
            "git",
            "-C",
            V2,
            "log",
            "-1",
            "--format=%ad",
            "--date=short",
            "origin/main",
            "--",
            path,
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    m = re.search(r"20\d\d-\d\d-\d\d", path)
    return m[0] if m else out


def main():
    paths = [p.strip() for p in open(f"{LESSONS}/raw/docs_list.txt") if p.strip()]
    if "docs/frontend/RATIFIED-FOUNDATIONS.md" not in paths:
        paths.append("docs/frontend/RATIFIED-FOUNDATIONS.md")
    n = kept = 0
    with open(f"{LESSONS}/raw/docs_candidates.jsonl", "w") as out:
        for path in paths:
            lines = git_show(path).splitlines()
            if not lines:
                continue
            date = commit_date(path)
            sections, cur, start = [], [], 1
            for i, l in enumerate(lines, 1):
                if (HEAD.match(l) and cur) or sum(len(x) for x in cur) > MAX:
                    sections.append((start, cur))
                    cur, start = [], i
                cur.append(l)
            if cur:
                sections.append((start, cur))
            for start, sec in sections:
                n += 1
                text = "\n".join(sec)
                if not DEFECT.search(text) or len(text.strip()) < 40:
                    continue
                kept += 1
                numbered = "\n".join(
                    f"{start + k:04d}| {l[:400]}" for k, l in enumerate(sec)
                )
                out.write(
                    json.dumps(
                        {
                            "cand_id": f"D-{os.path.basename(path)[:40]}-{start}",
                            "ref": f"repo:{path}:{start}",
                            "path": path,
                            "date": date,
                            "text": numbered,
                        }
                    )
                    + "\n"
                )
    print(f"docs files={len(paths)} sections={n} candidates={kept}")


if __name__ == "__main__":
    main()
