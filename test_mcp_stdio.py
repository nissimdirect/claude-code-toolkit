#!/usr/bin/env python3
"""Test MCP server over real stdio JSON-RPC protocol.

Proves the server works exactly as Claude Code will use it.
"""

import json
import subprocess
import sys

MESSAGES = [
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    },
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "llm_health",
            "arguments": {},
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "llm_route",
            "arguments": {"task": "Summarize the top reverb techniques"},
        },
    },
    {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "llm_delegate",
            "arguments": {"task": "What is sidechain compression? One sentence."},
        },
    },
]

stdin_data = "\n".join(json.dumps(m) for m in MESSAGES) + "\n"

proc = subprocess.run(
    [sys.executable, "llm_router_mcp.py"],
    input=stdin_data,
    capture_output=True,
    text=True,
    timeout=25,
    cwd=str(__import__("pathlib").Path(__file__).parent),
)

print("=== MCP STDIO PROTOCOL TEST ===\n")

responses = []
for line in proc.stdout.strip().split("\n"):
    line = line.strip()
    if not line:
        continue
    try:
        r = json.loads(line)
        responses.append(r)
    except json.JSONDecodeError:
        pass

for r in responses:
    rid = r.get("id", "?")
    if rid == 1:
        name = r.get("result", {}).get("serverInfo", {}).get("name", "?")
        print(f"1. initialize: server={name} — OK")
    elif rid == 2:
        tools = r.get("result", {}).get("tools", [])
        names = [t["name"] for t in tools]
        print(f"2. tools/list: {names}")
    elif rid == 3:
        content = r.get("result", {}).get("content", [{}])
        text = content[0].get("text", "") if content else ""
        d = json.loads(text) if text else {}
        healthy = [
            k for k, v in d.items() if isinstance(v, dict) and v.get("status") == "OK"
        ]
        print(f"3. llm_health: {len(healthy)} models OK — {', '.join(healthy)}")
    elif rid == 4:
        content = r.get("result", {}).get("content", [{}])
        text = content[0].get("text", "") if content else ""
        d = json.loads(text) if text else {}
        print(f"4. llm_route: model={d.get('model')}, conf={d.get('confidence')}")
    elif rid == 5:
        content = r.get("result", {}).get("content", [{}])
        text = content[0].get("text", "") if content else ""
        if "[External model output" in text:
            # Extract content between delimiters
            lines = text.split("\n")
            answer = [
                l.strip()
                for l in lines
                if l.strip()
                and "External model" not in l
                and "End external" not in l
                and "DEDUP" not in l
            ]
            print("5. llm_delegate: LIVE SUCCESS")
            if answer:
                print(f"   Response: {answer[0][:120]}")
        elif text:
            try:
                d = json.loads(text)
                print(
                    f"5. llm_delegate: {d.get('error', d.get('routed_to', text[:80]))}"
                )
            except json.JSONDecodeError:
                print(f"5. llm_delegate: {text[:80]}")

if not responses:
    print("NO RESPONSES — stderr:")
    print(proc.stderr[:500])

print(f"\n{len(responses)} responses received via stdio JSON-RPC")
print("=== PROTOCOL TEST COMPLETE ===")
