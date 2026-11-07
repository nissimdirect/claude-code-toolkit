#!/usr/bin/env python3
"""Export classified rows for root-cause-cluster assignment (batches/rc-NN.tsv) and collect answers (classified/rc-*.json).
export: rid \t type \t area \t symptom[:90] \t root_cause[:150]
collect: merges rc-*.json ({rid: "RCnn"}) into classified/rc_assign.json (unknown ids / codes dropped, counted).
"""
import json, glob, sys, re
from dedupe_export import rows
from schema import LESSONS

def export(size=280):
    rs = list(rows()); n = 0
    for k in range(0, len(rs), size):
        n += 1
        with open(f"{LESSONS}/batches/rc-{n:02d}.tsv", "w") as f:
            for r in rs[k:k + size]:
                f.write("\t".join([r["_rid"], r["type"], r["area"], r["symptom"][:90].replace("\t", " ").replace("\n", " "),
                                   r["root_cause"][:150].replace("\t", " ").replace("\n", " ")]) + "\n")
    print(f"rows={len(rs)} batches={n}")

def collect():
    known = {r["_rid"] for r in rows()}; out = {}; bad = 0
    for f in glob.glob(f"{LESSONS}/classified/rc-*.json"):
        for k, v in json.load(open(f)).items():
            if k in known and re.fullmatch(r"RC(0[1-9]|1\d|2[01]|99)", v): out[k] = v
            else: bad += 1
    json.dump(out, open(f"{LESSONS}/classified/rc_assign.json", "w"))
    print(f"assigned={len(out)}/{len(known)} dropped={bad}")

if __name__ == "__main__":
    {"export": export, "collect": collect}[sys.argv[1]]()
