#!/usr/bin/env python3
"""Phase 0C: Validate MCP Pull Behavior — 20 prompt test.

This script generates the 20 test prompts from the plan and records
whether Claude called the llm_delegate MCP tool for each one.

RUN THIS IN A FRESH CLAUDE CODE SESSION (after restart, so MCP tools are loaded).

Usage:
    # Step 1: Run this to generate the test prompts
    python3 ~/Development/tools/validate_mcp_pull.py generate

    # Step 2: In Claude Code, paste each prompt one at a time.
    #         After each, check the audit log:
    python3 ~/Development/tools/validate_mcp_pull.py check

    # Step 3: After all 20 prompts, run the analysis:
    python3 ~/Development/tools/validate_mcp_pull.py analyze
"""

import json
import sys
import time
from pathlib import Path

AUDIT_LOG = Path.home() / ".claude" / ".locks" / "delegation-hook-audit.log"
RESULTS_FILE = Path.home() / ".claude" / ".locks" / "mcp-pull-validation.json"

# 20 test prompts across 5 categories (4 each)
TEST_PROMPTS = {
    "research": [
        "summarize the key differences between plate reverb and spring reverb",
        "compare FIR and IIR filter implementations for audio plugins",
        "what do articles say about the future of spatial audio",
        "cross-reference the top 5 DAW market share reports from 2025",
    ],
    "code": [
        "write pytest tests for a function that validates MIDI note ranges",
        "scaffold a basic Express.js API with health check endpoint",
        "generate Python fixtures for testing audio buffer processing",
        "write a function that converts frequency to MIDI note number",
    ],
    "simple": [
        "what is the Nyquist frequency",
        "define dithering in audio processing",
        "syntax for Python dictionary comprehension",
        "what HTTP status code means rate limited",
    ],
    "ambiguous": [
        "hmm what about that thing we discussed",
        "interesting approach but could be better",
        "tell me more about the options",
        "what would you suggest here",
    ],
    "skill": [
        "/ask-lenny what metrics matter most for a new audio plugin launch",
        "/cto should we use WebAssembly for our audio processing pipeline",
        "/don-norman evaluate the UX of our plugin parameter layout",
        "/music-biz what distribution strategy works best for niche plugins",
    ],
}


def generate():
    """Print all 20 prompts for manual testing."""
    print("=== PHASE 0C: MCP PULL VALIDATION ===")
    print("Paste each prompt into Claude Code one at a time.")
    print("After each, run: python3 validate_mcp_pull.py check")
    print()

    n = 0
    for category, prompts in TEST_PROMPTS.items():
        print(f"--- {category.upper()} ({len(prompts)} prompts) ---")
        for p in prompts:
            n += 1
            print(f"  {n:2d}. {p}")
        print()

    print(f"Total: {n} prompts")
    print()
    print("Pass threshold: >=12/20 (60%) = pure pull viable later")
    print("Fail threshold: <8/20 (40%) = hybrid confirmed necessary")


def check():
    """Check the last audit log entry for MCP pull activity."""
    if not AUDIT_LOG.exists():
        print("No audit log found")
        return

    lines = AUDIT_LOG.read_text().strip().split("\n")
    # Show last 3 entries
    print("Last 3 audit entries:")
    for line in lines[-3:]:
        if "source=mcp" in line:
            print(f"  MCP PULL: {line[:120]}")
        elif "source=natural" in line:
            print(f"  HOOK PUSH: {line[:120]}")
        else:
            print(f"  {line[:120]}")

    # Count MCP entries in last 5 minutes
    recent_mcp = sum(1 for l in lines[-10:] if "source=mcp" in l)
    recent_push = sum(1 for l in lines[-10:] if "source=natural" in l)
    print(f"\nRecent: {recent_mcp} MCP pulls, {recent_push} hook pushes")


def analyze():
    """Analyze all MCP activity and determine pass/fail."""
    if not AUDIT_LOG.exists():
        print("No audit log found")
        return

    lines = AUDIT_LOG.read_text().strip().split("\n")
    mcp_entries = [l for l in lines if "source=mcp" in l]
    push_entries = [l for l in lines if "source=natural" in l]

    total_mcp = len(mcp_entries)
    mcp_delegated = sum(1 for l in mcp_entries if "DELEGATED" in l)
    mcp_blocked = sum(1 for l in mcp_entries if "BLOCKED" in l)

    print("=== PHASE 0C RESULTS ===")
    print(f"MCP pull attempts:  {total_mcp}")
    print(f"MCP delegated:      {mcp_delegated}")
    print(f"MCP blocked:        {mcp_blocked}")
    print(f"Hook push entries:  {len(push_entries)}")
    print()

    if total_mcp >= 12:
        print("RESULT: PASS (>=60%) — pure pull viable for future migration")
    elif total_mcp >= 8:
        print("RESULT: PARTIAL (40-60%) — hybrid confirmed, pull is bonus")
    else:
        print("RESULT: FAIL (<40%) — hybrid is necessary, pure pull deferred")

    # Save results
    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mcp_total": total_mcp,
        "mcp_delegated": mcp_delegated,
        "mcp_blocked": mcp_blocked,
        "push_total": len(push_entries),
        "verdict": "pass"
        if total_mcp >= 12
        else "partial"
        if total_mcp >= 8
        else "fail",
    }
    RESULTS_FILE.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if cmd == "generate":
        generate()
    elif cmd == "check":
        check()
    elif cmd == "analyze":
        analyze()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: validate_mcp_pull.py [generate|check|analyze]")
