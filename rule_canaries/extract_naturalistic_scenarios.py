"""
Extract naturalistic Phase 1 pilot scenarios from real Claude Code session logs.

Per SAP addendum 001 — pre-registered sampling protocol:

  Source:        ~/.claude/projects/**/*.jsonl modified within last 90 days
  Episode:       (user_message, file_path, file_contents_at_episode, expected_final_state)
                 where the assistant called Edit on file_path AND Read of same file
                 exists in the session.
  Filter:        empty/meta/slash-command prompts, secrets, oversized prompts/files,
                 generated-content paths, missing old_string match, multi-edit episodes.
  Sample:        seed=20260416, no replacement, 30 episodes.
  Stop rule:     if <30 episodes available, halt — re-evaluate sampling window.

Outputs scenarios to scenarios/gate-2-naturalistic/g2n-001.json ... g2n-030.json
plus an extraction-audit.json with provenance per scenario.
"""

import argparse
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Iterator

PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUT_DIR = Path(__file__).parent / "scenarios" / "gate-2-naturalistic"
AUDIT_PATH = (
    Path(__file__).parent / "scenarios" / "gate-2-naturalistic-extraction-audit.json"
)

DAYS_BACK = 90
SAMPLE_SIZE = 30
SAMPLE_SEED = 20260416
MAX_PROMPT_CHARS = 2_000
MIN_PROMPT_CHARS = 30  # filters "yeah", "ok", "go" continuations
MAX_FILE_CHARS = 10_000

# Patterns we exclude
META_PROMPT_PATTERNS = [
    re.compile(r"^<local-command-caveat>"),
    re.compile(r"^<local-command-stdout>"),
    re.compile(r"^<local-command-stderr>"),
    re.compile(r"^<command-name>"),
    re.compile(r"^<command-message>"),
    re.compile(r"^<system-reminder>"),
    re.compile(r"^<teammate-message"),  # subagent/team messages
    re.compile(r"^Caveat:"),
    re.compile(r"^Ready to code\?"),
    re.compile(r"^/[a-z][a-z0-9_-]*\s*$", re.MULTILINE),  # bare slash command
]
# Files we exclude (subagent sessions, not user-facing)
SESSION_FILE_EXCLUSIONS = [
    re.compile(r"^agent-"),  # agent-*.jsonl are subagent sessions
]
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # API keys
    re.compile(r"ghp_[a-zA-Z0-9]{20,}"),  # GitHub PAT
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
]
PATH_EXCLUSION_PATTERNS = [
    re.compile(r"^/tmp/"),
    re.compile(r"^/private/"),
    re.compile(r"/\.git/"),
    re.compile(r"/node_modules/"),
    re.compile(r"/\.cache/"),
    re.compile(r"/__pycache__/"),
    re.compile(r"/\.venv/"),
    re.compile(r"/dist/"),
    re.compile(r"/build/"),
]


def is_meta_prompt(text: str) -> bool:
    return any(p.match(text) for p in META_PROMPT_PATTERNS)


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)


def excluded_path(path: str) -> bool:
    return any(p.search(path) for p in PATH_EXCLUSION_PATTERNS)


def strip_line_numbers(read_result: str) -> str:
    """Claude Code's Read tool prepends 'N\\t' to each line. Strip it.

    Returns the original file content. If the format doesn't match (e.g.,
    error message), returns the input unchanged.
    """
    lines = read_result.splitlines(keepends=False)
    stripped: list[str] = []
    for ln in lines:
        m = re.match(r"^(\d+)\t(.*)$", ln)
        if m:
            stripped.append(m.group(2))
        else:
            return read_result  # not a Read result — return as-is
    return "\n".join(stripped) + ("\n" if read_result.endswith("\n") else "")


CONTEXT_BUFFER_MAX = 20  # ~10 user+assistant round trips
CONTEXT_MESSAGE_TRUNCATE = 600  # per-message char cap to keep context bounded


def format_context_snippet(buffer: list[dict]) -> str:
    """Format the rolling context buffer as a readable snippet for the synthesizer."""
    lines: list[str] = []
    for entry in buffer:
        role = entry.get("role", "?").upper()
        text = entry.get("text", "")
        lines.append(f"{role}: {text}")
    return "\n\n".join(lines)


