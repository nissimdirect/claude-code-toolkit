#!/usr/bin/env python3
"""Delegation Analyzer — Retroactive analysis of what COULD have been delegated.

Scans session JSONL transcripts, classifies user prompts using llm_router,
and estimates how many tokens were "wasted" on Opus for delegatable tasks.

Usage:
    python3 delegation_analyzer.py                    # Analyze last 5 sessions
    python3 delegation_analyzer.py --sessions 20      # Analyze last 20 sessions
    python3 delegation_analyzer.py --live              # Analyze live audit log
    python3 delegation_analyzer.py --assumptions       # Show/validate assumptions
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Development" / "tools"))
from llm_router import classify_task, contains_secrets

SESSION_DIR = Path.home() / ".claude" / "projects" / "-Users-nissimagent"
AUDIT_LOG = Path.home() / ".claude" / ".locks" / "delegation-hook-audit.log"

# Initial assumptions (hypotheses to validate)
ASSUMPTIONS = {
    "research_pct": {
        "hypothesis": 48,  # Validated 2026-02-15 (was 35, actual 48.3% on 263 prompts)
        "description": "% of prompts that are research/summarization (delegatable to Gemini)",
        "actual": None,
    },
    "simple_qa_pct": {
        "hypothesis": 1,  # Validated 2026-02-15 (was 15, actual 1.1% — we rarely ask simple Q&A)
        "description": "% of prompts that are simple Q&A (delegatable to Ollama)",
        "actual": None,
    },
    "code_gen_pct": {
        "hypothesis": 3,  # Validated 2026-02-15 (was 10, actual 3.0%)
        "description": "% of prompts that are code generation (delegatable to Qwen)",
        "actual": None,
    },
    "claude_only_pct": {
        "hypothesis": 48,  # Validated 2026-02-15 (was 40, actual 47.5% incl secrets)
        "description": "% of prompts that require Claude (strategy/security/tools/secrets)",
        "actual": None,
    },
    "potential_savings_pct": {
        "hypothesis": 52,  # Validated 2026-02-15 (was 45, actual 52.5%)
        "description": "% of total prompts that could be delegated to free models",
        "actual": None,
    },
}


def extract_user_messages(jsonl_path: Path, max_messages: int = 200) -> list[str]:
    """Extract user messages from a session JSONL file."""
    messages = []
    try:
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Claude Code JSONL format: type="user", content in entry["message"]["content"]
                    if entry.get("type") == "user":
                        msg = entry.get("message", {})
                        content = msg.get("content", "") if isinstance(msg, dict) else ""
                        if isinstance(content, list):
                            text_parts = [
                                p.get("text", "")
                                for p in content
                                if isinstance(p, dict) and p.get("type") == "text"
                            ]
                            content = " ".join(text_parts)
                        if isinstance(content, str) and len(content.strip()) > 10:
                            messages.append(content[:2000])
                except json.JSONDecodeError:
                    continue
                if len(messages) >= max_messages:
                    break
    except OSError:
        pass
    return messages


def analyze_sessions(num_sessions: int = 5) -> dict:
    """Analyze recent session JSONL files for delegation potential."""
    # Find recent session files
    jsonl_files = sorted(
        SESSION_DIR.glob("*.jsonl"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )[:num_sessions]

    if not jsonl_files:
        return {"error": "No session files found"}

    all_classifications = Counter()
    total_prompts = 0
    delegatable = 0

    for jsonl_path in jsonl_files:
        messages = extract_user_messages(jsonl_path)
        for msg in messages:
            if contains_secrets(msg[:2000]):
                all_classifications["claude_secrets"] += 1
                total_prompts += 1
                continue

            model, confidence = classify_task(msg[:2000])
            all_classifications[model] += 1
            total_prompts += 1
            if model != "claude":
                delegatable += 1

    return {
        "sessions_analyzed": len(jsonl_files),
        "total_prompts": total_prompts,
        "delegatable": delegatable,
        "delegatable_pct": (delegatable / total_prompts * 100) if total_prompts > 0 else 0,
        "classifications": dict(all_classifications),
    }


def analyze_live_log() -> dict:
    """Analyze the live delegation audit log."""
    if not AUDIT_LOG.exists():
        return {"error": "No audit log yet — hook hasn't fired"}

    lines = AUDIT_LOG.read_text().strip().split("\n")
    if not lines or not lines[0]:
        return {"error": "Audit log is empty"}

    models = Counter()
    advised_count = 0
    for line in lines:
        for token in line.split():
            if token.startswith("model="):
                models[token.split("=")[1]] += 1
            # v2 audit log uses tone=X (not injected=True)
            if token.startswith("tone=") and token != "tone=none":
                advised_count += 1

    total = len(lines)
    delegatable = total - models.get("claude", 0)
    return {
        "total_prompts": total,
        "delegatable": delegatable,
        "delegatable_pct": (delegatable / total * 100) if total > 0 else 0,
        "advised": advised_count,
        "classifications": dict(models),
    }


def validate_assumptions(actual_data: dict) -> None:
    """Compare assumptions against actual data."""
    total = actual_data.get("total_prompts", 0)
    if total == 0:
        print("No data to validate against.")
        return

    classifications = actual_data.get("classifications", {})

    # Map classifications to assumption categories
    research_count = classifications.get("gemini", 0)
    simple_count = classifications.get("ollama", 0)
    code_count = classifications.get("qwen", 0)
    claude_count = classifications.get("claude", 0) + classifications.get("claude_secrets", 0)
    groq_count = classifications.get("groq", 0)

    actuals = {
        "research_pct": research_count / total * 100,
        "simple_qa_pct": simple_count / total * 100,
        "code_gen_pct": (code_count + groq_count) / total * 100,
        "claude_only_pct": claude_count / total * 100,
        "potential_savings_pct": actual_data.get("delegatable_pct", 0),
    }

    print(f"\n{'Assumption':<30s} {'Hypothesis':>10s} {'Actual':>10s} {'Delta':>10s} {'Status'}")
    print("-" * 80)
    for key, assumption in ASSUMPTIONS.items():
        hyp = assumption["hypothesis"]
        actual = actuals.get(key, 0)
        delta = actual - hyp
        status = "VALIDATED" if abs(delta) < 10 else ("HIGHER" if delta > 0 else "LOWER")
        emoji = "~" if abs(delta) < 10 else ("^" if delta > 0 else "v")
        print(f"{assumption['description'][:30]:<30s} {hyp:>9.0f}% {actual:>9.1f}% {delta:>+9.1f}% {emoji} {status}")

    print(f"\nTotal prompts analyzed: {total}")
    print(f"Delegatable: {actual_data.get('delegatable', 0)} ({actual_data.get('delegatable_pct', 0):.1f}%)")


def main():
    args = sys.argv[1:]

    if "--help" in args:
        print(__doc__)
        return

    if "--live" in args:
        print("=== Live Audit Log Analysis ===")
        data = analyze_live_log()
        if "error" in data:
            print(data["error"])
            return
        print(json.dumps(data, indent=2))
        validate_assumptions(data)
        return

    if "--assumptions" in args:
        print("=== Delegation Assumptions (Hypotheses) ===\n")
        for key, a in ASSUMPTIONS.items():
            print(f"  {a['description']}")
            print(f"    Hypothesis: {a['hypothesis']}%\n")
        print("\nRun with --live or without flags to validate against real data.")
        return

    num = 5
    for i, arg in enumerate(args):
        if arg == "--sessions" and i + 1 < len(args):
            num = int(args[i + 1])

    print(f"=== Retroactive Session Analysis (last {num} sessions) ===")
    data = analyze_sessions(num)
    if "error" in data:
        print(data["error"])
        return
    print(json.dumps(data, indent=2))
    validate_assumptions(data)


if __name__ == "__main__":
    main()
