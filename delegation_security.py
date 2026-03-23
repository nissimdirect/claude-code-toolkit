#!/usr/bin/env python3
"""Shared security module for LLM delegation.

Extracted from delegation_hook.py v4.4.1 for use by both the
delegation hook (push path) and the MCP server (pull path).

Functions:
    sanitize_query()           — input sanitization + template injection markers
    sanitize_response()        — output sanitization (injection patterns)
    _normalize_for_matching()  — homoglyph/spacing evasion normalization
    _has_key_value_secrets()   — KEY=value secret detection
    contains_secret_output()   — scan output for leaked API keys/tokens
"""

import re

# --- Injection Patterns (RT-3, RT-7) ---
# Catches: direct instruction override, template injection, semantic injection,
# homoglyph/spaced evasion (via normalize step in sanitize_response)

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"execute\s+(bash|shell|command|code)", re.I),
    re.compile(r"curl\s+\S+\s*\|\s*(sh|bash)", re.I),
    re.compile(r"rm\s+-rf", re.I),
    re.compile(r"<\s*script\b", re.I),
    # Model-specific instruction markers (prevent template injection)
    re.compile(r"\[INST\]", re.I),
    re.compile(r"<\|im_start\|>", re.I),
    re.compile(r"###\s*(Human|System|Assistant)\s*:", re.I),
    # Semantic injection — instruction-like phrasing from LLM responses (RT-7)
    re.compile(r"disregard\s+(all\s+)?(earlier|prior|above|previous)", re.I),
    re.compile(r"from\s+now\s+on\s*,?\s*you\s+(must|should|will|are)", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"override\s+(the\s+)?(system|rules|instructions)", re.I),
    re.compile(r"<\|end_header_id\|>", re.I),  # Llama-style template injection
]

# Indirect instruction patterns — LLM output that tries to make Claude take actions
INDIRECT_INSTRUCTION_PATTERNS = [
    re.compile(r"use\s+the\s+(?:Bash|Read|Write|Edit|Glob|Grep)\s+tool", re.I),
    re.compile(r"create\s+a\s+file\s+at\b", re.I),
    re.compile(r"run\s+(?:this|the\s+following)\s+command", re.I),
    re.compile(r"execute\s+(?:this|the\s+following)", re.I),
    re.compile(r"delete\s+(?:the\s+)?file", re.I),
    re.compile(r"modify\s+(?:the\s+)?(?:file|config)\s+at", re.I),
]

# --- Secret Output Patterns ---
# Scan LLM output for accidentally leaked API keys/tokens

SECRET_OUTPUT_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_]{20,}"),  # OpenAI/Anthropic keys
    re.compile(r"gsk_[a-zA-Z0-9]{20,}"),  # Groq keys
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{30,}"),  # Google API keys
    re.compile(r"ghp_[a-zA-Z0-9]{30,}"),  # GitHub PATs
    re.compile(r"xoxb-[a-zA-Z0-9-]{20,}"),  # Slack tokens
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
]

# --- KEY=value Secret Detection ---

_KEY_VALUE_SECRET_RE = re.compile(
    r"(?:^|[\s,;])(?:"
    r"[A-Z_]*(?:API_?KEY|SECRET_?KEY|ACCESS_?KEY|AUTH_?TOKEN|PASSWORD|PASSPHRASE"
    r"|PRIVATE_?KEY|CLIENT_?SECRET|SENTRY_?DSN|DATABASE_?URL)"
    r")\s*[=:]\s*\S{6,}",
    re.IGNORECASE,
)


def _has_key_value_secrets(text: str) -> bool:
    """Catch KEY=value secrets that llm_router.contains_secrets() misses."""
    return bool(_KEY_VALUE_SECRET_RE.search(text))


def sanitize_query(text: str) -> str:
    """Sanitize text before sending to external model.

    Strips control chars, shell metacharacters, and template injection markers.
    """
    # Strip control characters (except newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Strip shell metacharacters that could be interpreted
    text = text.replace("`", "'").replace("$(", "(")
    # Strip template injection markers
    text = re.sub(r"\[INST\]", "", text)
    text = re.sub(r"<\|im_start\|>", "", text)
    text = re.sub(r"###\s*(Human|System|Assistant)\s*:", "", text)
    return text


def _normalize_for_matching(text: str) -> str:
    """Normalize text to defeat homoglyph and spacing evasion (RT-7).

    Converts common look-alike chars (0->o, 1->i, 3->e) and collapses
    extra whitespace so 'ign0re  prev1ous' matches 'ignore previous'.
    """
    table = str.maketrans("013@$", "oieas")
    normalized = text.translate(table)
    normalized = re.sub(r"(?<=\w)\s{2,}(?=\w)", " ", normalized)
    return normalized


def sanitize_response(text: str) -> str | None:
    """Sanitize external LLM response before injecting into Claude's context.

    Returns None if response contains high-confidence injection patterns (RT-3).
    Uses normalized text to catch homoglyph/spacing evasion (RT-7).
    Also checks for indirect instruction patterns.
    """
    norm_text = _normalize_for_matching(text)
    injection_count = 0

    # Check core injection patterns
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text) or pattern.search(norm_text):
            injection_count += 1

    # Check indirect instruction patterns
    for pattern in INDIRECT_INSTRUCTION_PATTERNS:
        if pattern.search(text) or pattern.search(norm_text):
            injection_count += 1

    # 2+ injection patterns = likely malicious, block entirely
    if injection_count >= 2:
        return None

    # 1 pattern = strip the line containing it
    if injection_count == 1:
        all_patterns = INJECTION_PATTERNS + INDIRECT_INSTRUCTION_PATTERNS
        lines = text.split("\n")
        clean_lines = []
        for line in lines:
            norm_line = _normalize_for_matching(line)
            if not any(p.search(line) or p.search(norm_line) for p in all_patterns):
                clean_lines.append(line)
        text = "\n".join(clean_lines)

    # Strip control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text


def contains_secret_output(text: str) -> bool:
    """Check if LLM output contains leaked API keys or tokens."""
    for pattern in SECRET_OUTPUT_PATTERNS:
        if pattern.search(text):
            return True
    return _has_key_value_secrets(text)


def validate_and_sanitize(output: str) -> str | None:
    """Combined validator + sanitizer. Returns None if unsafe.

    Checks: empty, secrets in output, injection patterns, indirect instructions.
    Does NOT run delegation_validator (that's task-specific, done by caller).
    """
    if not output or len(output) < 10:
        return None
    if contains_secret_output(output):
        return None
    return sanitize_response(output)
