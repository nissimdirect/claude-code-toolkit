#!/usr/bin/env python3
"""LLM Router — routes tasks to the cheapest capable model.

Implements the LLM Delegation Schema (LLM-DELEGATION-SCHEMA.md).
Used by OpenClaw and Claude Code to decide which LLM handles a task.

Usage:
    # As a library
    from llm_router import route
    result = route("Summarize reverb articles")
    # result.model = "gemini", result.wrapper = "gemini-safe.sh", ...

    # As CLI
    python3 llm_router.py "Summarize reverb articles"
    python3 llm_router.py --verbose "What is the syntax for Python list comprehension?"
    python3 llm_router.py --dry-run "Generate a JUCE plugin skeleton"
"""

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# Import delegation validator for output verification
try:
    from delegation_validator import validate_delegated_output
    HAS_VALIDATOR = True
except ImportError:
    # Fallback: try absolute path
    _validator_path = Path(__file__).parent / "delegation_validator.py"
    if _validator_path.exists():
        import importlib.util
        _spec = importlib.util.spec_from_file_location("delegation_validator", _validator_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        validate_delegated_output = _mod.validate_delegated_output
        HAS_VALIDATOR = True
    else:
        HAS_VALIDATOR = False

# --- Constants ---

RATE_LIMITS_FILE = Path.home() / ".openclaw" / "llm-rate-limits.json"
BUDGET_FILE = Path.home() / ".budget-state.json"
QUEUE_FILE = Path.home() / "Documents" / "Obsidian" / "process" / "CLAUDE-QUEUE.md"
TOOLS_DIR = Path.home() / "Development" / "tools"
LOG_FILE = Path.home() / ".openclaw" / "logs" / "llm-router-audit.log"

# --- Model Definitions ---

MODELS = {
    "claude": {
        "tier": 1,
        "wrapper": None,  # native, not delegated
        "rpm_limit": None,
        "headroom": 0,
        "context": 200_000,
        "strengths": ["strategy", "security", "tools", "taste", "multi-file"],
    },
    "gemini": {
        "tier": 2,
        "wrapper": str(TOOLS_DIR / "gemini-safe.sh"),
        "rpm_limit": 15,
        "headroom": 3,
        "context": 1_000_000,
        "strengths": ["large-context", "research", "summarization", "vision"],
    },
    "groq": {
        "tier": 2,
        "wrapper": str(TOOLS_DIR / "groq-safe.sh"),
        "rpm_limit": 30,
        "headroom": 5,
        "context": 128_000,
        "strengths": ["reasoning", "code-review", "technical-writing", "fast"],
    },
    "qwen": {
        "tier": 3,
        "wrapper": str(TOOLS_DIR / "qwen-safe.sh"),
        "rpm_limit": None,
        "headroom": 0,
        "context": 128_000,
        "strengths": ["code-gen", "scaffolding", "translation", "regex", "batch"],
    },
    "ollama": {
        "tier": 3,
        "wrapper": str(TOOLS_DIR / "ollama-safe.sh"),
        "rpm_limit": None,
        "headroom": 0,
        "context": 8_000,
        "strengths": ["simple-qa", "classification", "offline", "private", "fast"],
    },
    "deepseek": {
        "tier": 4,
        "wrapper": str(TOOLS_DIR / "deepseek-safe.sh"),
        "rpm_limit": None,
        "headroom": 0,
        "context": 64_000,
        "strengths": ["math", "reasoning", "research"],
    },
}

# --- Gemini API (direct REST, bypasses CLI agent mode) ---

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"


def _call_gemini_api(prompt: str, model: str = GEMINI_DEFAULT_MODEL, timeout: int = 120) -> str:
    """Call Gemini via REST API. Returns response text or raises."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    url = GEMINI_API_URL.format(model=model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 4096,
        },
    }
    resp = requests.post(
        url,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=timeout,
    )
    if resp.status_code != 200:
        # Extract API error message but strip key from any URL references
        try:
            err_detail = resp.json().get("error", {}).get("message", resp.reason)
        except Exception:
            err_detail = resp.reason
        raise RuntimeError(f"Gemini API {resp.status_code}: {err_detail}")
    data = resp.json()

    # Extract text from response
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini API returned no candidates: {data}")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


# --- Safety Patterns (Gate 0a: secrets/credentials) ---

SECRET_PATTERNS = [
    re.compile(r'sk-[a-zA-Z0-9_]{8,}'),              # OpenAI/Anthropic API keys
    re.compile(r'gsk_[a-zA-Z0-9]{8,}'),             # Groq API keys
    re.compile(r'ntn_[a-zA-Z0-9]{8,}'),             # Notion tokens
    re.compile(r'ghp_[a-zA-Z0-9]{8,}'),             # GitHub PATs
    re.compile(r'xoxb-[a-zA-Z0-9-]+'),              # Slack tokens
    re.compile(r'key[_-]?[a-zA-Z0-9]{16,}', re.I),  # Generic API key patterns
    re.compile(r'-----BEGIN .* KEY-----', re.S),     # PEM keys
    re.compile(r'password\s*[=:]\s*\S+', re.I),     # password assignments
    re.compile(r'token\s*[=:]\s*["\']?\S{10,}', re.I),  # token assignments
    re.compile(r'export\s+\w*(?:KEY|TOKEN|SECRET|PASSWORD)\w*\s*=', re.I),  # env exports
    re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),   # phone numbers
    re.compile(r'[a-zA-Z0-9._%+-]{1,64}@[a-zA-Z0-9.-]{1,253}\.[a-zA-Z]{2,10}'),  # emails (bounded, HT-4)
    re.compile(r'\.env\b'),                          # .env references
    re.compile(r'credentials?\.(json|yaml|yml|toml)', re.I),
]

# --- DeepSeek Blocklist (proprietary terms that skip DeepSeek) ---

DEEPSEEK_BLOCKLIST = [
    "popchaos", "pop chaos", "nissim", "gone missin", "openclaw", "entropy bot",
    "revenue", "customer", "pricing", "our strategy", "our roadmap",
    "system design", "our plugin", "our architecture", "proprietary",
    "sidechain operator", "majestyk", "space age superstar",
]

# --- Task Classification Keywords ---

TASK_KEYWORDS = {
    "claude_only": {
        "keywords": [
            "decide", "should we", "should i", "strategy", "plan", "approve",
            "security", "review security", "attack surface", "red team",
            "architecture", "design the", "deploy", "push", "commit",
            "edit file", "modify", "debug", "fix this bug",
            "what do you think", "your opinion", "recommend",
        ],
        "model": "claude",
    },
    "gemini_research": {
        "keywords": [
            "summarize", "summarise", "recap", "overview", "what do.*say about",
            "read this codebase", "read this file", "read these",
            "find in", "search across", "cross-reference",
            "compare these", "find contradictions", "extract from",
            "analyze this pdf", "analyze these articles",
            "translate to english", "translate to spanish", "translate to",
        ],
        "model": "gemini",
    },
    "groq_reasoning": {
        "keywords": [
            "explain", "explain why", "explain how", "walk through", "step by step",
            "analyze this code", "what's wrong with", "code review",
            "write docs for", "document this",
            "how does.*work", "what happens when", "describe how",
        ],
        "model": "groq",
    },
    "qwen_code": {
        "keywords": [
            "generate", "scaffold", "boilerplate", "template",
            "write code for", "write a function", "write a class",
            "write tests for", "unit test", "test file", "integration test", "pytest",
            "translate.*to python", "translate.*to c\\+\\+", "translate.*to rust",
            "convert.*code", "rename all", "batch", "regex for",
            "refactor", "refactor.*to use", "apply.*pattern",
            "cmakelist.*", "github action", "ci config", "dockerfile",
        ],
        "model": "qwen",
    },
    "ollama_simple": {
        "keywords": [
            "what is", "what are", "define", "syntax for",
            "how to.*in python", "how to.*in bash", "how to.*in javascript",
            "convert.*json.*yaml", "convert.*yaml.*json", "format this",
            "spell check", "grammar", "fix typos",
            "give me.*names", "brainstorm.*names", "list.*ideas",
            "what http", "what status code",
            "is this a bug", "classify",
        ],
        "model": "ollama",
    },
}

# --- Follow-up Detection (Task Chaining) ---

FOLLOWUP_SIGNALS = [
    re.compile(r'^(now|also|then|and|next|what about|how about)\b', re.I),
    re.compile(r'^(compare that|expand on|tell me more|go deeper|elaborate)', re.I),
    re.compile(r'\b(the previous|from before|you just said|your answer|that result)\b', re.I),
]

# --- Confidence Scoring ---

HEDGING_WORDS = [
    "i'm not sure", "i think", "probably", "might be", "could be",
    "unclear", "ambiguous", "it depends", "hard to say",
    "i believe", "perhaps", "possibly", "not certain",
]

REFUSAL_SIGNALS = [
    "i can't", "i cannot", "i don't have enough", "beyond my capability",
    "i'm unable to", "not able to", "outside my", "i need more context",
]


@dataclass
class RouteResult:
    """Result of routing a task to a model."""
    model: str                          # "gemini", "groq", "claude", etc.
    wrapper: Optional[str]              # path to safe wrapper, or None for Claude
    reason: str                         # why this model was chosen
    tier: int                           # 1-4
    fallback_chain: list = field(default_factory=list)  # remaining fallbacks
    gate_triggered: Optional[str] = None  # which safety gate fired, if any
    is_followup: bool = False           # was this detected as a follow-up?
    confidence: float = 1.0             # routing confidence (0-1)


def log_event(status: str, detail: str) -> None:
    """Append to audit log."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(LOG_FILE, "a") as f:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            f.write(f"[{ts}] {status}: {detail}\n")
    except OSError:
        pass


# --- Rate Limit Tracking ---

def load_rate_limits() -> dict:
    """Load rate limit state from disk."""
    if RATE_LIMITS_FILE.exists():
        try:
            return json.loads(RATE_LIMITS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_rate_limits(state: dict) -> None:
    """Save rate limit state to disk."""
    RATE_LIMITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMITS_FILE.write_text(json.dumps(state, indent=2))


def record_call(model_name: str) -> None:
    """Record a call to a model for rate limit tracking."""
    state = load_rate_limits()
    now = datetime.now(timezone.utc).isoformat()
    if model_name not in state:
        state[model_name] = {"calls": []}
    state[model_name]["calls"].append(now)
    # Prune calls older than 60 seconds
    cutoff = time.time() - 60
    state[model_name]["calls"] = [
        c for c in state[model_name]["calls"]
        if datetime.fromisoformat(c.replace("Z", "+00:00")).timestamp() > cutoff
    ]
    save_rate_limits(state)


def check_rate_limit(model_name: str) -> bool:
    """Return True if model has capacity, False if rate-limited."""
    model = MODELS.get(model_name)
    if not model or model["rpm_limit"] is None:
        return True  # no rate limit

    state = load_rate_limits()
    if model_name not in state:
        return True

    cutoff = time.time() - 60
    recent_calls = [
        c for c in state.get(model_name, {}).get("calls", [])
        if datetime.fromisoformat(c.replace("Z", "+00:00")).timestamp() > cutoff
    ]
    remaining = model["rpm_limit"] - len(recent_calls)
    return remaining > model["headroom"]


# --- Model Health ---

def check_model_health(model_name: str) -> bool:
    """Check if a model is available. Returns True if healthy."""
    model = MODELS.get(model_name)
    if not model or not model["wrapper"]:
        return True  # Claude is always "available"

    # Gemini uses API directly — healthy if key exists
    if model_name == "gemini":
        return bool(GEMINI_API_KEY)

    wrapper = Path(model["wrapper"])
    if not wrapper.exists():
        return False

    if model_name == "ollama":
        # Check if ollama service is running
        try:
            result = subprocess.run(
                ["ollama", "list"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    if model_name == "groq":
        return bool(os.environ.get("GROQ_API_KEY"))

    if model_name == "deepseek":
        return bool(os.environ.get("DEEPSEEK_API_KEY"))

    # Gemini and Qwen: check if binary exists
    return True


def check_budget() -> float:
    """Return budget usage percentage (0-100). Returns 0 if can't read."""
    if BUDGET_FILE.exists():
        try:
            data = json.loads(BUDGET_FILE.read_text())
            return data.get("usage_percent", 0)
        except (json.JSONDecodeError, OSError, KeyError):
            pass
    return 0


# --- Gate 0a: Secrets Detection ---

def contains_secrets(message: str) -> bool:
    """Check if message contains credentials or PII."""
    for pattern in SECRET_PATTERNS:
        if pattern.search(message):
            return True
    return False


# --- Gate 0b: Size Validation ---

def check_message_size(message: str) -> Optional[str]:
    """Return error string if message is invalid size, None if OK."""
    if not message or not message.strip():
        return "empty"
    if len(message) > 500_000:
        return "oversized"
    return None


# --- Context Checks ---

def is_followup(message: str) -> bool:
    """Detect if this is a follow-up to a previous task."""
    for pattern in FOLLOWUP_SIGNALS:
        if pattern.search(message):
            return True
    return False


def get_last_model() -> Optional[str]:
    """Get the model used for the last routed task."""
    state = load_rate_limits()
    return state.get("_last_model")


def set_last_model(model_name: str) -> None:
    """Record which model was used for the last task."""
    state = load_rate_limits()
    state["_last_model"] = model_name
    save_rate_limits(state)


# --- DeepSeek Filter ---

def contains_deepseek_blocked(message: str) -> bool:
    """Check if message contains proprietary terms that should skip DeepSeek."""
    lower = message.lower()
    return any(term in lower for term in DEEPSEEK_BLOCKLIST)


# --- Task Classification ---

def classify_task(message: str) -> tuple[str, float]:
    """Classify a message into a task category.

    Returns (model_name, confidence).
    Confidence: 1.0 = exact keyword match, 0.5 = partial, 0.0 = no match.
    """
    lower = message.lower()

    # Check each category in priority order
    # Use word boundaries for plain keywords to prevent substring matches
    # (e.g., "plan" should NOT match "explanation")
    for category, config in TASK_KEYWORDS.items():
        for keyword in config["keywords"]:
            # If keyword already contains regex chars (.*+\), use as-is
            # Otherwise, wrap with word boundaries
            if any(c in keyword for c in r'.*+\()[]{}|^$?'):
                pattern = keyword
            else:
                pattern = rf'\b{keyword}\b'
            if re.search(pattern, lower):
                return config["model"], 0.9

    # Check for Claude-leaning signals before defaulting to Gemini (HT-6)
    claude_signals = [
        "this codebase", "this project", "my files", "our system",
        "this repo", "my repo", "these files", "this file",
        "the current", "our codebase", "my project",
    ]
    if any(sig in lower for sig in claude_signals):
        return "claude", 0.6

    # No match — ambiguous
    return "gemini", 0.5  # default to Gemini with low confidence


# --- Confidence Scoring (for responses) ---

def score_response_confidence(response: str) -> int:
    """Score a model's response confidence. 100 = confident, 0 = uncertain."""
    score = 100
    lower = response.lower()

    for word in HEDGING_WORDS:
        if word in lower:
            score -= 20

    for signal in REFUSAL_SIGNALS:
        if signal in lower:
            score -= 30

    return max(0, score)


# --- Fallback Chains ---

FALLBACK_CHAINS = {
    "research":     ["gemini", "groq", "deepseek", "ollama"],
    "code":         ["qwen", "groq", "ollama"],
    "reasoning":    ["gemini", "groq", "deepseek"],
    "simple":       ["ollama", "groq", "gemini"],
    "large_context": ["gemini", "groq"],
    "privacy":      ["ollama"],
    "security":     [],  # Claude only, no fallback
    "default":      ["gemini", "groq", "ollama", "deepseek"],
}


def get_fallback_chain(model: str, message: str) -> list[str]:
    """Get the appropriate fallback chain based on model and message."""
    lower = message.lower()

    # Determine task type for fallback chain selection
    if model == "claude":
        return []

    # Match task type to chain
    for keyword in ["summarize", "research", "read", "article", "search"]:
        if keyword in lower:
            chain = FALLBACK_CHAINS["research"][:]
            break
    else:
        for keyword in ["generate", "scaffold", "code", "write.*function"]:
            if re.search(keyword, lower):
                chain = FALLBACK_CHAINS["code"][:]
                break
        else:
            for keyword in ["what is", "define", "syntax", "convert", "format"]:
                if keyword in lower:
                    chain = FALLBACK_CHAINS["simple"][:]
                    break
            else:
                chain = FALLBACK_CHAINS["default"][:]

    # Remove the primary model from chain (it's already been tried)
    if model in chain:
        chain.remove(model)

    # Remove DeepSeek if message contains proprietary terms
    if contains_deepseek_blocked(message) and "deepseek" in chain:
        chain.remove("deepseek")

    return chain


# --- Main Router ---

def route(message: str, previous_model: Optional[str] = None) -> RouteResult:
    """Route a task to the best available model.

    Args:
        message: The task/prompt to route.
        previous_model: Override for last model (for follow-up detection).

    Returns:
        RouteResult with model, wrapper, reason, and fallback chain.
    """

    # === GATE 0b: Size (check FIRST — fast, avoids O(n^2) regex on huge msgs) ===
    size_issue = check_message_size(message)
    if size_issue == "empty":
        log_event("GATE_0B", "Empty message rejected")
        return RouteResult(
            model="claude",
            wrapper=None,
            reason="Empty message — please provide a task",
            tier=1,
            gate_triggered="empty",
        )
    if size_issue == "oversized":
        # Check secrets on a sample (first+last 10K) to avoid regex DoS
        sample = message[:10_000] + message[-10_000:]
        if contains_secrets(sample):
            log_event("GATE_0A", "Secrets in oversized message — Claude only")
            return RouteResult(
                model="claude",
                wrapper=None,
                reason="Oversized message with credentials — Claude only",
                tier=1,
                gate_triggered="secrets",
            )
        log_event("GATE_0B", f"Oversized message ({len(message)} chars) — Gemini only")
        if check_model_health("gemini") and check_rate_limit("gemini"):
            return RouteResult(
                model="gemini",
                wrapper=MODELS["gemini"]["wrapper"],
                reason=f"Message too large ({len(message)} chars) — needs 1M context",
                tier=2,
            )
        return RouteResult(
            model="claude",
            wrapper=None,
            reason="Oversized message, Gemini unavailable — queue for Claude",
            tier=1,
            gate_triggered="oversized_no_gemini",
        )

    # === GATE 0a: Secrets ===
    if contains_secrets(message):
        log_event("GATE_0A", "Secrets detected — Claude only")
        return RouteResult(
            model="claude",
            wrapper=None,
            reason="Message contains credentials/PII — Claude only",
            tier=1,
            gate_triggered="secrets",
        )

    # === STEP 1: Context Check ===

    # Follow-up detection
    if is_followup(message):
        last = previous_model or get_last_model()
        if last and last != "claude":
            if check_model_health(last) and check_rate_limit(last):
                log_event("FOLLOWUP", f"Follow-up detected — routing to {last}")
                return RouteResult(
                    model=last,
                    wrapper=MODELS[last]["wrapper"],
                    reason=f"Follow-up to previous task — same model ({last})",
                    tier=MODELS[last]["tier"],
                    is_followup=True,
                    fallback_chain=get_fallback_chain(last, message),
                )

    # === STEP 2: Classify task ===
    classified_model, confidence = classify_task(message)

    # Low confidence = ambiguous
    if confidence < 0.7:
        log_event("AMBIGUOUS", f"Low confidence ({confidence}) — defaulting to Claude")
        return RouteResult(
            model="claude",
            wrapper=None,
            reason=f"Ambiguous intent (confidence={confidence}) — Claude handles safely",
            tier=1,
            confidence=confidence,
        )

    # Claude-only tasks
    if classified_model == "claude":
        log_event("CLASSIFIED", "Claude-only task")
        return RouteResult(
            model="claude",
            wrapper=None,
            reason="Task requires Claude (strategy/tools/security/taste)",
            tier=1,
            confidence=confidence,
        )

    # === STEP 3: Health + Rate Limit Check ===
    target = classified_model
    fallback_chain = get_fallback_chain(target, message)

    # Try primary model
    if check_model_health(target) and check_rate_limit(target):
        log_event("ROUTED", f"{target} (confidence={confidence})")
        set_last_model(target)
        return RouteResult(
            model=target,
            wrapper=MODELS[target]["wrapper"],
            reason=f"Classified as {target} task (confidence={confidence})",
            tier=MODELS[target]["tier"],
            fallback_chain=fallback_chain,
            confidence=confidence,
        )

    # === STEP 4: Fallback Chain ===
    for fallback in fallback_chain:
        if check_model_health(fallback) and check_rate_limit(fallback):
            log_event("FALLBACK", f"{target}→{fallback}")
            set_last_model(fallback)
            return RouteResult(
                model=fallback,
                wrapper=MODELS[fallback]["wrapper"],
                reason=f"{target} unavailable — falling back to {fallback}",
                tier=MODELS[fallback]["tier"],
                fallback_chain=[f for f in fallback_chain if f != fallback],
                confidence=confidence,
            )

    # All external models failed — queue for Claude
    budget = check_budget()
    if budget > 90:
        log_event("QUEUE_WARN", f"All models unavailable + Claude budget at {budget}%")
        return RouteResult(
            model="claude",
            wrapper=None,
            reason=f"All models unavailable, Claude budget at {budget}% — task queued",
            tier=1,
            gate_triggered="all_failed_low_budget",
        )

    log_event("QUEUE", "All external models unavailable — queue for Claude")
    return RouteResult(
        model="claude",
        wrapper=None,
        reason="All external models unavailable — routing to Claude",
        tier=1,
    )


def clean_response(text: str) -> str:
    """Strip excessive markdown formatting from LLM responses.

    Removes: headers (#), bold (**), horizontal rules (---),
    and collapses excessive whitespace. Keeps the content readable
    as plain text for Telegram delivery.
    """
    if not text:
        return text

    # Strip qwen3 thinking chain (Thinking...\n[chain]\n...done thinking.\n[answer])
    thinking_match = re.search(r'(?:\.\.\.done thinking\.?\s*\n?)(.*)', text, re.DOTALL)
    if thinking_match and "Thinking..." in text:
        text = thinking_match.group(1).strip()

    lines = text.split("\n")
    cleaned = []
    for line in lines:
        # Strip markdown headers (## Header → Header)
        line = re.sub(r'^#{1,6}\s+', '', line)
        # Strip bold markers (**text** → text)
        line = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
        # Strip italic markers (*text* → text, but not bullet *)
        line = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', line)
        # Strip horizontal rules
        if re.match(r'^[-*_]{3,}\s*$', line):
            continue
        # Strip leading bullet markers (- item → item, * item → item)
        line = re.sub(r'^\s*[-*]\s+', '', line)
        # Strip numbered list markers (1. item → item)
        line = re.sub(r'^\s*\d+\.\s+', '', line)
        cleaned.append(line)

    result = "\n".join(cleaned)
    # Collapse 3+ consecutive newlines to 2
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def execute(message: str, dry_run: bool = False, verbose: bool = False,
            force_model: Optional[str] = None) -> str:
    """Route and optionally execute a task.

    Args:
        message: The task to route.
        dry_run: If True, only show routing decision (don't execute).
        verbose: If True, show detailed routing info.
        force_model: If set, bypass routing and use this model directly.

    Returns:
        Model response string, or routing info if dry_run.
    """
    if force_model:
        if force_model not in MODELS:
            return f"[ERROR] Unknown model '{force_model}'. Available: {', '.join(MODELS.keys())}"
        model_info = MODELS[force_model]
        result = RouteResult(
            model=force_model,
            tier=model_info["tier"],
            reason=f"Forced to {force_model} via --model flag",
            wrapper=model_info["wrapper"],
            fallback_chain=[],
            confidence=1.0,
        )
        log_event("FORCED", f"User forced model={force_model}")
    else:
        result = route(message)

    if verbose or dry_run:
        info = (
            f"Model: {result.model}\n"
            f"Tier: {result.tier}\n"
            f"Reason: {result.reason}\n"
            f"Wrapper: {result.wrapper or 'native (Claude)'}\n"
            f"Confidence: {result.confidence}\n"
            f"Follow-up: {result.is_followup}\n"
            f"Gate: {result.gate_triggered or 'none'}\n"
            f"Fallbacks: {' → '.join(result.fallback_chain) or 'none'}"
        )
        if dry_run:
            return info

        print(f"--- Routing Decision ---\n{info}\n--- Executing ---\n", file=sys.stderr)

    if result.model == "claude":
        return f"[QUEUE FOR CLAUDE] {result.reason}\nTask: {message}"

    # Add formatting instruction to match Claude's communication style
    formatted_message = message + (
        "\n\n[Style: Respond like a sharp technical co-founder. "
        "Direct, concise, no fluff. Plain text only — no markdown headers, "
        "no bold, no bullet lists, no numbered lists. Short paragraphs. "
        "If the answer is one sentence, give one sentence. "
        "Don't pad with filler like 'Great question!' or 'Here's what I found:'. "
        "Just answer.]"
    )

    # Execute — Gemini uses REST API, everything else uses safe wrapper
    try:
        record_call(result.model)
        response = ""

        if result.model == "gemini":
            # Direct API call — bypasses CLI agent mode
            try:
                response = _call_gemini_api(formatted_message)
                response = clean_response(response)
            except Exception as e:
                log_event("ERROR", f"gemini API failed: {e}")
                response = ""
        else:
            if not result.wrapper:
                return f"[ERROR] No wrapper for model {result.model}"
            proc = subprocess.run(
                [result.wrapper, "-p", formatted_message],
                capture_output=True,
                text=True,
                timeout=120,
            )
            response = clean_response(proc.stdout.strip())
            if proc.returncode != 0:
                log_event("ERROR", f"{result.model} failed: {proc.stderr.strip()}")
                response = ""

        # Fallback chain (works for any model failure)
        if not response:
            for fallback in result.fallback_chain:
                if not check_model_health(fallback) or not check_rate_limit(fallback):
                    continue
                log_event("FALLBACK_EXEC", f"{result.model}→{fallback}")
                record_call(fallback)
                try:
                    if fallback == "gemini":
                        fb_response = _call_gemini_api(formatted_message)
                    else:
                        fb_wrapper = MODELS[fallback]["wrapper"]
                        if not fb_wrapper:
                            continue
                        fb_proc = subprocess.run(
                            [fb_wrapper, "-p", formatted_message],
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        fb_response = fb_proc.stdout.strip() if fb_proc.returncode == 0 else ""
                    if fb_response:
                        response = clean_response(fb_response)
                        break
                except Exception:
                    continue

            if not response:
                return f"[ALL MODELS FAILED] {result.model} and fallbacks exhausted."

        # --- Validate output through delegation_validator ---
        if HAS_VALIDATOR and response:
            # Infer validator task_type from routing context
            validator_type = "general"
            msg_lower = message.lower()
            if any(kw in msg_lower for kw in ["code", "implement", "function", "class", "def ", "import"]):
                validator_type = "code"
            elif any(kw in msg_lower for kw in ["file", "path", "directory", "find", "locate"]):
                validator_type = "file_analysis"
            elif any(kw in msg_lower for kw in ["count", "how many", "number of", "total"]):
                validator_type = "count"

            validation = validate_delegated_output(response, task_type=validator_type)

            if validation["blocked"]:
                warnings_str = "; ".join(validation["warnings"])
                log_event("VALIDATION_BLOCKED", f"{result.model} output blocked: {warnings_str}")
                return f"[BLOCKED BY VALIDATOR] {result.model} output failed safety check: {warnings_str}. Task queued for Claude."

            if validation["warnings"]:
                warnings_str = "; ".join(validation["warnings"])
                log_event("VALIDATION_WARNING", f"{result.model}: {warnings_str}")
                response = f"[VALIDATION WARNINGS: {warnings_str}]\n{response}"

        # Score confidence
        conf = score_response_confidence(response)
        if conf < 60 and result.fallback_chain:
            log_event("LOW_CONFIDENCE", f"{result.model} response scored {conf}")
            # Don't auto-escalate in execution — flag for review
            response = f"[LOW CONFIDENCE: {conf}/100] {response}"

        return response

    except subprocess.TimeoutExpired:
        log_event("TIMEOUT", f"{result.model} timed out (120s)")
        return f"[TIMEOUT] {result.model} took >120s. Task queued for Claude."


# --- CLI ---

def main():
    import argparse

    parser = argparse.ArgumentParser(description="LLM Router — route tasks to the best model")
    parser.add_argument("message", nargs="?", help="Task to route (positional)")
    parser.add_argument("-p", "--prompt", help="Task to route (same as positional, for consistency with safe wrappers)")
    parser.add_argument("--dry-run", action="store_true", help="Show routing decision only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show routing details")
    parser.add_argument("--score", help="Score a response's confidence (pass response text)")
    parser.add_argument("--model", choices=list(MODELS.keys()), help="Force a specific model (bypass routing)")
    parser.add_argument("--health", action="store_true", help="Check all model health")
    parser.add_argument("--rates", action="store_true", help="Show current rate limit state")
    args = parser.parse_args()

    # Support both positional and -p flag (consistent with safe wrappers)
    if args.prompt and not args.message:
        args.message = args.prompt

    if args.health:
        print("Model Health Check:")
        for name in MODELS:
            healthy = check_model_health(name)
            rate_ok = check_rate_limit(name)
            status = "OK" if (healthy and rate_ok) else "DEGRADED" if healthy else "DOWN"
            rpm = MODELS[name]["rpm_limit"]
            rpm_str = f"{rpm} RPM" if rpm else "unlimited"
            print(f"  {name:12s} [{status:8s}] tier={MODELS[name]['tier']} rpm={rpm_str}")
        budget = check_budget()
        print(f"\n  Claude budget: {budget:.0f}% used")
        return

    if args.rates:
        state = load_rate_limits()
        print("Rate Limit State:")
        cutoff = time.time() - 60
        for name in MODELS:
            if name in state:
                recent = [
                    c for c in state[name].get("calls", [])
                    if datetime.fromisoformat(c.replace("Z", "+00:00")).timestamp() > cutoff
                ]
                rpm = MODELS[name]["rpm_limit"] or "unlimited"
                print(f"  {name:12s} {len(recent)} calls/min (limit: {rpm})")
            else:
                print(f"  {name:12s} 0 calls/min")
        print(f"\n  Last model: {state.get('_last_model', 'none')}")
        return

    if args.score:
        conf = score_response_confidence(args.score)
        print(f"Confidence: {conf}/100")
        if conf < 60:
            print("VERDICT: Escalate to next tier")
        else:
            print("VERDICT: Response acceptable")
        return

    if not args.message:
        # Read from stdin
        if not sys.stdin.isatty():
            args.message = sys.stdin.read().strip()
        else:
            parser.print_help()
            return

    output = execute(args.message, dry_run=args.dry_run, verbose=args.verbose,
                     force_model=args.model)
    print(output)


if __name__ == "__main__":
    main()
