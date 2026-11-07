#!/usr/bin/env python3
"""Merge classified/*.jsonl into ledger.jsonl with dedupe + recurrence counting.

Dedupe (union-find):
  1. deterministic: two rows from DIFFERENT candidates that share a concrete ref (source_ref/fix_ref/also_refs, incl.
     PR# <-> its merge/squash commit via raw/gh_prs.jsonl) AND the same area  -> same incident.
  2. transcript rows flagged dup_of_history are joined to the matching history row by session+text (already same ref
     family, handled via incident_key + date).
  3. semantic: classified/merges.json = [[row_id, row_id, ...], ...] produced by the dedupe agents.
recurrence_count = number of distinct occurrences in a cluster = distinct (fix_ref or ISO-week of date) values.
id = CX-<sha1 of the earliest member's row id>[:8]  (stable across rebuilds as long as that member exists).
"""

import json
import glob
import os
import hashlib
import collections
import datetime
from schema import LESSONS, REQUIRED

SRC_PRIORITY = ["gh", "git", "docs", "history", "transcripts", "memory"]


def load():
    rows = []
    for f in sorted(glob.glob(f"{LESSONS}/classified/*.jsonl")):
        for l in open(f):
            if l.strip():
                r = json.loads(l)
                r["_file"] = os.path.basename(f)
                rows.append(r)
    return rows


def pr_commit_alias():
    alias = {}
    p = f"{LESSONS}/raw/gh_prs.jsonl"
    if os.path.exists(p):
        for l in open(p):
            pr = json.loads(l)
            if pr.get("mergeCommit"):
                alias[pr["mergeCommit"][:10]] = f"PR#{pr['number']}"
    return alias


def norm(ref, alias):
    if not ref:
        return None
    ref = ref.strip()
    if all(c in "0123456789abcdef" for c in ref) and len(ref) >= 7:
        return alias.get(ref[:10], f"sha:{ref[:10]}")
    return ref


def issue_numbers():
    p = f"{LESSONS}/raw/gh_issues.jsonl"
    return {json.loads(l)["number"] for l in open(p)} if os.path.exists(p) else set()


def canon_refs(rows):
    """GitHub shares PR/issue numbering; classifiers write `#426` as PR#426 even when it is an issue."""
    iss = issue_numbers()
    fix = lambda x: f"issue#{x[3:]}" if isinstance(x, str) and x.startswith("PR#") and x[3:].isdigit() and int(x[3:]) in iss else x
    for r in rows:
        r["source_ref"] = fix(r["source_ref"]); r["fix_ref"] = fix(r.get("fix_ref"))
        r["also_refs"] = [fix(x) for x in r.get("also_refs") or []]


def main():
    rows = load()
    canon_refs(rows)
    alias = pr_commit_alias()
    key = lambda r: f"{r['_file']}::{r['id']}"
    parent = {key(r): key(r) for r in rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    by_ref = collections.defaultdict(list)
    for r in rows:
        refs = {
            norm(x, alias)
            for x in [
                r.get("source_ref"),
                r.get("fix_ref"),
                *(r.get("also_refs") or []),
            ]
        } - {None}
        for x in refs:
            by_ref[(x, r["area"])].append(r)
    for group in by_ref.values():
        # only merge across candidates; one candidate's multiple rows are distinct incidents by construction
        cands = {}
        for r in group:
            cands.setdefault(r.get("cand_id"), r)
        reps = list(cands.values())
        for a in reps[1:]:
            # avoid collapsing multi-bug PRs: require same type or same incident_key
            if a["type"] == reps[0]["type"] or a.get("incident_key") == reps[0].get(
                "incident_key"
            ):
                union(key(a), key(reps[0]))
    mp = f"{LESSONS}/classified/merges.json"
    if os.path.exists(mp):
        for grp in json.load(open(mp)):
            ks = [i for i in grp if i in parent]
            for k in ks[1:]:
                union(k, ks[0])

    rcp = f"{LESSONS}/classified/rc_assign.json"
    rc = json.load(open(rcp)) if os.path.exists(rcp) else {}

    clusters = collections.defaultdict(list)
    for r in rows:
        clusters[find(key(r))].append(r)
    out = []
    for members in clusters.values():
        members.sort(
            key=lambda r: (
                r["date"],
                SRC_PRIORITY.index(r["source"]) if r["source"] in SRC_PRIORITY else 9,
            )
        )
        first = members[0]
        best = max(
            members,
            key=lambda r: (r.get("confidence") or 0, len(r.get("root_cause", ""))),
        )
        occ = set()
        for m in members:
            d = datetime.date.fromisoformat(m["date"])
            occ.add(
                norm(m.get("fix_ref"), alias)
                or f"wk{d.isocalendar()[0]}-{d.isocalendar()[1]}"
            )
        refs = []
        for m in members:
            for x in [m["source_ref"], m.get("fix_ref"), *(m.get("also_refs") or [])]:
                if x and x not in refs and x != first["source_ref"]:
                    refs.append(x)
        row = {k: first[k] for k in REQUIRED}
        row.update(
            {
                k: best[k]
                for k in ("area", "type", "symptom", "root_cause", "prevention")
            }
        )
        row["id"] = (
            "CX-"
            + hashlib.sha1(f"{first['_file']}::{first['id']}".encode()).hexdigest()[:8]
        )
        row["fix_ref"] = next(
            (m["fix_ref"] for m in reversed(members) if m.get("fix_ref")), None
        )
        row["user_quote"] = next(
            (m["user_quote"] for m in members if m.get("user_quote")), None
        )
        row["recurrence_count"] = max(1, len(occ))
        row["also_refs"] = refs
        row["sources"] = sorted({m["source"] for m in members})
        row["incident_key"] = best.get("incident_key")
        row["member_ids"] = [m["id"] for m in members]
        votes = collections.Counter(rc.get(key(m)) for m in members if rc.get(key(m)))
        row["root_cause_cluster"] = votes.most_common(1)[0][0] if votes else None
        row["confidence"] = round(
            sum(m.get("confidence") or 0 for m in members) / len(members), 2
        )
        out.append(row)
    out.sort(key=lambda r: (r["date"], r["id"]))
    with open(f"{LESSONS}/ledger.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    multi = sum(1 for r in out if len(r["member_ids"]) > 1)
    print(
        f"classified_rows={len(rows)} incidents={len(out)} merged_clusters={multi} "
        f"recurring(>1)={sum(r['recurrence_count'] > 1 for r in out)}"
    )
    print("by source:", dict(collections.Counter(s for r in out for s in r["sources"])))
    print("by type:", dict(collections.Counter(r["type"] for r in out)))


if __name__ == "__main__":
    main()
