#!/usr/bin/env python3
"""Export compact per-area row lists for semantic dedupe agents, and merge their answers into classified/merges.json.

export: writes batches/dedupe-<area>.tsv (row_id \t date \t source \t type \t incident_key \t symptom[:120])
        Large areas are split into chunks of <=450 rows (sorted by incident_key so near-dupes sit together).
collect: reads classified/dedupe-*.json ([[row_id,...],...]) -> classified/merges.json (validated: ids must exist).
Row ids are "<classified file>::<id>" to stay unique across files.
"""

import json
import glob
import os
import sys
import collections
from schema import LESSONS


def rows():
    for f in sorted(glob.glob(f"{LESSONS}/classified/*-[0-9][0-9].jsonl")):
        for l in open(f):
            if l.strip():
                r = json.loads(l)
                r["_rid"] = f"{os.path.basename(f)}::{r['id']}"
                yield r


def export():
    by = collections.defaultdict(list)
    for r in rows():
        by[r["area"].replace("/", "_")].append(r)
    n = 0
    for area, rs in by.items():
        rs.sort(key=lambda r: (r.get("incident_key") or "", r["date"]))
        for k in range(0, len(rs), 450):
            n += 1
            with open(f"{LESSONS}/batches/dedupe-{area}-{k // 450 + 1}.tsv", "w") as f:
                for r in rs[k : k + 450]:
                    f.write(
                        "\t".join(
                            [
                                r["_rid"],
                                r["date"],
                                r["source"],
                                r["type"],
                                r.get("incident_key") or "",
                                r["symptom"][:120]
                                .replace("\t", " ")
                                .replace("\n", " "),
                            ]
                        )
                        + "\n"
                    )
            print(f"dedupe-{area}-{k // 450 + 1}.tsv rows={len(rs[k : k + 450])}")


def collect():
    known = {r["_rid"] for r in rows()}
    groups, bad = [], 0
    for f in glob.glob(f"{LESSONS}/classified/dedupe-*.json"):
        for g in json.load(open(f)):
            g2 = [x for x in g if x in known]
            bad += len(g) - len(g2)
            if len(g2) > 1:
                groups.append(g2)
    json.dump(groups, open(f"{LESSONS}/classified/merges.json", "w"))
    print(
        f"merge groups={len(groups)} rows_in_groups={sum(map(len, groups))} unknown_ids_dropped={bad}"
    )


if __name__ == "__main__":
    {"export": export, "collect": collect}[sys.argv[1]]()
