#!/usr/bin/env python3
"""Ollama Model Keepalive — Prevents cold-start latency.

Sends a minimal request every 4 minutes to keep the model loaded in GPU/RAM.
Ollama's default keepalive is 5 minutes, so 4-minute pings prevent unload.

Run as: python3 ollama_keepalive.py &
Or via cron: */4 * * * * python3 ~/Development/tools/ollama_keepalive.py
"""

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

OLLAMA_URL = 'http://localhost:11434/api/chat'
MODELS_TO_KEEP = ['mistral:7b', 'qwen3:8b']  # Primary + fallback
PING_INTERVAL = 240  # 4 minutes (Ollama default keepalive = 5 min)
LOCK_FILE = Path.home() / '.claude/.locks/ollama-keepalive.pid'


def is_ollama_running() -> bool:
    try:
        req = urllib.request.Request('http://localhost:11434/api/tags')
        urllib.request.urlopen(req, timeout=2)
        return True
    except Exception:
        return False


def ping_model(model: str) -> bool:
    payload = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': 'ping'}],
        'stream': False,
        'options': {'num_predict': 1},
    }).encode()
    
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            json.loads(resp.read())  # Consume response to keep model loaded
            return True
    except Exception:
        return False


def run_once():
    """Single keepalive pass — for cron mode."""
    if not is_ollama_running():
        return
    for model in MODELS_TO_KEEP:
        ping_model(model)


def _is_pid_running(pid: int) -> bool:
    """Check if a PID is actually running (HT-8: stale PID detection)."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def run_daemon():
    """Continuous keepalive loop."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    # HT-8: Check for stale PID file before refusing to start
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if _is_pid_running(old_pid):
                print(f"Already running (PID {old_pid})")
                sys.exit(0)
        except (ValueError, OSError):
            pass
        LOCK_FILE.unlink(missing_ok=True)

    # Write PID file
    LOCK_FILE.write_text(str(os.getpid()))
    
    try:
        while True:
            if is_ollama_running():
                for model in MODELS_TO_KEEP:
                    ping_model(model)
            time.sleep(PING_INTERVAL)
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        run_once()
    else:
        run_daemon()