def parse_session(jsonl_path: Path) -> Iterator[dict]:
    """Yield candidate episodes from one session log.

    An episode is a dict with: user_prompt, target_file_path, file_contents,
    edit_old_string, edit_new_string, replace_all, source_session,
    source_line_idx, raw_context_snippet.
    """
    from collections import deque

    last_user_text: str | None = None
    pending_reads: dict[str, str] = {}
    file_contents_cache: dict[str, str] = {}
    edits_seen_per_file: dict[str, int] = {}
    context_buffer: "deque[dict]" = deque(maxlen=CONTEXT_BUFFER_MAX)

    with jsonl_path.open() as f:
        for line_idx, line in enumerate(f):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = event.get("type")

            if etype == "user":
                msg = event.get("message", {})
                content = msg.get("content")
                if event.get("isMeta"):
                    continue
                if isinstance(content, str):
                    if not is_meta_prompt(content):
                        last_user_text = content
                        context_buffer.append(
                            {"role": "user", "text": content[:CONTEXT_MESSAGE_TRUNCATE]}
                        )
                elif isinstance(content, list):
                    # Could be plain text blocks OR tool_results
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "tool_result":
                            tool_use_id = block.get("tool_use_id")
                            if tool_use_id in pending_reads:
                                file_path = pending_reads.pop(tool_use_id)
                                result = block.get("content", "")
                                if isinstance(result, list):
                                    # Multi-block content; take text blocks
                                    result = "".join(
                                        b.get("text", "")
                                        for b in result
                                        if isinstance(b, dict)
                                        and b.get("type") == "text"
                                    )
                                if isinstance(result, str) and not block.get(
                                    "is_error"
                                ):
                                    file_contents_cache[file_path] = strip_line_numbers(
                                        result
                                    )
                        elif block.get("type") == "text":
                            text = block.get("text", "")
                            if isinstance(text, str) and not is_meta_prompt(text):
                                last_user_text = text
                                context_buffer.append(
                                    {
                                        "role": "user",
                                        "text": text[:CONTEXT_MESSAGE_TRUNCATE],
                                    }
                                )

            elif etype == "assistant":
                msg = event.get("message", {})
                content = msg.get("content", [])
                if not isinstance(content, list):
                    continue
                # Collect this assistant message's text + tool calls for the buffer
                asst_text_parts: list[str] = []
                asst_tool_summary: list[str] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        t = block.get("text", "")
                        if isinstance(t, str):
                            asst_text_parts.append(t)
                    elif btype == "tool_use":
                        name = block.get("name")
                        inp = block.get("input", {})
                        # Brief summary for context (first arg only, truncated)
                        first_val = next(
                            (v for v in inp.values() if isinstance(v, str)), ""
                        )
                        asst_tool_summary.append(f"{name}({first_val[:60]})")
                        if name == "Read":
                            fp = inp.get("file_path")
                            if isinstance(fp, str):
                                pending_reads[block.get("id", "")] = fp
                        elif name == "Edit":
                            fp = inp.get("file_path")
                            old = inp.get("old_string")
                            new = inp.get("new_string")
                            replace_all = bool(inp.get("replace_all", False))
                            if not (
                                isinstance(fp, str)
                                and isinstance(old, str)
                                and isinstance(new, str)
                            ):
                                continue
                            if last_user_text is None:
                                continue
                            if fp not in file_contents_cache:
                                continue  # no Read = can't reconstruct synthetic_fs
                            edits_seen_per_file[fp] = edits_seen_per_file.get(fp, 0) + 1
                            if edits_seen_per_file[fp] > 1:
                                continue  # multi-edit episode — exclude
                            yield {
                                "user_prompt": last_user_text,
                                "target_file_path": fp,
                                "file_contents": file_contents_cache[fp],
                                "edit_old_string": old,
                                "edit_new_string": new,
                                "replace_all": replace_all,
                                "source_session": jsonl_path.name,
                                "source_line_idx": line_idx,
                                "raw_context_snippet": format_context_snippet(
                                    list(context_buffer)
                                ),
                            }
                # Push assistant message into context buffer
                asst_text = " ".join(asst_text_parts).strip()
                tools_str = (
                    "  [tools: " + ", ".join(asst_tool_summary) + "]"
                    if asst_tool_summary
                    else ""
                )
                buffer_text = (asst_text[:CONTEXT_MESSAGE_TRUNCATE] + tools_str).strip()
                if buffer_text:
                    context_buffer.append({"role": "assistant", "text": buffer_text})


