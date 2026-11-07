#!/usr/bin/env python3
"""Hard oracle: schema-check every row and resolve every source_ref (+ fix_ref and also_refs when present).

Usage: validate.py [ledger.jsonl ...]   (default: ~/Development/creatrix-lessons/ledger.jsonl)
Exit 0 only if 100% of rows pass. Prints pass rate + first failures.
"""

import json
import sys
import collections
from schema import row_errors, resolves, LESSONS


def check(path):
    rows, fails, reasons = 0, [], collections.Counter()
    ids = collections.Counter()
    for n, line in enumerate(open(path), 1):
        if not line.strip():
            continue
        rows += 1
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            fails.append((n, ["invalid json"]))
            reasons["invalid json"] += 1
            continue
        errs = row_errors(r)
        ids[r.get("id")] += 1
        if not errs:
            if not resolves(r["source_ref"]):
                errs.append(f"source_ref unresolved: {r['source_ref']}")
            fr = r.get("fix_ref")
            if fr and not resolves(fr):
                errs.append(f"fix_ref unresolved: {fr}")
            for a in r.get("also_refs") or []:
                if not resolves(a):
                    errs.append(f"also_ref unresolved: {a}")
        if errs:
            fails.append((n, errs))
            for e in errs:
                reasons[e.split(":")[0]] += 1
    dup = [i for i, c in ids.items() if c > 1]
    if dup:
        fails.append((0, [f"duplicate ids: {dup[:5]}"]))
        reasons["duplicate id"] += len(dup)
    ok = rows - len({n for n, _ in fails if n})
    print(f"{path}: {ok}/{rows} rows pass ({100 * ok / max(rows, 1):.1f}%)")
    for k, v in reasons.most_common():
        print(f"  {v:5d}  {k}")
    for n, e in fails[:10]:
        print(f"  line {n}: {'; '.join(e)[:200]}")
    return ok == rows and not dup


if __name__ == "__main__":
    paths = sys.argv[1:] or [f"{LESSONS}/ledger.jsonl"]
    sys.exit(0 if all([check(p) for p in paths]) else 1)
