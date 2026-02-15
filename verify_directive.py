#!/usr/bin/env python3
"""Verify signed directives from Entropy Bot.

Usage: python3 verify_directive.py <filepath>
Exit 0 = valid signature, safe to execute
Exit 1 = invalid/missing signature, require manual confirmation
Exit 2 = blocked (scope violation or rate limit)

The HMAC is computed over the file content with the `auth:` line removed,
using the shared secret in ~/.config/entropy-signing-key.
"""

import hashlib
import hmac
import json
import re
import sys
import time
from pathlib import Path

SECRET_PATH = Path.home() / ".config" / "entropy-signing-key"
RATE_STATE = Path.home() / ".claude" / ".locks" / ".directive-rate.json"
RATE_LIMIT_SECONDS = 300  # 1 directive per 5 minutes

# Paths that signed directives can NEVER touch
BLOCKED_PATHS = [
    str(Path.home() / ".claude"),
    str(Path.home() / ".config"),
    str(Path.home() / ".zshrc"),
    str(Path.home() / ".ssh"),
]

# Keywords in directive content that trigger scope block
BLOCKED_KEYWORDS = [
    "rm -rf", "git push", "git branch -D", "brew install",
    "pip install", "chmod", "chown", "sudo",
    "CLAUDE.md", "hooks/", "skills/", "settings.json",
    "api_key", "secret", "password", "token",
    "entropy-signing-key", "EXCHANGE-PROTOCOL",
]


def load_secret() -> bytes | None:
    """Load the signing key. Returns None if missing."""
    if not SECRET_PATH.exists():
        return None
    try:
        return SECRET_PATH.read_text().strip().encode()
    except OSError:
        return None


def extract_auth_and_content(filepath: str) -> tuple[str | None, str]:
    """Extract the auth field and the content without the auth line."""
    text = Path(filepath).read_text()
    auth_match = re.search(r'^auth:\s*(.+)$', text, re.MULTILINE)
    if not auth_match:
        return None, text

    auth_value = auth_match.group(1).strip()
    # Remove the auth line for HMAC computation
    content_without_auth = re.sub(r'^auth:\s*.+\n?', '', text, count=1, flags=re.MULTILINE)
    return auth_value, content_without_auth


def verify_hmac(secret: bytes, content: str, claimed_hmac: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    computed = hmac.new(secret, content.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, claimed_hmac)


def check_rate_limit() -> bool:
    """Returns True if within rate limit (OK to proceed)."""
    if not RATE_STATE.exists():
        return True
    try:
        data = json.loads(RATE_STATE.read_text())
        last = data.get("last_executed", 0)
        return (time.time() - last) >= RATE_LIMIT_SECONDS
    except (json.JSONDecodeError, OSError):
        return True


def record_execution():
    """Record that a directive was executed (for rate limiting)."""
    try:
        RATE_STATE.parent.mkdir(parents=True, exist_ok=True)
        RATE_STATE.write_text(json.dumps({"last_executed": time.time()}))
    except OSError:
        pass


def check_scope(content: str) -> str | None:
    """Check if directive content violates scope limits. Returns violation or None."""
    content_lower = content.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword.lower() in content_lower:
            return f"Blocked keyword: '{keyword}'"
    return None


def main():
    if len(sys.argv) != 2:
        print("Usage: verify_directive.py <filepath>", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    if not Path(filepath).exists():
        print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    # Load secret
    secret = load_secret()
    if secret is None:
        print("NO_KEY: Signing key not found at ~/.config/entropy-signing-key", file=sys.stderr)
        sys.exit(1)

    # Extract auth and content
    auth_value, content = extract_auth_and_content(filepath)
    if auth_value is None:
        print("NO_AUTH: No auth field in frontmatter", file=sys.stderr)
        sys.exit(1)

    # Verify HMAC
    if not verify_hmac(secret, content, auth_value):
        print("BAD_SIG: HMAC verification failed", file=sys.stderr)
        sys.exit(1)

    # Check scope
    violation = check_scope(content)
    if violation:
        print(f"SCOPE_BLOCK: {violation}", file=sys.stderr)
        sys.exit(2)

    # Check rate limit
    if not check_rate_limit():
        print("RATE_LIMIT: Too many directives, wait 5 minutes", file=sys.stderr)
        sys.exit(2)

    # All checks passed
    record_execution()
    print("VERIFIED: Signature valid, scope OK, rate limit OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
