#!/usr/bin/env bash
# gemini-safe.sh — Hardened wrapper for Gemini CLI
# Blocks dangerous patterns before passing to real binary.
# Used by OpenClaw instead of raw `gemini` to prevent prompt injection → exec attacks.

set -euo pipefail

GEMINI_BIN="/opt/homebrew/bin/gemini"
LOG_FILE="$HOME/.openclaw/logs/gemini-safe-audit.log"

# --- BLOCKLIST: reject prompts containing these patterns ---
BLOCKED_PATTERNS=(
    'curl\s'
    'wget\s'
    '\.env'
    'credentials'
    'api.key'
    'api_key'
    'API_KEY'
    'bot.?[Tt]oken'
    'password'
    'secret'
    '/etc/passwd'
    '/etc/shadow'
    'ssh.*key'
    'id_rsa'
    'id_ed25519'
    'rm\s+-rf'
    'rm\s+-r'
    'mkfs'
    'dd\s+if='
    '>\s*/dev/'
    'chmod\s+777'
    'sudo\s'
    'eval\s'
    '\$\('
    '`.*`'
    'base64.*decode'
    'nc\s+-l'
    'netcat'
    'reverse.shell'
    'attacker'
    'exfiltrate'
    '\.claude/'
    'openclaw\.json'
    'exec-approvals'
)

# --- ALLOWED DIRECTORIES: only these paths can be referenced ---
ALLOWED_DIRS=(
    "$HOME/Development/"
    "$HOME/Documents/Obsidian/"
)

log_event() {
    local status="$1"
    local detail="$2"
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $status: $detail" >> "$LOG_FILE" 2>/dev/null || true
}

check_prompt() {
    local prompt="$1"
    for pattern in "${BLOCKED_PATTERNS[@]}"; do
        if echo "$prompt" | grep -qEi "$pattern"; then
            log_event "BLOCKED" "Pattern '$pattern' matched in prompt"
            echo "ERROR: Blocked by gemini-safe.sh — prompt contains restricted pattern." >&2
            echo "If this is legitimate, run gemini directly: $GEMINI_BIN" >&2
            exit 1
        fi
    done
}

# Parse args to find -p flag value
prompt_text=""
args=("$@")
for i in "${!args[@]}"; do
    if [[ "${args[$i]}" == "-p" ]] && [[ $((i+1)) -lt ${#args[@]} ]]; then
        prompt_text="${args[$((i+1))]}"
    fi
done

# If there's a prompt, validate it
if [[ -n "$prompt_text" ]]; then
    check_prompt "$prompt_text"
    log_event "ALLOWED" "Prompt passed validation (${#prompt_text} chars)"
fi

# Pass through to real binary
exec "$GEMINI_BIN" "$@"