def passes_filters(episode: dict) -> tuple[bool, str]:
    """Apply SAP §6 exclusion criteria. Returns (passes, reason_if_not)."""
    prompt = episode["user_prompt"]
    if not prompt or not prompt.strip():
        return False, "empty_prompt"
    if is_meta_prompt(prompt):
        return False, "meta_prompt"
    if len(prompt) < MIN_PROMPT_CHARS:
        return False, "prompt_too_short"
    if len(prompt) > MAX_PROMPT_CHARS:
        return False, "prompt_too_long"
    if contains_secret(prompt):
        return False, "secret_in_prompt"
    if excluded_path(episode["target_file_path"]):
        return False, "excluded_path"
    if len(episode["file_contents"]) > MAX_FILE_CHARS:
        return False, "file_too_large"
    old = episode["edit_old_string"]
    if not old:
        return False, "empty_old_string"
    if old not in episode["file_contents"]:
        return False, "old_string_not_in_captured_file"  # Read happened too late
    # Check that Edit would succeed: replace_all=False requires uniqueness
    if not episode["replace_all"]:
        if episode["file_contents"].count(old) > 1:
            return False, "old_string_not_unique"
    return True, ""


def apply_edit(contents: str, old: str, new: str, replace_all: bool) -> str:
    if replace_all:
        return contents.replace(old, new)
    return contents.replace(old, new, 1)


def make_synthetic_path(real_path: str) -> str:
    """Strip user-specific path prefix to make synthetic paths portable.

    Real: /Users/nissimagent/Development/ghostwriter/scripts/multi_roll.py
    Synth: ghostwriter/scripts/multi_roll.py
    """
    p = real_path
    p = re.sub(r"^/Users/[^/]+/", "", p)
    p = re.sub(r"^Development/", "", p)
    p = re.sub(r"^\.claude/", ".claude/", p)
    return p


