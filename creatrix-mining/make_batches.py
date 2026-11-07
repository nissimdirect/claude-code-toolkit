#!/usr/bin/env python3
"""Turn raw/<source>_candidates.jsonl into compact classifier batches under batches/<source>-NN.jsonl.

Usage: make_batches.py <source> [--size 60]
Each batch line is a compact candidate with a stable `cand_id`; the classifier brief is CLASSIFIER_BRIEF.md.
"""

import argparse
import json
import os
from schema import LESSONS


def compact_git(r):
    return {
        "cand_id": f"G-{r['sha'][:10]}",
        "ref": r["source_ref"],
        "date": r["date"],
        "subject": r["subject"],
        "body": r["body"][:700],
        "files": r["files"][:8],
        "nfiles": r["nfiles"],
        "revert_of": r["revert_of"],
        "pr": r["pr"],
        "area_hint": r["area_hint"],
    }


def compact_prompt(r):
    keep = ("cand_id", "ref", "date", "project", "cwd", "prompt", "prev_prompt", "prev_assistant", "pasted_excerpt")
    return {k: r[k] for k in keep if r.get(k)}


COMPACT = {"git": compact_git, "history": compact_prompt, "transcripts": compact_prompt, "cfg_transcripts": compact_prompt}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--size", type=int, default=60)
    a = ap.parse_args()
    src = f"{LESSONS}/raw/{a.source}_candidates.jsonl"
    fn = COMPACT.get(a.source, lambda r: r)
    rows = [fn(json.loads(l)) for l in open(src) if l.strip()]
    rows.sort(key=lambda r: r.get("date", ""))
    os.makedirs(f"{LESSONS}/batches", exist_ok=True)
    nb = 0
    for i in range(0, len(rows), a.size):
        nb += 1
        with open(f"{LESSONS}/batches/{a.source}-{nb:02d}.jsonl", "w") as f:
            for r in rows[i : i + a.size]:
                f.write(json.dumps(r) + "\n")
    print(f"{a.source}: {len(rows)} candidates -> {nb} batches")


if __name__ == "__main__":
    main()
