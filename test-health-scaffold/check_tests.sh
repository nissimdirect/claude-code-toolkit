#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# check_tests.sh — Framework-agnostic skip-if-green gate
#
# USAGE:
#   Copy this script into your project root (next to .test-manifest.json).
#   Run it before your test command. Exit code tells you what to do:
#
#     ./check_tests.sh && echo "Skip tests" || pytest
#
#   Or in a Makefile / CI step:
#
#     test:
#         ./check_tests.sh || pytest
#
# EXIT CODES:
#   0 — Tests are green, no source changes. Safe to skip.
#   1 — Tests need to run (no manifest, stale, branch mismatch, or changes).
#
# REQUIRES:
#   - python3 (for JSON parsing)
#   - git
#   - .test-manifest.json (produced by conftest_manifest.py)
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

MANIFEST=".test-manifest.json"

# ── 1. No manifest? Run tests. ──
if [[ ! -f "$MANIFEST" ]]; then
    echo "No test manifest found. Running tests."
    exit 1
fi

# ── 2. Parse manifest fields via python3 one-liner ──
read -r green branch_manifest sha max_age_hours <<< "$(
    python3 -c "
import json, sys
m = json.load(open('$MANIFEST'))
print(m.get('green', False),
      m.get('branch', ''),
      m.get('commit_sha', ''),
      m.get('max_age_hours', 24))
"
)"

# ── 3. Not green? Run tests. ──
if [[ "$green" != "True" ]]; then
    echo "Last run was not green (green=$green). Running tests."
    exit 1
fi

# ── 4. Branch mismatch? Run tests. ──
current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
if [[ "$branch_manifest" != "$current_branch" ]]; then
    echo "Branch changed ($branch_manifest -> $current_branch). Running tests."
    exit 1
fi

# ── 5. Manifest age check ──
manifest_ts="$(python3 -c "
import json
m = json.load(open('$MANIFEST'))
print(m.get('timestamp', ''))
")"

is_stale="$(python3 -c "
from datetime import datetime, timezone
ts = '$manifest_ts'
max_h = $max_age_hours
try:
    # Handle both Z suffix and +00:00
    ts_clean = ts.replace('Z', '+00:00')
    dt = datetime.fromisoformat(ts_clean)
    age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    print('stale' if age_h > max_h else 'fresh')
except Exception:
    print('stale')
")"

if [[ "$is_stale" == "stale" ]]; then
    echo "Test manifest is older than ${max_age_hours}h. Running tests."
    exit 1
fi

# ── 6. SHA format validation ──
if ! echo "$sha" | grep -qE '^[0-9a-f]{40}$'; then
    echo "Invalid SHA in manifest: '$sha'. Running tests."
    exit 1
fi

# ── 7. Check for source changes since manifest SHA ──
# No HEAD — catches unstaged changes too.
diff_output="$(git diff "$sha" -- src/ tests/ 2>/dev/null || echo "DIFF_ERROR")"

if [[ "$diff_output" == "DIFF_ERROR" ]]; then
    echo "Could not diff against manifest SHA ($sha). Running tests."
    exit 1
fi

if [[ -n "$diff_output" ]]; then
    echo "Source changes detected since $sha. Running tests."
    exit 1
fi

# ── 8. All clear — skip tests ──
short_sha="${sha:0:8}"
echo "Tests green at ${short_sha}, no changes. Skipping."
exit 0
