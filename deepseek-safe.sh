#!/usr/bin/env bash
# deepseek-safe.sh — Hardened wrapper for DeepSeek API (cloud LLM, free tier)
# Uses curl to call DeepSeek's OpenAI-compatible API.
# Requires DEEPSEEK_API_KEY env var.
# WARNING: Data stored in China. Do NOT send sensitive/personal data.

set -euo pipefail

LOG_FILE="$HOME/.openclaw/logs/deepseek-safe-audit.log"

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
            echo "ERROR: Blocked by deepseek-safe.sh — prompt contains restricted pattern." >&2
            exit 1
        fi
    done
}

# Check for API key
if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "ERROR: DEEPSEEK_API_KEY not set. Get one free at https://platform.deepseek.com" >&2
    exit 1
fi

prompt_text=""
model="deepseek-chat"  # default: DeepSeek V3
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
    echo "Usage: deepseek-safe.sh -p \"your prompt\" [-m model]" >&2
    echo "Default model: deepseek-chat (V3)" >&2
    echo "Available: deepseek-chat (V3), deepseek-reasoner (R1)" >&2
    echo "WARNING: Data is processed/stored in China." >&2
    exit 1
fi

check_prompt "$prompt_text"
log_event "ALLOWED" "Prompt passed validation (${#prompt_text} chars) model=$model"

# Call DeepSeek API (OpenAI-compatible)
response=$(curl -sS -X POST "https://api.deepseek.com/chat/completions" \
    -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"$model\",
        \"messages\": [{\"role\": \"user\", \"content\": $(echo "$prompt_text" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')}],
        \"max_tokens\": 4096,
        \"stream\": false
    }" 2>&1)

# Extract just the message content
echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if 'choices' in data:
        print(data['choices'][0]['message']['content'])
    elif 'error' in data:
        print(f\"ERROR: {data['error']['message']}\", file=sys.stderr)
        sys.exit(1)
    else:
        print(json.dumps(data, indent=2))
except:
    print(sys.stdin.read())
"
