#!/usr/bin/env python3
"""10% stratified spot-check sample of classified rows, printed compactly next to the candidate evidence.

Usage: spotcheck.py sample [--sources git,gh,...] [--seed 7]   -> writes spotcheck_sample.jsonl, prints compact view
       spotcheck.py score                                          -> reads spotcheck_verdicts.jsonl, prints disagreement
Verdict file rows: {"id": <classified row id>, "file": <classified file>, "verdict": "agree"|"type"|"area"|"not-incident"|"unsupported", "note": ...}
"""

import json
import glob
import os
import random
import sys
import collections
from schema import LESSONS


def cands():
    out = {}
    for f in glob.glob(f"{LESSONS}/batches/*.jsonl"):
        for l in open(f):
            r = json.loads(l)
            out[r["cand_id"]] = r
    return out


def evidence(c):
    for k in ("subject", "title", "prompt"):
        if c.get(k):
            extra = c.get("body") or c.get("body_head") or c.get("prev_assistant") or ""
            return (c[k] + " || " + extra.replace("\n", " "))[:260]
    return (c.get("text") or "").replace("\n", " ")[:260]


def sample(sources, seed):
    rnd = random.Random(seed)
    cs = cands()
    picked = []
    for f in sorted(glob.glob(f"{LESSONS}/classified/*-*.jsonl")):
        src = os.path.basename(f).split("-")[0]
        if sources and src not in sources:
            continue
        rows = [json.loads(l) for l in open(f) if l.strip()]
        k = max(1, round(len(rows) * 0.10)) if rows else 0
        for r in rnd.sample(rows, k):
            picked.append(
                {
                    "file": os.path.basename(f),
                    "id": r["id"],
                    "type": r["type"],
                    "area": r["area"],
                    "symptom": r["symptom"][:140],
                    "evidence": evidence(cs.get(r.get("cand_id"), {})),
                }
            )
    with open(f"{LESSONS}/spotcheck_sample.jsonl", "w") as o:
        for p in picked:
            o.write(json.dumps(p) + "\n")
    for i, p in enumerate(picked):
        print(
            f"{i:03d} [{p['type']}/{p['area']}] {p['symptom']}\n     EV: {p['evidence']}"
        )
    print(f"sampled={len(picked)}")


def score():
    v = [
        json.loads(l) for l in open(f"{LESSONS}/spotcheck_verdicts.jsonl") if l.strip()
    ]
    c = collections.Counter(x["verdict"] for x in v)
    dis = len(v) - c["agree"]
    print(
        f"checked={len(v)} agree={c['agree']} disagree={dis} rate={100 * dis / max(len(v), 1):.1f}% breakdown={dict(c)}"
    )
    by = collections.defaultdict(lambda: [0, 0])
    for x in v:
        s = x["file"].split("-")[0]
        by[s][0] += 1
        by[s][1] += x["verdict"] != "agree"
    for s, (n, d) in sorted(by.items()):
        print(f"  {s}: {d}/{n} disagree ({100 * d / n:.0f}%)")


if __name__ == "__main__":
    if sys.argv[1] == "sample":
        srcs = (
            set(sys.argv[sys.argv.index("--sources") + 1].split(","))
            if "--sources" in sys.argv
            else set()
        )
        sample(
            srcs,
            int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7,
        )
    else:
        score()
