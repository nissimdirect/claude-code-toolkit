"""Ledger schema + source_ref resolver. Single source of truth for validate.py and classifier briefs.

source_ref canonical forms (one per row; extra refs go in `also_refs`):
  <sha7-40>                       commit in entropic-v2challenger (any ref, incl. wip-backup/*)
  entropic@<sha>                  commit in ~/Development/entropic (v1)
  PR#<n> | issue#<n>              GitHub nissimdirect/entropic-v2challenger
  repo:<path>:<line>              file at origin/main in entropic-v2challenger
  memory:<file>:<line>            ~/.claude/projects/-Users-nissimagent/memory/<file>
  obsidian:<relpath>:<line>       ~/Documents/Obsidian/<relpath>
  history:<timestamp_ms>          ~/.claude/history.jsonl prompt (exact `timestamp`)
  transcript:<sessionId>:<uuid>   ~/.claude/projects/**/<sessionId>.jsonl message uuid
  cfgtranscript:<sessionId>:<uuid>  same, but the transcript only survives in the ~/.claude auto-backup git repo
                                  (private repo, commit e3211c5, 2026-02-09)
"""

import json
import os
import re
import subprocess
from functools import lru_cache

HOME = os.path.expanduser("~")
V2 = f"{HOME}/Development/entropic-v2challenger"
V1 = f"{HOME}/Development/entropic"
MEM = f"{HOME}/.claude/projects/-Users-nissimagent/memory"
OBS = f"{HOME}/Documents/Obsidian"
HIST = f"{HOME}/.claude/history.jsonl"
PROJ = f"{HOME}/.claude/projects"
LESSONS = f"{HOME}/Development/creatrix-lessons"

TYPES = {
    "bug",
    "regression",
    "revert",
    "design-reversal",
    "spec-gap",
    "misunderstanding",
    "process-failure",
    "false-done-claim",
}
AREAS = {
    "timeline",
    "effects",
    "routing",
    "ui-shell",
    "ipc",
    "perf",
    "export",
    "build/ci",
    "audio",
    "testing",
    "data/persistence",
    "security",
    "process",
    "docs",
    "other",
}
REQUIRED = {
    "id": str,
    "date": str,
    "source": str,
    "source_ref": str,
    "area": str,
    "type": str,
    "symptom": str,
    "root_cause": str,
    "fix_ref": (str, type(None)),
    "user_quote": (str, type(None)),
    "recurrence_count": int,
    "prevention": str,
}
SOURCES = {"history", "transcripts", "git", "gh", "docs", "memory"}
DATE = re.compile(r"^2026-\d\d-\d\d$")


def row_errors(r):
    errs = []
    for k, t in REQUIRED.items():
        if k not in r:
            errs.append(f"missing {k}")
        elif not isinstance(r[k], t):
            errs.append(f"bad type {k}")
    if errs:
        return errs
    if not DATE.match(r["date"]) or r["date"] < "2026-02-01":
        errs.append(f"bad date {r['date']}")
    if r["type"] not in TYPES:
        errs.append(f"bad type value {r['type']}")
    if r["area"] not in AREAS:
        errs.append(f"bad area {r['area']}")
    if r["source"] not in SOURCES:
        errs.append(f"bad source {r['source']}")
    if r["recurrence_count"] < 1:
        errs.append("recurrence_count<1")
    for k in ("symptom", "root_cause", "prevention"):
        if len(r[k].strip()) < 12:
            errs.append(f"{k} too short")
    return errs


@lru_cache(None)
def _git_ok(repo, sha):
    return (
        subprocess.run(
            ["git", "-C", repo, "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True,
        ).returncode
        == 0
    )


@lru_cache(None)
def _gh_numbers(kind):
    f = f"{LESSONS}/raw/gh_{kind}.jsonl"
    if not os.path.exists(f):
        return frozenset()
    return frozenset(json.loads(l)["number"] for l in open(f) if l.strip())


@lru_cache(None)
def _hist_ts():
    return frozenset(json.loads(l).get("timestamp") for l in open(HIST) if l.strip())


@lru_cache(None)
def _transcript_uuids(session):
    for root, _, files in os.walk(PROJ):
        if f"{session}.jsonl" in files:
            out = set()
            for l in open(os.path.join(root, f"{session}.jsonl"), errors="replace"):
                try:
                    out.add(json.loads(l).get("uuid"))
                except Exception:
                    pass
            return frozenset(out)
    return frozenset()


@lru_cache(None)
def _main_lines(path):
    p = subprocess.run(
        ["git", "-C", V2, "show", f"origin/main:{path}"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return p.stdout.count("\n") if p.returncode == 0 else 0


def _file_line(base, rel, line):
    p = os.path.realpath(os.path.join(base, rel))
    if not p.startswith(os.path.realpath(base)) or not os.path.isfile(p):
        return False
    with open(p, errors="replace") as f:
        return sum(1 for _ in f) >= int(line)


def resolves(ref):
    """Return True iff the ref points at something that exists."""
    if not isinstance(ref, str):
        return False
    ref = ref.strip()
    if m := re.fullmatch(r"[0-9a-f]{7,40}", ref):
        return _git_ok(V2, ref)
    if m := re.fullmatch(r"entropic@([0-9a-f]{7,40})", ref):
        return _git_ok(V1, m[1])
    if m := re.fullmatch(r"PR#(\d+)", ref):
        return int(m[1]) in _gh_numbers("prs")
    if m := re.fullmatch(r"issue#(\d+)", ref):
        return int(m[1]) in _gh_numbers("issues")
    if m := re.fullmatch(
        r"repo:(.+):(\d+)", ref
    ):  # pinned to origin/main, not the checked-out branch
        return _main_lines(m[1]) >= int(m[2]) > 0
    if m := re.fullmatch(r"(memory|obsidian):(.+):(\d+)", ref):
        base = {"memory": MEM, "obsidian": OBS}[m[1]]
        return _file_line(base, m[2], m[3])
    if m := re.fullmatch(r"history:(\d+)", ref):
        return int(m[1]) in _hist_ts()
    if m := re.fullmatch(r"transcript:([0-9a-f-]{36}):([0-9a-f-]{36})", ref):
        return m[2] in _transcript_uuids(m[1])
    if m := re.fullmatch(r"cfgtranscript:([0-9a-f-]{36}):([0-9a-f-]{36})", ref):
        return m[2] in _cfg_transcript_uuids(m[1])
    return False


CFG_REPO = f"{HOME}/.claude"
CFG_COMMIT = "e3211c5"


@lru_cache(maxsize=None)
def _cfg_transcript_uuids(session):
    p = subprocess.run(["git", "-C", CFG_REPO, "show", f"{CFG_COMMIT}:projects/-Users-nissimagent/{session}.jsonl"],
                       capture_output=True, text=True, errors="replace")
    if p.returncode:
        return frozenset()
    out = set()
    for l in p.stdout.splitlines():
        try:
            out.add(json.loads(l).get("uuid"))
        except Exception:
            pass
    return frozenset(out)
