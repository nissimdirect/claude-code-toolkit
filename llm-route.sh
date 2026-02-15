#!/usr/bin/env bash
# llm-route.sh — Shell wrapper for LLM router
# OpenClaw calls this to decide which model handles a task, then executes it.
#
# Usage:
#   llm-route.sh -p "your prompt"           # Route + execute
#   llm-route.sh -p "your prompt" --dry-run # Show routing decision only
#   llm-route.sh --health                   # Check all model health
#   llm-route.sh --rates                    # Show rate limit state

set -euo pipefail

ROUTER="$HOME/Development/tools/llm_router.py"

if [[ ! -f "$ROUTER" ]]; then
    echo "ERROR: Router not found at $ROUTER" >&2
    exit 1
fi

# Pass all arguments through to the Python router
exec python3 "$ROUTER" "$@"
