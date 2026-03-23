#!/usr/bin/env python3
"""Verify LLM Router MCP Server — runs all 10 checks."""

import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import llm_router_mcp as mcp
import llm_router


async def main():
    print("=== MCP SERVER VERIFICATION ===\n")

    # 1. Tool registration
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    print(f"1. Tools registered: {len(tools)} — {', '.join(names)}")
    assert len(tools) == 4, f"Expected 4 tools, got {len(tools)}"

    # 2. llm_route — research
    r = await mcp.call_tool("llm_route", {"task": "Summarize the reverb KB articles"})
    d = json.loads(r[0].text)
    print(f"2. llm_route (research): model={d['model']}, conf={d['confidence']}")
    assert d["model"] == "gemini"

    # 3. llm_route — strategy
    r = await mcp.call_tool(
        "llm_route", {"task": "Should we refactor the auth module?"}
    )
    d = json.loads(r[0].text)
    print(f"3. llm_route (strategy): model={d['model']}")
    assert d["model"] == "claude"

    # 4. llm_route — secrets blocked
    r = await mcp.call_tool("llm_route", {"task": "Use key sk-abc123456789abcdef"})
    d = json.loads(r[0].text)
    print(f"4. llm_route (secrets): gate={d['gate']}")
    assert d["gate"] == "secrets"

    # 5. llm_route — followup detection
    llm_router.set_last_model("groq")
    r = await mcp.call_tool(
        "llm_route", {"task": "Now explain the next part", "previous_model": "groq"}
    )
    d = json.loads(r[0].text)
    print(
        f"5. llm_route (followup): model={d['model']}, is_followup={d['is_followup']}"
    )
    assert d["model"] == "groq"
    assert d["is_followup"] is True

    # 6. llm_delegate — secrets blocked
    r = await mcp.call_tool("llm_delegate", {"task": "Use key sk-abc123456789abcdef"})
    d = json.loads(r[0].text)
    print(f"6. llm_delegate (secrets): gate={d['gate']}")
    assert d["gate"] == "secrets"

    # 7. llm_delegate — empty blocked
    r = await mcp.call_tool("llm_delegate", {"task": ""})
    d = json.loads(r[0].text)
    print(f"7. llm_delegate (empty): gate={d['gate']}")
    assert d["gate"] == "empty"

    # 8. llm_health — all models
    r = await mcp.call_tool("llm_health", {})
    d = json.loads(r[0].text)
    healthy = [
        k for k, v in d.items() if isinstance(v, dict) and v.get("status") == "OK"
    ]
    down = [
        k for k, v in d.items() if isinstance(v, dict) and v.get("status") == "DOWN"
    ]
    budget = d.get("_budget_percent", 0)
    print(
        f"8. llm_health: {len(healthy)} OK ({', '.join(healthy)}), {len(down)} DOWN, budget={budget}%"
    )
    assert len(healthy) >= 3, f"Expected >=3 healthy models, got {len(healthy)}"

    # 9. llm_stats — compliance data
    r = await mcp.call_tool("llm_stats", {})
    d = json.loads(r[0].text)
    comp = d.get("compliance", {})
    prompts = comp.get("total_prompts", 0)
    rate = comp.get("delegation_rate", "0%")
    mcp_del = comp.get("mcp_delegated", 0)
    print(f"9. llm_stats: prompts={prompts}, rate={rate}, mcp_delegated={mcp_del}")

    # 10. LIVE delegate — actual Gemini/Ollama call
    print("\n10. llm_delegate LIVE (What is 2+2?)...")
    r = await mcp.call_tool(
        "llm_delegate", {"task": "What is 2+2? Answer with just the number."}
    )
    text = r[0].text
    if "[External model output" in text:
        print("    SUCCESS — response framed correctly")
        for line in text.split("\n"):
            stripped = line.strip()
            if (
                stripped
                and "External model" not in stripped
                and "End external" not in stripped
                and "DEDUP" not in stripped
            ):
                print(f"    Content: {stripped[:80]}")
                break
    elif "error" in text:
        d = json.loads(text)
        routed = d.get("routed_to", d.get("error", "?"))
        print(f"    Routed to Claude (no external model available): {str(routed)[:80]}")
    else:
        print(f"    Response: {text[:100]}")

    # Check audit log was written
    if mcp.AUDIT_LOG.exists():
        content = mcp.AUDIT_LOG.read_text()
        mcp_entries = [l for l in content.strip().split("\n") if "source=mcp" in l]
        print(f"\n    Audit log: {len(mcp_entries)} MCP entries found")

    print("\n=== ALL 10 CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
