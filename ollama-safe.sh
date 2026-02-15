#!/usr/bin/env bash
# ollama-safe.sh — Hardened wrapper for Ollama (local LLM)
# Same blocklist pattern as gemini-safe.sh / qwen-safe.sh.
# Unlike cloud tools, Ollama runs locally — zero rate limits, zero cost.

set -euo pipefail

OLLAMA_BIN="/opt/homebrew/bin/ollama"
LOG_FILE="$HOME/.openclaw/logs/ollama-safe-audit.log"

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
            echo "ERROR: Blocked by ollama-safe.sh — prompt contains restricted pattern." >&2
            echo "If this is legitimate, run ollama directly: $OLLAMA_BIN" >&2
            exit 1
        fi
    done
}

# Usage: ollama-safe.sh -p "prompt" [-m model]
# Translates to: ollama run <model> "<prompt>"
prompt_text=""
model="qwen3:8b"  # default model
args=("$@")

for i in "${!args[@]}"; do
    if [[ "${args[$i]}" == "-p" ]] && [[ $((i+1)) -lt ${#args[@]} ]]; then
        prompt_text="${args[$((i+1))]}"
    fi
    if [[ "${args[$i]}" == "-m" || "${args[$i]}" == "--model" ]] && [[ $((i+1)) -lt ${#args[@]} ]]; then
        model="${args[$((i+1))]}"
    fi
done

if [[ -z "$prompt_text" ]]; then
    echo "Usage: ollama-safe.sh -p \"your prompt\" [-m model]" >&2
    echo "Default model: qwen3:8b" >&2
    echo "Available: qwen3:8b (general), qwen2.5-coder:7b (code)" >&2
    exit 1
fi

check_prompt "$prompt_text"
log_event "ALLOWED" "Prompt passed validation (${#prompt_text} chars) model=$model"

# Use HTTP API instead of `ollama run` CLI — the CLI is interactive/streaming
# and hangs in subprocess contexts (teammates, cron, pipes).
# Disable thinking for qwen3 models to avoid 10-15s chain-of-thought overhead.
OLLAMA_API="http://localhost:11434/api/generate"

# Build JSON payload (escape prompt for JSON)
json_prompt=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$prompt_text")

response=$(curl -s --max-time 60 "$OLLAMA_API" \
    -d "{\"model\": \"$model\", \"prompt\": $json_prompt, \"stream\": false, \"options\": {\"num_predict\": 1024}}")

if [[ $? -ne 0 ]]; then
    log_event "ERROR" "Ollama API call failed (curl exit $?)"
    echo "ERROR: Ollama API call failed" >&2
    exit 1
fi

# Extract response text
output=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('response',''))" 2>/dev/null)

if [[ -z "$output" ]]; then
    log_event "ERROR" "Empty response from Ollama API"
    echo "ERROR: Empty response from Ollama" >&2
    exit 1
fi

echo "$output"
