#!/bin/bash
# claude-lint.sh — Run Claude Code as a linter/reviewer on git changes
# Usage: claude-lint.sh [base-branch]
# Default base branch: main

set -euo pipefail

BASE="${1:-main}"

# Verify we're in a git repo
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "Error: Not inside a git repo"
    exit 1
fi

# Check if base branch exists
if ! git rev-parse --verify "$BASE" &>/dev/null; then
    # Try 'master' if 'main' doesn't exist
    if git rev-parse --verify "master" &>/dev/null; then
        BASE="master"
    else
        echo "Error: Neither 'main' nor 'master' branch found. Specify base branch: claude-lint.sh <branch>"
        exit 1
    fi
fi

DIFF=$(git diff "$BASE"...HEAD 2>/dev/null || git diff "$BASE" 2>/dev/null)

if [ -z "$DIFF" ]; then
    echo "No changes found vs $BASE"
    exit 0
fi

echo "Linting changes vs $BASE..."

claude -p "You are a code linter and reviewer. Review the following diff for:
1. Typos and spelling errors in code, comments, and strings
2. Security issues (hardcoded secrets, injection risks, missing input validation)
3. Logic bugs (off-by-one, null checks, race conditions)
4. Style issues (inconsistent naming, unused imports, dead code)

For each issue found, output:
FILENAME:LINE_NUMBER
  SEVERITY: [error|warning|info]
  ISSUE: description

If no issues found, output: No issues found.
Do not output any other text.

\`\`\`diff
$DIFF
\`\`\`"
