#!/usr/bin/env python3
"""Delegation Validator — validates output from Gemini/Qwen before Claude uses it.

Checks:
1. Size (empty or suspiciously large)
2. Injection patterns (prompt injection, command injection)
3. Task-specific validation (code syntax, file existence, number sanity)

Usage:
    from delegation_validator import validate_delegated_output
    result = validate_delegated_output(output, task_type="code")
    if result["blocked"]:
        # Discard output, fall back to native Claude
    elif result["warnings"]:
        # Proceed with caution, log warnings

CLI usage (for testing):
    python3 delegation_validator.py --type code --input "def foo(): pass"
    python3 delegation_validator.py --type file_analysis --input "Found 3 files in ~/Development/"
    echo "some output" | python3 delegation_validator.py --type count
"""

import ast
import json
import re
import sys
from pathlib import Path

# --- Injection patterns (regex-based, not LLM-based) ---

INJECTION_PATTERNS = [
    # Prompt injection attempts
    re.compile(r'ignore\s+(all\s+)?previous\s+instructions', re.IGNORECASE),
    re.compile(r'disregard\s+(all\s+)?(?:prior|above|previous)', re.IGNORECASE),
    re.compile(r'forget\s+(everything|all|your)\s+(?:instructions|rules|guidelines)', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+(?:a|an|the)\s+', re.IGNORECASE),
    re.compile(r'new\s+system\s+(?:instructions|rules|role|persona)', re.IGNORECASE),
    re.compile(r'(?:system|admin)\s*(?:prompt|override|command)', re.IGNORECASE),
    re.compile(r'<\s*(?:system|admin|root)\s*>', re.IGNORECASE),
    re.compile(r'\]\]\s*>\s*<', re.IGNORECASE),  # XML injection

    # Command injection via output
    re.compile(r'(?:^|\s)(?:rm\s+-rf|sudo\s+|chmod\s+777|curl\s+.*\|\s*(?:sh|bash))', re.IGNORECASE),
    re.compile(r'(?:^|\s)(?:eval|exec)\s*\(', re.IGNORECASE),
    re.compile(r'__import__\s*\(', re.IGNORECASE),
    re.compile(r'os\.(?:system|popen|exec)', re.IGNORECASE),
    re.compile(r'subprocess\.(?:call|run|Popen)', re.IGNORECASE),

    # Data exfiltration patterns
    re.compile(r'(?:curl|wget|fetch)\s+.*(?:attacker|evil|malicious)', re.IGNORECASE),
    re.compile(r'base64\s+(?:-d|--decode).*\|\s*(?:sh|bash)', re.IGNORECASE),
]

# Known hallucination patterns for code generators
HALLUCINATED_IMPORTS = [
    # Common Qwen/Gemini hallucinations — packages that don't exist
    'from anthropic_ai.',      # Anthropic doesn't publish this namespace
    'import qwen_utils',       # Not a real package
    'from gemini_api.',        # Not a real package
    'import claude_sdk',       # Not a real package
    'from openai_helpers.',    # Not a real package
]

# Sensitive path patterns that should never appear in delegated output
SENSITIVE_PATHS = [
    re.compile(r'~/.env\b'),
    re.compile(r'~/\.claude/.*\.json\b'),
    re.compile(r'credentials\.json\b'),
    re.compile(r'\.ssh/'),
    re.compile(r'\.gnupg/'),
    re.compile(r'\.aws/'),
    re.compile(r'token[s]?\.json\b', re.IGNORECASE),
    re.compile(r'secret[s]?\.(?:json|yaml|yml|env)\b', re.IGNORECASE),
]


def validate_delegated_output(output: str, task_type: str = "general") -> dict:
    """Validate output from Gemini/Qwen before Claude uses it.

    Args:
        output: The raw text output from the delegated model.
        task_type: One of "code", "file_analysis", "count", "general".

    Returns:
        dict with keys:
            valid: bool — overall assessment
            warnings: list[str] — non-blocking issues
            blocked: bool — if True, discard this output entirely
            details: dict — task-specific validation results
    """
    result = {
        "valid": True,
        "warnings": [],
        "blocked": False,
        "details": {},
    }

    if not isinstance(output, str):
        result["blocked"] = True
        result["valid"] = False
        result["warnings"].append("Output is not a string")
        return result

    # --- 1. Size checks ---
    if len(output.strip()) < 10:
        result["warnings"].append(f"Output suspiciously short ({len(output)} chars)")
        result["valid"] = False

    if len(output) > 100_000:
        result["warnings"].append(f"Output very large ({len(output)} chars) — may need truncation")

    # --- 2. Injection scan ---
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(output)
        if match:
            result["warnings"].append(f"Injection pattern detected: '{match.group()}'")
            result["blocked"] = True
            result["valid"] = False

    # --- 3. Sensitive path scan ---
    for pattern in SENSITIVE_PATHS:
        match = pattern.search(output)
        if match:
            result["warnings"].append(f"Sensitive path reference: '{match.group()}'")

    # --- 4. Task-specific validation ---
    if task_type == "code":
        result["details"] = _validate_code(output)
    elif task_type == "file_analysis":
        result["details"] = _validate_file_analysis(output)
    elif task_type == "count":
        result["details"] = _validate_count(output)

    # Propagate task-specific blocks
    if result["details"].get("blocked"):
        result["blocked"] = True
        result["valid"] = False

    return result


def _validate_code(output: str) -> dict:
    """Validate code output for syntax and hallucinated imports."""
    details = {"syntax_valid": False, "hallucinated_imports": [], "blocked": False}

    # Extract code blocks if wrapped in markdown fences
    code = output
    fence_match = re.search(r'```(?:python)?\n(.*?)```', output, re.DOTALL)
    if fence_match:
        code = fence_match.group(1)

    # Check Python syntax
    try:
        ast.parse(code)
        details["syntax_valid"] = True
    except SyntaxError as e:
        details["syntax_valid"] = False
        details["syntax_error"] = str(e)

    # Check for hallucinated imports
    for hallucination in HALLUCINATED_IMPORTS:
        if hallucination in code:
            details["hallucinated_imports"].append(hallucination.strip())
            details["blocked"] = True

    return details


def _validate_file_analysis(output: str) -> dict:
    """Validate file analysis output — check referenced paths exist."""
    details = {"paths_checked": 0, "paths_missing": [], "blocked": False}

    # Find file paths in output (~/... or /Users/... patterns)
    path_pattern = re.compile(r'(?:~/|/Users/\w+/)\S+')
    paths = path_pattern.findall(output)

    for p in paths[:20]:  # Cap at 20 to avoid slowness
        expanded = Path(p).expanduser()
        details["paths_checked"] += 1
        if not expanded.exists():
            details["paths_missing"].append(str(expanded))

    return details


def _validate_count(output: str) -> dict:
    """Validate count/number output — check numbers are reasonable."""
    details = {"numbers_found": [], "suspicious": False, "blocked": False}

    # Extract numbers
    numbers = re.findall(r'\b(\d+)\b', output)
    details["numbers_found"] = [int(n) for n in numbers[:20]]

    # Flag unreasonably large numbers (likely hallucination)
    for n in details["numbers_found"]:
        if n > 1_000_000:
            details["suspicious"] = True
            details["blocked"] = False  # Warn but don't block

    return details


def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate delegated LLM output")
    parser.add_argument("--type", choices=["code", "file_analysis", "count", "general"],
                        default="general", help="Task type for validation")
    parser.add_argument("--input", type=str, help="Text to validate (or pipe via stdin)")
    args = parser.parse_args()

    if args.input:
        text = args.input
    else:
        text = sys.stdin.read()

    result = validate_delegated_output(text, task_type=args.type)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] and not result["blocked"] else 1)


if __name__ == "__main__":
    main()