def episode_to_scenario(episode: dict, scenario_id: str) -> dict:
    synthetic_path = make_synthetic_path(episode["target_file_path"])
    after = apply_edit(
        episode["file_contents"],
        episode["edit_old_string"],
        episode["edit_new_string"],
        episode["replace_all"],
    )
    # Rewrite the user prompt to use the synthetic path if the real path was mentioned
    user_prompt = episode["user_prompt"].replace(
        episode["target_file_path"], synthetic_path
    )
    raw_context = episode.get("raw_context_snippet", "")
    raw_context_redacted = raw_context.replace(
        episode["target_file_path"], synthetic_path
    )
    return {
        "scenario_id": scenario_id,
        "user_prompt": user_prompt,
        "synthetic_fs": {synthetic_path: episode["file_contents"]},
        "pre_existing_files": [synthetic_path],
        "expected_final_state": {synthetic_path: after},
        "max_iterations": 20,
        "notes": (
            f"Naturalistic — sampled from {episode['source_session']} "
            f"line {episode['source_line_idx']}."
        ),
        "synthesis_audit": {
            "raw_user_prompt": user_prompt,
            "raw_context_snippet": raw_context_redacted,
            "edit_old_string_preview": episode["edit_old_string"][:200],
            "edit_new_string_preview": episode["edit_new_string"][:200],
            "synthesized_user_prompt": None,
            "synthesizer_model": None,
            "synthesizer_temperature": None,
            "synthesized_at": None,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run", action="store_true", help="Only enumerate; do not write"
    )
    ap.add_argument("--days-back", type=int, default=DAYS_BACK)
    ap.add_argument("--sample-size", type=int, default=SAMPLE_SIZE)
    ap.add_argument("--seed", type=int, default=SAMPLE_SEED)
    args = ap.parse_args()

    if not PROJECTS_DIR.exists():
        sys.exit(f"projects dir not found: {PROJECTS_DIR}")

    cutoff_ts = time.time() - (args.days_back * 86_400)
    print(
        f"Scanning {PROJECTS_DIR} (modified within last {args.days_back} days)",
        file=sys.stderr,
    )

    log_paths = [
        p
        for p in PROJECTS_DIR.rglob("*.jsonl")
        if p.stat().st_mtime >= cutoff_ts
        and not any(rx.match(p.name) for rx in SESSION_FILE_EXCLUSIONS)
    ]
    print(
        f"Found {len(log_paths)} session logs in window (post agent-* exclusion)",
        file=sys.stderr,
    )

    all_episodes: list[dict] = []
    exclusion_counts: dict[str, int] = {}

    for i, p in enumerate(log_paths):
        if i and i % 500 == 0:
            print(
                f"  scanned {i}/{len(log_paths)}; episodes so far: {len(all_episodes)}",
                file=sys.stderr,
            )
        try:
            for ep in parse_session(p):
                ok, reason = passes_filters(ep)
                if ok:
                    all_episodes.append(ep)
                else:
                    exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
        except Exception:
            exclusion_counts.setdefault("parse_error", 0)
            exclusion_counts["parse_error"] += 1

    print(
        f"\nFiltered episode universe: {len(all_episodes)} candidates", file=sys.stderr
    )
    print(
        f"Exclusion counts: {json.dumps(exclusion_counts, indent=2)}", file=sys.stderr
    )

    if len(all_episodes) < args.sample_size:
        print(
            f"\nINSUFFICIENT EPISODES: {len(all_episodes)} < {args.sample_size}",
            file=sys.stderr,
        )
        print(
            "Per SAP addendum 001, halt or widen window before sampling.",
            file=sys.stderr,
        )
        if not args.dry_run:
            return 2

    # Deterministic shuffle, take first N
    rng = random.Random(args.seed)
    rng.shuffle(all_episodes)
    selected = all_episodes[: args.sample_size]
    overflow = all_episodes[args.sample_size : args.sample_size + 30]  # for swap-ins

    print(
        f"\nSelected: {len(selected)} (with {len(overflow)} overflow for swap-ins)",
        file=sys.stderr,
    )

    if args.dry_run:
        print("\nDRY RUN — first 5 selected episodes:", file=sys.stderr)
        for i, ep in enumerate(selected[:5]):
            print(
                f"\n  [{i + 1}] {ep['source_session']}:{ep['source_line_idx']}",
                file=sys.stderr,
            )
            print(f"      file: {ep['target_file_path']}", file=sys.stderr)
            print(f"      prompt[:200]: {ep['user_prompt'][:200]!r}", file=sys.stderr)
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[dict] = []
    for i, ep in enumerate(selected, start=1):
        scenario_id = f"g2n-{i:03d}"
        scenario = episode_to_scenario(ep, scenario_id)
        out = OUT_DIR / f"{scenario_id}.json"
        out.write_text(json.dumps(scenario, indent=2))
        written.append(
            {
                "scenario_id": scenario_id,
                "source_session": ep["source_session"],
                "source_line_idx": ep["source_line_idx"],
                "real_target_file": ep["target_file_path"],
                "prompt_preview": ep["user_prompt"][:200],
                "scenario_sha256": hashlib.sha256(Path(out).read_bytes()).hexdigest(),
            }
        )

    audit = {
        "extracted_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scan_window_days": args.days_back,
        "logs_scanned": len(log_paths),
        "filtered_episode_universe_size": len(all_episodes),
        "exclusion_counts": exclusion_counts,
        "sample_seed": args.seed,
        "sample_size": args.sample_size,
        "selected_scenarios": written,
        "overflow_episodes_available_for_user_swap": len(overflow),
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2))

    print(f"\nWrote {len(written)} scenarios to {OUT_DIR}", file=sys.stderr)
    print(f"Audit: {AUDIT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
