#!/usr/bin/env python3
"""Mine transcripts that only survive in the ~/.claude auto-backup repo.

auto-backup.sh commits ~/.claude nightly; its first commit (e3211c5, 2026-02-09) captured 356 session transcripts
from 2026-02-07..09 before .gitignore excluded projects/*. Those files are gone from disk. Same candidate logic as
extract_transcripts.py; refs are cfgtranscript:<sessionId>:<uuid>. Subagent (agent-*) files are skipped (no user prompts).
Output: raw/cfg_transcripts_candidates.jsonl
"""
import subprocess
import os
from schema import LESSONS, CFG_REPO, CFG_COMMIT
from extract_transcripts import SCOPE, process, load_hist


def git(*a):
    return subprocess.run(["git", "-C", CFG_REPO, *a], capture_output=True, text=True, errors="replace").stdout


def main():
    paths = [p for p in git("ls-tree", "-r", "--name-only", CFG_COMMIT, "projects/-Users-nissimagent/").split()
             if p.endswith(".jsonl") and not os.path.basename(p).startswith("agent-")]
    hist = load_hist()
    nin = nc = ndup = 0
    with open(f"{LESSONS}/raw/cfg_transcripts_candidates.jsonl", "w") as out:
        for p in paths:
            raw = git("show", f"{CFG_COMMIT}:{p}")
            if not SCOPE.search(raw):
                continue
            nin += 1
            c, d = process(raw, os.path.basename(p)[:-6], "cfgtranscript", hist, out)
            nc += c
            ndup += d
    print(f"cfg transcripts main-session files={len(paths)} in_scope={nin} candidates={nc} dup_of_history={ndup}")


if __name__ == "__main__":
    main()
