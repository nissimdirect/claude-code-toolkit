#!/usr/bin/env python3
"""Directive Watcher — polls entropy-insights/ for new signed directives.

Runs as a background process (launched by cron or launchd).
When a new directive with `status: new` is found:
1. Verifies HMAC signature
2. Spawns a Claude Code session to execute it
3. Updates the directive status to `in-progress` then `done`
4. Writes result to claude-code-insights/ for Entropy Bot to relay back

Usage:
    python3 directive_watcher.py              # Run once (check and exit)
    python3 directive_watcher.py --daemon     # Poll every 60 seconds
    python3 directive_watcher.py --dry-run    # Check but don't execute
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ENTROPY_DIR = Path.home() / 'Development' / 'AI-Knowledge-Exchange' / 'entropy-insights'
CLAUDE_DIR = Path.home() / 'Development' / 'AI-Knowledge-Exchange' / 'claude-code-insights'
VERIFY_SCRIPT = Path.home() / 'Development' / 'tools' / 'verify_directive.py'
LOG_FILE = Path.home() / '.claude' / '.locks' / 'directive-watcher.log'
POLL_INTERVAL = 60  # seconds
CLAUDE_TIMEOUT = 300  # 5 minutes per directive


def log(msg: str):
    """Append to log file and print."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, 'a') as f:
            f.write(line + '\n')
    except OSError:
        pass


def find_new_directives() -> list[Path]:
    """Find all directive files with status: new."""
    if not ENTROPY_DIR.exists():
        return []

    new_files = []
    for f in sorted(ENTROPY_DIR.glob('*-directive-*.md')):
        try:
            content = f.read_text()
            if re.search(r'^status:\s*new\s*$', content, re.MULTILINE):
                if re.search(r'^category:\s*directive\s*$', content, re.MULTILINE):
                    new_files.append(f)
        except OSError:
            continue
    return new_files


def verify_directive(filepath: Path) -> bool:
    """Run verify_directive.py. Returns True if signature is valid."""
    try:
        result = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), str(filepath)],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def update_status(filepath: Path, new_status: str):
    """Update the status field in a directive file's frontmatter."""
    try:
        content = filepath.read_text()
        updated = re.sub(
            r'^status:\s*\S+',
            f'status: {new_status}',
            content,
            count=1,
            flags=re.MULTILINE
        )
        filepath.write_text(updated)
    except OSError:
        log(f"WARNING: Could not update status on {filepath.name}")


def extract_task(filepath: Path) -> str:
    """Extract the task description from a directive file."""
    content = filepath.read_text()
    # Get everything after the frontmatter
    parts = content.split('---', 2)
    if len(parts) >= 3:
        body = parts[2].strip()
        # Remove the markdown header
        lines = body.split('\n')
        task_lines = [l for l in lines if not l.startswith('#')]
        return '\n'.join(task_lines).strip()
    return content


def extract_project_dir(filepath: Path) -> str | None:
    """Extract project directory from directive if specified."""
    content = filepath.read_text()
    match = re.search(r'\*\*Project directory:\*\*\s*`([^`]+)`', content)
    if match:
        path = match.group(1).replace('~', str(Path.home()))
        if os.path.isdir(path):
            return path
    return None


def execute_directive(filepath: Path, dry_run: bool = False) -> bool:
    """Execute a verified directive via Claude Code CLI."""
    task = extract_task(filepath)
    project_dir = extract_project_dir(filepath)

    if not task:
        log(f"SKIP: Empty task in {filepath.name}")
        return False

    log(f"EXECUTING: {filepath.name}")
    log(f"  Task: {task[:100]}...")
    if project_dir:
        log(f"  Project: {project_dir}")

    if dry_run:
        log("  [DRY RUN] Would execute via Claude Code CLI")
        return True

    # Mark as in-progress
    update_status(filepath, 'in-progress')

    # Build Claude Code prompt
    prompt = (
        f"You are executing a signed directive from Entropy Bot (verified by HMAC). "
        f"Task: {task}"
    )
    if project_dir:
        prompt += f"\nWork in project directory: {project_dir}"

    prompt += (
        "\n\nAfter completing the task, write a brief status update."
    )

    # Execute via Claude CLI
    try:
        cmd = ['claude', '-p', prompt, '--output-format', 'text']
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=CLAUDE_TIMEOUT,
            cwd=project_dir or str(Path.home() / 'Development'),
        )

        success = result.returncode == 0
        output = result.stdout.strip() if success else result.stderr.strip()

        # Write result to claude-code-insights/
        write_result(filepath.name, task, output, success)

        # Update directive status
        update_status(filepath, 'done' if success else 'failed')

        log(f"  Result: {'SUCCESS' if success else 'FAILED'}")
        return success

    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT after {CLAUDE_TIMEOUT}s")
        update_status(filepath, 'timeout')
        write_result(filepath.name, task, f"Timed out after {CLAUDE_TIMEOUT}s", False)
        return False
    except (OSError, FileNotFoundError) as e:
        log(f"  ERROR: {e}")
        update_status(filepath, 'error')
        return False


def write_result(directive_name: str, task: str, output: str, success: bool):
    """Write execution result to claude-code-insights/ for Entropy Bot."""
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    status_word = 'completed' if success else 'failed'

    result_content = (
        f"---\n"
        f"date: {today}\n"
        f"from: claude-code\n"
        f"category: status\n"
        f"priority: P1\n"
        f"status: new\n"
        f"re: {directive_name}\n"
        f"---\n\n"
        f"# Directive {status_word.title()}: {task[:60]}\n\n"
        f"**Status:** {status_word}\n"
        f"**Directive:** {directive_name}\n\n"
        f"## Result\n\n{output[:2000]}\n"
    )

    result_file = CLAUDE_DIR / f"{today}-status-directive-{status_word}.md"
    counter = 1
    while result_file.exists():
        result_file = CLAUDE_DIR / f"{today}-status-directive-{status_word}-{counter}.md"
        counter += 1

    result_file.write_text(result_content)
    log(f"  Result written to {result_file.name}")


def run_once(dry_run: bool = False) -> int:
    """Check for new directives and execute them. Returns count executed."""
    directives = find_new_directives()
    if not directives:
        return 0

    log(f"Found {len(directives)} new directive(s)")
    executed = 0

    for filepath in directives:
        # Verify signature
        if not verify_directive(filepath):
            log(f"REJECTED: {filepath.name} — signature verification failed")
            update_status(filepath, 'rejected')
            write_result(filepath.name, "Unknown", "Signature verification failed — not executed", False)
            continue

        if execute_directive(filepath, dry_run=dry_run):
            executed += 1

    return executed


def daemon(dry_run: bool = False):
    """Poll for new directives every POLL_INTERVAL seconds."""
    log(f"Directive watcher started (polling every {POLL_INTERVAL}s)")
    while True:
        try:
            run_once(dry_run=dry_run)
        except Exception as e:
            log(f"ERROR in poll cycle: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Watch for signed directives from Entropy Bot')
    parser.add_argument('--daemon', action='store_true', help='Poll continuously')
    parser.add_argument('--dry-run', action='store_true', help='Check but do not execute')
    args = parser.parse_args()

    if args.daemon:
        daemon(dry_run=args.dry_run)
    else:
        count = run_once(dry_run=args.dry_run)
        if count == 0:
            log("No new directives found")
