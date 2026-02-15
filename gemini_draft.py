#!/usr/bin/env python3
"""gemini_draft.py — Fast Gemini API drafting for code, tests, and docs.

Calls Gemini 2.0 Flash API directly (no CLI overhead).
Returns raw text output for Claude to review before writing to disk.

Usage:
    # As CLI
    python3 gemini_draft.py "Write pytest tests for function X"
    python3 gemini_draft.py --file prompt.txt        # Read prompt from file
    python3 gemini_draft.py --context file.py "Add error handling"  # Include file context

    # As library
    from gemini_draft import draft
    code = draft("Write a levels effect in Python using cv2.LUT")
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.0-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
MAX_CONTEXT_CHARS = 30000  # Don't send huge files


def draft(prompt: str, context: str = "", temperature: float = 0.3) -> str:
    """Call Gemini Flash API and return the text response.

    Args:
        prompt: The task/instruction for Gemini
        context: Optional file content or reference material
        temperature: 0.0-1.0 (lower = more deterministic, default 0.3 for code)

    Returns:
        Raw text response from Gemini

    Raises:
        RuntimeError: If API call fails
    """
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in environment")

    # Build the prompt with optional context
    full_prompt = prompt
    if context:
        context_trimmed = context[:MAX_CONTEXT_CHARS]
        if len(context) > MAX_CONTEXT_CHARS:
            context_trimmed += f"\n\n[... truncated, {len(context) - MAX_CONTEXT_CHARS} chars omitted]"
        full_prompt = f"Reference context:\n```\n{context_trimmed}\n```\n\nTask: {prompt}"

    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
        }
    }

    url = f"{API_URL}?key={API_KEY}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")

    # Extract text from response
    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected response format: {json.dumps(result)[:500]}")

    # Strip markdown fences if present (common in code responses)
    text = _strip_fences(text)

    return text


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from response."""
    lines = text.strip().split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Draft code/docs via Gemini Flash API")
    parser.add_argument("prompt", nargs="?", help="The drafting prompt")
    parser.add_argument("--file", "-f", help="Read prompt from file")
    parser.add_argument("--context", "-c", help="Include file as context")
    parser.add_argument("--temperature", "-t", type=float, default=0.3)
    args = parser.parse_args()

    # Get prompt
    if args.file:
        prompt = Path(args.file).read_text()
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = sys.stdin.read()

    if not prompt.strip():
        print("ERROR: Empty prompt", file=sys.stderr)
        sys.exit(1)

    # Get optional context
    context = ""
    if args.context:
        ctx_path = Path(args.context)
        if ctx_path.exists():
            context = ctx_path.read_text()
        else:
            print(f"WARNING: Context file not found: {args.context}", file=sys.stderr)

    try:
        result = draft(prompt, context=context, temperature=args.temperature)
        print(result)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
