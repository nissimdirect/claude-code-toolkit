#!/usr/bin/env python3
"""Filter ~/.claude/history.jsonl to Creatrix/Entropic prompts and flag correction language.

Creatrix scope = project path matches entropic|creatrix, OR prompt text mentions creatrix|entropic, OR the prompt's
sessionId had any in-scope prompt (session that touched the repos).
Candidates = in-scope prompts with correction/bug language. Each carries the previous prompt of the same session.
Writes raw/history_scope.jsonl (all in-scope, compact) and raw/history_candidates.jsonl.
"""

import json
import re
import datetime
import collections
from schema import HIST, LESSONS

SCOPE_PATH = re.compile(r"entropic|creatrix", re.I)
SCOPE_TEXT = re.compile(r"\b(creatrix|entropic)\b", re.I)
CORR = re.compile(
    r"(^\s*no\b|^\s*nope|\bwrong\b|not what i|that'?s not|still (broken|not|doesn'?t|isn'?t|fail)|you said|"
    r"\bworse\b|doesn'?t work|does not work|didn'?t work|not working|isn'?t working|\bbroke(n)?\b|"
    r"\bbug\b|regress|\brevert|undo|why (did|is|are|does|isn'?t|didn'?t)|i (said|asked|told)|"
    r"\bagain\b|\bstop\b|don'?t (do|change|touch)|never (asked|said)|\bmissing\b|disappear|"
    r"crash|freez|black screen|blank|nothing happens|can'?t (see|click|find)|not (showing|visible|rendering)|"
    r"supposed to|should (be|have|not)|instead of|lied|false|not (done|fixed)|you didn'?t|still see)",
    re.I,
)
SKIP = re.compile(r"^\s*(/\w+\s*$|yes\b|ok\b|y$|continue$|go$)", re.I)


def ts_date(ms):
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def main():
    rows = [json.loads(l) for l in open(HIST) if l.strip()]
    rows.sort(key=lambda r: r.get("timestamp", 0))
    sessions = {
        r.get("sessionId")
        for r in rows
        if SCOPE_PATH.search(r.get("project") or "")
        or SCOPE_TEXT.search(r.get("display") or "")
    }
    sessions.discard(None)
    scope = [
        r
        for r in rows
        if r.get("timestamp", 0) >= 1769904000000
        and (  # 2026-02-01
            SCOPE_PATH.search(r.get("project") or "")
            or SCOPE_TEXT.search(r.get("display") or "")
            or r.get("sessionId") in sessions
        )
    ]
    prev = {}
    nc = 0
    with (
        open(f"{LESSONS}/raw/history_scope.jsonl", "w") as sf,
        open(f"{LESSONS}/raw/history_candidates.jsonl", "w") as cf,
    ):
        for r in scope:
            text = (r.get("display") or "").strip()
            pasted = " ".join(
                str(v.get("content", ""))[:300]
                for v in (r.get("pastedContents") or {}).values()
                if isinstance(v, dict)
            )
            rec = {
                "ref": f"history:{r['timestamp']}",
                "date": ts_date(r["timestamp"]),
                "session": r.get("sessionId"),
                "project": r.get("project"),
                "prompt": text[:1200],
            }
            sf.write(json.dumps(rec) + "\n")
            if text and not SKIP.match(text) and CORR.search(text):
                rec["prev_prompt"] = prev.get(r.get("sessionId"), "")[:400]
                if pasted:
                    rec["pasted_excerpt"] = pasted[:400]
                rec["cand_id"] = f"H-{r['timestamp']}"
                cf.write(json.dumps(rec) + "\n")
                nc += 1
            prev[r.get("sessionId")] = text
    print(
        f"history total={len(rows)} creatrix_sessions={len(sessions)} in_scope={len(scope)} candidates={nc}"
    )


if __name__ == "__main__":
    main()
