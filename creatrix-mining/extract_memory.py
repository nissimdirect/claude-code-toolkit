#!/usr/bin/env python3
"""Chunk memory files + Obsidian notes into line-numbered sections for classification.

Memory: creatrix*/entropic*/project_creatrix*/project_entropic*/visual-uat-entropic/feedback_*/learnings*.md.
Obsidian: any .md mentioning creatrix|entropic (incl. handoffs). Generic files (learnings*, feedback_*) keep only
sections that mention Creatrix/Entropic or UI/Electron/UAT terms; project files keep sections with defect language.
"""

import json
import os
import re
import glob
import datetime
from schema import MEM, OBS, LESSONS
from extract_docs import DEFECT, HEAD

SCOPE = re.compile(
    r"creatrix|entropic|v2challenger|sidecar|zmq|electron|timeline|effect chain|datamosh",
    re.I,
)
MAX = 2000


def chunks(lines):
    sec, cur, start = [], [], 1
    for i, l in enumerate(lines, 1):
        boundary = (
            HEAD.match(l)
            or re.match(r"^\s*(\d+\.|- \*\*|\*\*#?\d+)", l)
            and sum(len(x) for x in cur) > 600
        )
        if (boundary and cur) or sum(len(x) for x in cur) > MAX:
            sec.append((start, cur))
            cur, start = [], i
        cur.append(l)
    if cur:
        sec.append((start, cur))
    return sec


def file_date(path, text):
    m = re.search(r"20\d\d-\d\d-\d\d", os.path.basename(path)) or re.search(
        r"20\d\d-\d\d-\d\d", text[:3000]
    )
    return (
        m[0] if m else datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    )


def main():
    mem = [
        f
        for f in glob.glob(f"{MEM}/*.md")
        if re.search(
            r"/(creatrix|entropic|project_creatrix|project_entropic|visual-uat-entropic|feedback_|learnings)",
            f,
        )
    ]
    obs = []
    for f in glob.glob(f"{OBS}/**/*.md", recursive=True):
        try:
            if re.search(r"creatrix|entropic", open(f, errors="replace").read(), re.I):
                obs.append(f)
        except OSError:
            pass
    n = 0
    with open(f"{LESSONS}/raw/memory_candidates.jsonl", "w") as out:
        for kind, base, files in (("memory", MEM, mem), ("obsidian", OBS, obs)):
            for f in sorted(files):
                text = open(f, errors="replace").read()
                generic = kind == "memory" and re.search(r"/(feedback_|learnings)", f)
                fdate = file_date(f, text)
                rel = os.path.relpath(f, base)
                for start, sec in chunks(text.splitlines()):
                    t = "\n".join(sec)
                    if (
                        len(t.strip()) < 60
                        or not DEFECT.search(t)
                        and not re.search(
                            r"\b(lesson|mistake|correct|user said|should have|instead)\b",
                            t,
                            re.I,
                        )
                    ):
                        continue
                    if (generic or kind == "obsidian") and not SCOPE.search(t):
                        continue
                    d = re.search(r"20\d\d-\d\d-\d\d", t)
                    out.write(
                        json.dumps(
                            {
                                "cand_id": f"M-{kind[0]}-{rel[:50]}-{start}",
                                "ref": f"{kind}:{rel}:{start}",
                                "date": d[0] if d else fdate,
                                "text": "\n".join(
                                    f"{start + k:04d}| {l[:400]}"
                                    for k, l in enumerate(sec)
                                ),
                            }
                        )
                        + "\n"
                    )
                    n += 1
    print(f"memory files={len(mem)} obsidian files={len(obs)} candidates={n}")


if __name__ == "__main__":
    main()
