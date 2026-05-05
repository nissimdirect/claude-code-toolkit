"""
Stage 2: Synthesize self-contained user prompts from raw context snippets.

Reads scenario JSONs produced by extract_naturalistic_scenarios.py, calls
Gemini Flash for each, and replaces `user_prompt` with a synthesized
self-contained instruction. Original raw prompt + context retained in
`synthesis_audit` for inspection.

Per SAP addendum 002. Synthesizer prompt template is FROZEN — modifying it
requires addendum-003 BEFORE re-running.

Usage:
    python3 synthesize_prompts.py scenarios/gate-2-naturalistic/*.json
"""

import json
import re
import sys
import time
from pathlib import Path

# Use the local gemini_draft helper. Add ~/Development/tools to sys.path.
sys.path.insert(0, str(Path.home() / "Development" / "tools"))
try:
    from gemini_draft import draft  # type: ignore[import-not-found]
except ImportError:
    sys.exit("gemini_draft not importable; check ~/Development/tools/gemini_draft.py")

SYNTHESIZER_MODEL = "bulk"  # gemini-2.5-flash-lite
SYNTHESIZER_TEMPERATURE = 0.3

# FROZEN per addendum 002. Do not modify without addendum-003.
SYNTHESIZER_TEMPLATE = """You are reconstructing a single self-contained user instruction from a snippet of conversation between a user and Claude.

Your job: write the instruction the user was effectively asking for at the moment Claude was about to edit `{file_path}`. The instruction should:
- Read as a natural user request (1-3 sentences, plain prose)
- Be specific enough that a fresh Claude session could act on it
- Explicitly mention `{file_path}` (or its filename)
- Describe the change in user-intent terms (what they want done), NOT in diff terms (don't say "replace X with Y" — say what behavior should change)
- NOT include meta commentary like "the user wants" — write as if YOU are the user

The change Claude was about to make:
- File: {file_path}
- Replacing: {old_preview}
- With: {new_preview}

Conversation snippet (last messages leading to the edit):
---
{context_snippet}
---

Output ONLY the instruction. No preamble, no explanation, no quotation marks around it."""

MIN_PROMPT_CHARS = 30
MAX_PROMPT_CHARS = 2000
MAX_RETRY = 2


def synthesize_one(scenario: dict) -> tuple[str | None, str]:
    """Returns (synthesized_prompt | None, status_message)."""
    audit = scenario.get("synthesis_audit", {})
    file_path = next(iter(scenario["pre_existing_files"]), "")
    filename = Path(file_path).name
    context = audit.get("raw_context_snippet", "")
    if not context.strip():
        return None, "empty_context"

    prompt = SYNTHESIZER_TEMPLATE.format(
        file_path=file_path,
        old_preview=audit.get("edit_old_string_preview", ""),
        new_preview=audit.get("edit_new_string_preview", ""),
        context_snippet=context[:6000],
    )

    last_err = ""
    for attempt in range(MAX_RETRY + 1):
        try:
            result = draft(
                prompt=prompt,
                temperature=SYNTHESIZER_TEMPERATURE,
                model=SYNTHESIZER_MODEL,
            )
        except Exception as exc:
            last_err = f"api_error_attempt{attempt}: {exc}"
            time.sleep(1)
            continue

        result = result.strip().strip('"').strip("'")
        # Validate
        if len(result) < MIN_PROMPT_CHARS:
            last_err = f"too_short_attempt{attempt} (n={len(result)})"
            continue
        if len(result) > MAX_PROMPT_CHARS:
            last_err = f"too_long_attempt{attempt} (n={len(result)})"
            continue
        if filename not in result and file_path not in result:
            last_err = f"no_filename_attempt{attempt}"
            continue
        if re.search(r"```|^\s*-\s+", result, flags=re.MULTILINE):
            # Looks like markdown/diff syntax — reject
            last_err = f"diff_syntax_attempt{attempt}"
            continue
        return result, "ok"

    return None, last_err


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("Usage: synthesize_prompts.py <scenario.json> [scenario.json ...]")

    paths = [Path(p) for p in sys.argv[1:]]
    print(
        f"Synthesizing {len(paths)} scenarios with {SYNTHESIZER_MODEL} "
        f"(temp={SYNTHESIZER_TEMPERATURE})",
        file=sys.stderr,
    )

    success = 0
    failures: list[tuple[str, str]] = []

    for i, p in enumerate(paths, start=1):
        scenario = json.loads(p.read_text())
        if scenario.get("synthesis_audit", {}).get("synthesized_user_prompt"):
            print(
                f"[{i}/{len(paths)}] {p.name}: already synthesized — skipping",
                file=sys.stderr,
            )
            continue

        synthesized, status = synthesize_one(scenario)
        if synthesized is None:
            failures.append((p.name, status))
            print(f"[{i}/{len(paths)}] {p.name}: FAIL — {status}", file=sys.stderr)
            continue

        # Update scenario in place
        scenario["synthesis_audit"]["synthesized_user_prompt"] = synthesized
        scenario["synthesis_audit"]["synthesizer_model"] = SYNTHESIZER_MODEL
        scenario["synthesis_audit"]["synthesizer_temperature"] = SYNTHESIZER_TEMPERATURE
        scenario["synthesis_audit"]["synthesized_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        scenario["user_prompt"] = synthesized
        p.write_text(json.dumps(scenario, indent=2))
        success += 1
        print(
            f"[{i}/{len(paths)}] {p.name}: OK ({len(synthesized)} chars)",
            file=sys.stderr,
        )

    print(f"\nDone. Success: {success}/{len(paths)}.", file=sys.stderr)
    if failures:
        print("\nFailures:", file=sys.stderr)
        for name, status in failures:
            print(f"  {name}: {status}", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
