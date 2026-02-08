#!/usr/bin/env python3
"""
Input Log Rotation Tool
Caps user-input-log.md at 200 lines, archives older entries monthly.
Code > Tokens: runs locally, zero API cost.
"""

import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime


def atomic_write(filepath, content, permissions=0o600):
    """Write to temp file, then atomic rename. Crash-safe."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent),
        prefix=f'.{filepath.name}.',
        suffix='.tmp'
    )
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, permissions)
        os.rename(tmp_path, str(filepath))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

# Dynamic path resolution — no hardcoded usernames
HOME = Path.home()
PROJECT_KEY = f"-{str(HOME).replace('/', '-').lstrip('-')}"
MEMORY_DIR = HOME / '.claude' / 'projects' / PROJECT_KEY / 'memory'

LOG_PATH = MEMORY_DIR / 'user-input-log.md'
ARCHIVE_DIR = MEMORY_DIR / 'archives'
MAX_LINES = 200


def count_lines(filepath):
    """Count lines in file."""
    if not filepath.exists():
        return 0
    return len(filepath.read_text(encoding='utf-8').splitlines())


def rotate_log(dry_run=False):
    """Rotate input log if over MAX_LINES."""
    if not LOG_PATH.exists():
        print("No input log found.")
        return

    lines = LOG_PATH.read_text(encoding='utf-8').splitlines()
    total = len(lines)

    if total <= MAX_LINES:
        print(f"Log is {total} lines (limit: {MAX_LINES}). No rotation needed.")
        return

    # Find header (everything before first "## " section after line 10)
    header_end = 0
    for i, line in enumerate(lines):
        if line.startswith('## ') and i > 5:
            header_end = i
            break

    header = lines[:header_end]
    content = lines[header_end:]

    # Keep the most recent MAX_LINES - len(header) lines of content
    keep_count = MAX_LINES - len(header)
    archive_content = content[:-keep_count] if keep_count < len(content) else []
    keep_content = content[-keep_count:] if keep_count < len(content) else content

    if not archive_content:
        print("Nothing to archive.")
        return

    # Archive filename
    now = datetime.now()
    archive_name = f"input-log-archive-{now.strftime('%Y-%m')}.md"
    archive_path = ARCHIVE_DIR / archive_name

    print(f"Log: {total} lines → keeping {len(header) + len(keep_content)}, archiving {len(archive_content)}")

    if not dry_run:
        # Create archive directory
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        # Append to archive (may already exist if multiple rotations in same month)
        existing = archive_path.read_text(encoding='utf-8') if archive_path.exists() else ''
        archive_text = existing + '\n'.join(archive_content) + '\n'
        atomic_write(archive_path, archive_text)

        # Rewrite log with header + recent content (atomic)
        new_log = '\n'.join(header + keep_content) + '\n'
        atomic_write(LOG_PATH, new_log)

        print(f"Archived to: {archive_path}")
        print(f"Log trimmed to: {count_lines(LOG_PATH)} lines")
    else:
        print(f"Would archive to: {ARCHIVE_DIR / archive_name}")
        print("Run without --dry-run to apply.")


def stats():
    """Show log stats."""
    if not LOG_PATH.exists():
        print("No input log found.")
        return

    lines = count_lines(LOG_PATH)
    size = LOG_PATH.stat().st_size
    print(f"Input log: {lines} lines, {size:,} bytes")
    print(f"Limit: {MAX_LINES} lines")
    print(f"Status: {'NEEDS ROTATION' if lines > MAX_LINES else 'OK'}")

    # Check archives
    if ARCHIVE_DIR.exists():
        archives = list(ARCHIVE_DIR.glob('input-log-archive-*.md'))
        if archives:
            print(f"\nArchives: {len(archives)} files")
            for a in sorted(archives):
                print(f"  {a.name}: {count_lines(a)} lines")


def main():
    if '--stats' in sys.argv:
        stats()
    elif '--dry-run' in sys.argv:
        rotate_log(dry_run=True)
    else:
        rotate_log(dry_run=False)


if __name__ == '__main__':
    main()
