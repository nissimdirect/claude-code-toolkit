#!/usr/bin/env python3
"""
Context Memory Database - Production Grade
Tracks files read, token costs, session state for intelligent caching.

No external dependencies -- stdlib only (sqlite3, hashlib, pathlib, etc.)

CLI Usage:
    python context_db.py check <file_path>
    python context_db.py stats
    python context_db.py session start
    python context_db.py session end [--tasks "task1,task2"]
    python context_db.py mark <file_path> [--tokens N]
    python context_db.py reset
"""

import sqlite3
import hashlib
import sys
import os
import json
import time
import uuid
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# ContextDB -- core library class
# ---------------------------------------------------------------------------

class ContextDB:
    """
    Lightweight SQLite database for context management.
    - Tracks files read with timestamps and content hashes
    - Records session metrics (tokens, costs, tasks)
    - Enables semantic caching (skip re-reading unchanged files)
    """

    # Rough heuristic: 1 token ~ 4 bytes of text.  Used when caller does not
    # supply an explicit token cost.
    BYTES_PER_TOKEN = 4

    def __init__(self, db_path="~/.claude/context.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row   # allow dict-style access
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self):
        """Create tables for context tracking, migrating from old schema if needed."""
        self._migrate_if_needed()
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS files_read (
                file_path       TEXT PRIMARY KEY,
                last_read_ts    INTEGER NOT NULL,
                token_cost      INTEGER NOT NULL DEFAULT 0,
                content_hash    TEXT,
                file_size       INTEGER,
                metadata        TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id        TEXT PRIMARY KEY,
                start_time        INTEGER NOT NULL,
                end_time          INTEGER,
                total_tokens      INTEGER NOT NULL DEFAULT 0,
                tasks_completed   TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_files_ts
                ON files_read(last_read_ts);

            CREATE INDEX IF NOT EXISTS idx_sessions_start
                ON sessions(start_time);
        """)
        self.conn.commit()

    def _migrate_if_needed(self):
        """Detect old schema and migrate tables if column names changed."""
        # Check if old files_read table exists with old column names
        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files_read'")
        if cursor.fetchone() is None:
            return  # No existing table, nothing to migrate

        cols = [row[1] for row in self.conn.execute("PRAGMA table_info(files_read)").fetchall()]
        if "last_read_timestamp" in cols and "last_read_ts" not in cols:
            # Old schema detected -- rebuild tables with new column names
            self.conn.executescript("""
                DROP TABLE IF EXISTS files_read;
                DROP TABLE IF EXISTS context_checkpoints;
                DROP INDEX IF EXISTS idx_files_timestamp;
            """)
            # Also rebuild sessions if it has extra columns from old schema
            old_sess_cols = [row[1] for row in self.conn.execute("PRAGMA table_info(sessions)").fetchall()]
            if "input_tokens" in old_sess_cols or "cost_usd" in old_sess_cols or "files_read" in old_sess_cols:
                self.conn.execute("DROP TABLE IF EXISTS sessions")
            self.conn.commit()

    # ------------------------------------------------------------------
    # File tracking
    # ------------------------------------------------------------------

    def should_reread_file(self, file_path):
        """
        Determine whether *file_path* should be re-read.

        Returns
        -------
        (should_read: bool, status: str, detail: str)
            status is one of "UNREAD", "STALE", "FRESH".
            detail is a human-readable explanation.
        """
        path = Path(file_path).resolve()

        if not path.exists():
            return True, "UNREAD", "File does not exist on disk"

        row = self.conn.execute(
            "SELECT last_read_ts, content_hash FROM files_read WHERE file_path = ?",
            (str(path),),
        ).fetchone()

        if row is None:
            return True, "UNREAD", "Never read before"

        last_read_ts = row["last_read_ts"]
        old_hash = row["content_hash"]

        file_mtime = int(path.stat().st_mtime)

        if file_mtime > last_read_ts:
            # mtime newer -- verify with content hash
            current_hash = self._hash_file(path)
            if current_hash != old_hash:
                return True, "STALE", "Modified since last read"
            # mtime bumped but content identical (e.g. touch)
            return False, "FRESH", self._freshness_label(last_read_ts)

        return False, "FRESH", self._freshness_label(last_read_ts)

    def mark_file_read(self, file_path, token_cost=None, metadata=None):
        """
        Record that *file_path* was read.  If *token_cost* is None an
        estimate is computed from file size.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            return

        content_hash = self._hash_file(path)
        file_size = path.stat().st_size
        now = int(time.time())

        if token_cost is None:
            token_cost = max(1, file_size // self.BYTES_PER_TOKEN)

        self.conn.execute(
            """
            INSERT OR REPLACE INTO files_read
                (file_path, last_read_ts, token_cost, content_hash, file_size, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(path),
                now,
                token_cost,
                content_hash,
                file_size,
                json.dumps(metadata) if metadata else None,
            ),
        )
        self.conn.commit()

    def get_file_info(self, file_path):
        """Return a dict of stored info for *file_path*, or None."""
        path = Path(file_path).resolve()
        row = self.conn.execute(
            "SELECT * FROM files_read WHERE file_path = ?",
            (str(path),),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------

    def start_session(self, session_id=None):
        """
        Record a new session start.  Returns the session_id (auto-generated
        if not supplied).
        """
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]

        now = int(time.time())
        self.conn.execute(
            """
            INSERT INTO sessions (session_id, start_time, total_tokens)
            VALUES (?, ?, 0)
            """,
            (session_id, now),
        )
        self.conn.commit()
        return session_id

    def end_session(self, session_id=None, tasks_completed=None):
        """
        Record session end.  If *session_id* is None the most recent open
        session (no end_time) is closed.

        Returns the closed session row as a dict, or None.
        """
        now = int(time.time())

        if session_id is None:
            row = self.conn.execute(
                "SELECT session_id FROM sessions WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            session_id = row["session_id"]

        tasks_json = json.dumps(tasks_completed) if tasks_completed else None
        self.conn.execute(
            """
            UPDATE sessions
            SET end_time = ?, tasks_completed = ?
            WHERE session_id = ?
            """,
            (now, tasks_json, session_id),
        )
        self.conn.commit()

        return self._get_session(session_id)

    def get_active_session(self):
        """Return the most recent open session, or None."""
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def _get_session(self, session_id):
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Statistics / reporting
    # ------------------------------------------------------------------

    def get_stats(self):
        """
        Return a dict of aggregate statistics across the database.
        """
        files_count = self._scalar("SELECT COUNT(*) FROM files_read")
        total_tokens = self._scalar("SELECT COALESCE(SUM(token_cost), 0) FROM files_read")
        total_size = self._scalar("SELECT COALESCE(SUM(file_size), 0) FROM files_read")

        session_count = self._scalar("SELECT COUNT(*) FROM sessions")
        open_sessions = self._scalar("SELECT COUNT(*) FROM sessions WHERE end_time IS NULL")

        # Top 10 most expensive files by token cost
        top_expensive = self.conn.execute(
            """
            SELECT file_path, token_cost, file_size, last_read_ts
            FROM files_read
            ORDER BY token_cost DESC
            LIMIT 10
            """
        ).fetchall()

        return {
            "files_tracked": files_count,
            "total_token_cost": total_tokens,
            "total_file_size_bytes": total_size,
            "session_count": session_count,
            "open_sessions": open_sessions,
            "top_expensive_files": [dict(r) for r in top_expensive],
        }

    def get_recent_sessions(self, limit=10):
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def reset(self):
        """Clear all data (for testing / fresh start)."""
        self.conn.executescript("""
            DELETE FROM files_read;
            DELETE FROM sessions;
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_file(file_path):
        """SHA-256 content hash, reading in 8 KiB chunks."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError):
            return None

    @staticmethod
    def _freshness_label(ts):
        """Human-friendly 'read X ago' string."""
        delta = int(time.time()) - ts
        if delta < 60:
            return f"read {delta}s ago"
        elif delta < 3600:
            return f"read {delta // 60}m ago"
        elif delta < 86400:
            return f"read {delta // 3600}h ago"
        else:
            return f"read {delta // 86400}d ago"

    def _scalar(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()[0]


# ---------------------------------------------------------------------------
# CLI interface
# ---------------------------------------------------------------------------

def _fmt_bytes(n):
    """Format byte count to human-readable string."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


def _fmt_tokens(n):
    """Format token count with thousands separators."""
    return f"{n:,}"


def _fmt_ts(ts):
    """Format unix timestamp to readable datetime."""
    if ts is None:
        return "(none)"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def cli_check(db, args):
    """check <file_path> -- report FRESH / STALE / UNREAD."""
    if not args:
        print("Usage: python context_db.py check <file_path>")
        sys.exit(1)

    file_path = args[0]
    should_read, status, detail = db.should_reread_file(file_path)

    if status == "UNREAD":
        print(f"UNREAD - {detail}")
    elif status == "STALE":
        print(f"STALE (modified since last read)")
        info = db.get_file_info(file_path)
        if info:
            print(f"  Previous read: {_fmt_ts(info['last_read_ts'])}")
            print(f"  Token cost:    {_fmt_tokens(info['token_cost'])}")
    else:
        # FRESH
        print(f"FRESH ({detail})")
        info = db.get_file_info(file_path)
        if info:
            print(f"  Last read:   {_fmt_ts(info['last_read_ts'])}")
            print(f"  Token cost:  {_fmt_tokens(info['token_cost'])}")
            print(f"  File size:   {_fmt_bytes(info['file_size'])}")


def cli_stats(db, args):
    """stats -- show aggregate statistics."""
    stats = db.get_stats()

    print("Context Database Statistics")
    print("=" * 50)
    print(f"  Files tracked:       {stats['files_tracked']}")
    print(f"  Total token cost:    {_fmt_tokens(stats['total_token_cost'])}")
    print(f"  Total file size:     {_fmt_bytes(stats['total_file_size_bytes'])}")
    print(f"  Sessions recorded:   {stats['session_count']}")
    print(f"  Open sessions:       {stats['open_sessions']}")
    print()

    # Token savings estimate: if every tracked file were re-read in a new
    # session, this is how many tokens that would cost.  By checking freshness
    # first, you can skip unchanged files and save those tokens.
    if stats["total_token_cost"] > 0:
        print(f"  Tokens saved by skipping fresh files: up to {_fmt_tokens(stats['total_token_cost'])}")
    print()

    top = stats["top_expensive_files"]
    if top:
        print("Top expensive files (by token cost):")
        print("-" * 50)
        for i, f in enumerate(top, 1):
            name = f["file_path"]
            # Shorten home directory for readability
            home = str(Path.home())
            if name.startswith(home):
                name = "~" + name[len(home):]
            print(f"  {i:>2}. {_fmt_tokens(f['token_cost']):>10} tokens  {_fmt_bytes(f['file_size']):>10}  {name}")
    print()

    # Recent sessions summary
    sessions = db.get_recent_sessions(5)
    if sessions:
        print("Recent sessions:")
        print("-" * 50)
        for s in sessions:
            sid = s["session_id"]
            start = _fmt_ts(s["start_time"])
            end = _fmt_ts(s["end_time"]) if s["end_time"] else "(active)"
            duration = ""
            if s["end_time"] and s["start_time"]:
                dur_secs = s["end_time"] - s["start_time"]
                dur_mins = dur_secs // 60
                duration = f" ({dur_mins}m)" if dur_mins > 0 else f" ({dur_secs}s)"
            tasks = ""
            if s["tasks_completed"]:
                try:
                    t = json.loads(s["tasks_completed"])
                    if isinstance(t, list):
                        tasks = f"  tasks: {', '.join(t)}"
                except (json.JSONDecodeError, TypeError):
                    tasks = f"  tasks: {s['tasks_completed']}"
            print(f"  {sid}  {start} -> {end}{duration}{tasks}")


def cli_session(db, args):
    """session start | session end [--tasks t1,t2]"""
    if not args:
        print("Usage:")
        print("  python context_db.py session start")
        print("  python context_db.py session end [--tasks 'task1,task2']")
        sys.exit(1)

    sub = args[0]

    if sub == "start":
        # Check if there is already an open session
        active = db.get_active_session()
        if active:
            print(f"Warning: session '{active['session_id']}' is still open (started {_fmt_ts(active['start_time'])})")
            print("Closing it now before starting a new one.")
            db.end_session(active["session_id"])

        sid = db.start_session()
        print(f"Session started: {sid}")
        print(f"  Start time: {_fmt_ts(int(time.time()))}")

    elif sub == "end":
        tasks = None
        if "--tasks" in args:
            idx = args.index("--tasks")
            if idx + 1 < len(args):
                tasks = [t.strip() for t in args[idx + 1].split(",") if t.strip()]

        active = db.get_active_session()
        if not active:
            print("No active session to end.")
            sys.exit(1)

        result = db.end_session(tasks_completed=tasks)
        if result:
            duration_secs = (result["end_time"] or 0) - (result["start_time"] or 0)
            duration_mins = duration_secs // 60
            print(f"Session ended: {result['session_id']}")
            print(f"  Start:    {_fmt_ts(result['start_time'])}")
            print(f"  End:      {_fmt_ts(result['end_time'])}")
            print(f"  Duration: {duration_mins}m {duration_secs % 60}s")
            if tasks:
                print(f"  Tasks:    {', '.join(tasks)}")

            # Show files read during this session window
            files_in_session = db.conn.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(token_cost), 0)
                FROM files_read
                WHERE last_read_ts BETWEEN ? AND ?
                """,
                (result["start_time"], result["end_time"]),
            ).fetchone()
            print(f"  Files read in session: {files_in_session[0]}")
            print(f"  Token cost:            {_fmt_tokens(files_in_session[1])}")
    else:
        print(f"Unknown session subcommand: {sub}")
        print("Use: session start | session end")
        sys.exit(1)


def cli_mark(db, args):
    """mark <file_path> [--tokens N] -- record a file read."""
    if not args:
        print("Usage: python context_db.py mark <file_path> [--tokens N]")
        sys.exit(1)

    file_path = args[0]
    token_cost = None

    if "--tokens" in args:
        idx = args.index("--tokens")
        if idx + 1 < len(args):
            try:
                token_cost = int(args[idx + 1])
            except ValueError:
                print(f"Invalid token count: {args[idx + 1]}")
                sys.exit(1)

    path = Path(file_path).resolve()
    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    db.mark_file_read(str(path), token_cost=token_cost)
    info = db.get_file_info(str(path))
    print(f"Marked as read: {path}")
    if info:
        print(f"  Token cost:    {_fmt_tokens(info['token_cost'])}")
        print(f"  File size:     {_fmt_bytes(info['file_size'])}")
        print(f"  Content hash:  {info['content_hash'][:16]}...")


def cli_reset(db, args):
    """reset -- clear all data (requires confirmation)."""
    # Allow --yes flag to skip prompt (for scripting)
    if "--yes" in args:
        db.reset()
        print("Database reset complete.")
        return

    try:
        confirm = input("Reset all context data? This cannot be undone. (yes/no): ")
    except EOFError:
        print("Cancelled.")
        return

    if confirm.strip().lower() == "yes":
        db.reset()
        print("Database reset complete.")
    else:
        print("Cancelled.")


COMMANDS = {
    "check":   (cli_check,   "check <file>              Check if file needs re-reading"),
    "stats":   (cli_stats,   "stats                     Show database statistics"),
    "session": (cli_session, "session start|end [opts]   Manage sessions"),
    "mark":    (cli_mark,    "mark <file> [--tokens N]   Record a file read"),
    "reset":   (cli_reset,   "reset [--yes]              Clear all data"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("context_db.py -- Context Memory Database for Claude Code")
        print()
        print("Usage: python context_db.py <command> [args...]")
        print()
        print("Commands:")
        for _, (_, helptext) in COMMANDS.items():
            print(f"  {helptext}")
        print()
        print(f"Database location: ~/.claude/context.db")
        sys.exit(0)

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command not in COMMANDS:
        print(f"Unknown command: {command}")
        print(f"Run 'python context_db.py help' for usage.")
        sys.exit(1)

    db = ContextDB()
    try:
        handler, _ = COMMANDS[command]
        handler(db, rest)
    finally:
        db.close()


if __name__ == "__main__":
    main()
