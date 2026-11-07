#!/usr/bin/env python3
"""Mine surviving transcripts (~/.claude/projects/**/*.jsonl) for Creatrix user corrections.

Session in scope if any line mentions entropic|creatrix. Candidate = real user prompt (not tool_result, not sidechain,
not hook/system text) matching correction language; carries the last assistant text before it (to judge false-done
claims). Prompts already present in history.jsonl (same session + same text prefix) are marked dup_of_history so the
dedupe step merges them instead of double counting.
"""

import json
import os
import re
import glob
from schema import PROJ, LESSONS
from extract_history import CORR, SKIP

SCOPE = re.compile(r"entropic|creatrix", re.I)
NOISE = re.compile(
    r"^\s*(<(command|local-command|system-reminder|task-notification)|Caveat:|\[Request interrupted)",
    re.I,
)


def user_text(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        if any(b.get("type") == "tool_result" for b in c if isinstance(b, dict)):
            return None
        return " ".join(
            b.get("text", "")
            for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return None


def asst_text(msg):
    c = msg.get("content")
    if isinstance(c, list):
        return " ".join(
            b.get("text", "")
            for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return c if isinstance(c, str) else ""


def main():
    hist = load_hist()
    files = glob.glob(f"{PROJ}/**/*.jsonl", recursive=True)
    files = [f for f in files if "/memory/" not in f and "subagents" not in f]
    nin = nc = ndup = 0
    with open(f"{LESSONS}/raw/transcripts_candidates.jsonl", "w") as out:
        for f in files:
            with open(f, errors="replace") as fh:
                raw = fh.read()
            if not SCOPE.search(raw):
                continue
            nin += 1
            c, d_ = process(raw, os.path.basename(f)[:-6], "transcript", hist, out)
            nc += c
            ndup += d_
    print(
        f"transcripts files={len(files)} in_scope={nin} candidates={nc} dup_of_history={ndup}"
    )


def load_hist():
    hist = set()
    hp = f"{LESSONS}/raw/history_scope.jsonl"
    if os.path.exists(hp):
        for l in open(hp):
            r = json.loads(l)
            hist.add((r["session"], r["prompt"][:80]))
    return hist


def process(raw, default_sess, ref_prefix, hist, out):
    """Emit correction candidates from one transcript's raw JSONL text. Returns (candidates, dup_of_history)."""
    nc = ndup = 0
    if True:
        if True:
            last_asst = ""
            for line in raw.splitlines():
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("isSidechain"):
                    continue
                t = d.get("type")
                if t == "assistant":
                    txt = asst_text(d.get("message") or {})
                    if txt.strip():
                        last_asst = txt
                elif (
                    t == "user"
                    and d.get("userType", "external") == "external"
                    and not d.get("isMeta")
                ):
                    txt = user_text(d.get("message") or {})
                    if (
                        not txt
                        or NOISE.match(txt)
                        or SKIP.match(txt)
                        or not CORR.search(txt)
                    ):
                        continue
                    sess = d.get("sessionId") or default_sess
                    dup = (sess, txt.strip()[:80]) in hist
                    ndup += dup
                    out.write(
                        json.dumps(
                            {
                                "cand_id": f"T-{d['uuid'][:13]}",
                                "ref": f"{ref_prefix}:{sess}:{d['uuid']}",
                                "date": (d.get("timestamp") or "")[:10],
                                "cwd": d.get("cwd"),
                                "prompt": txt.strip()[:1200],
                                "prev_assistant": last_asst.strip()[-600:],
                                "dup_of_history": dup,
                            }
                        )
                        + "\n"
                    )
                    nc += 1
    return nc, ndup


if __name__ == "__main__":
    main()
