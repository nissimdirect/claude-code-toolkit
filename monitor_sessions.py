#!/usr/bin/env python3
"""
Session Monitor - Track outputs across Claude Code sessions
Monitors all active and recent sessions for files created, tasks completed, errors
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

class SessionMonitor:
    def __init__(self, sessions_dir="~/.claude/projects/-Users-nissimagent"):
        self.sessions_dir = Path(sessions_dir).expanduser()
        self.current_session = None

    def list_sessions(self, limit=10):
        """List recent sessions by modification time"""
        session_files = list(self.sessions_dir.glob("*.jsonl"))
        session_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return session_files[:limit]

    def parse_session(self, session_file):
        """Parse a session JSONL file"""
        session_data = {
            'session_id': session_file.stem,
            'file_path': str(session_file),
            'size': session_file.stat().st_size,
            'modified': datetime.fromtimestamp(session_file.stat().st_mtime),
            'messages': [],
            'files_created': set(),
            'files_modified': set(),
            'tasks': [],
            'errors': [],
            'tools_used': defaultdict(int),
        }

        try:
            with open(session_file, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        self._process_entry(entry, session_data)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            session_data['parse_error'] = str(e)

        return session_data

    def _process_entry(self, entry, session_data):
        """Process a single JSONL entry"""
        # Track messages
        if 'role' in entry:
            session_data['messages'].append({
                'role': entry['role'],
                'timestamp': entry.get('timestamp'),
                'content_length': len(str(entry.get('content', '')))
            })

        # Track tool usage
        if entry.get('type') == 'tool_use':
            tool_name = entry.get('name', 'unknown')
            session_data['tools_used'][tool_name] += 1

            # Extract file operations
            if tool_name == 'Write':
                file_path = entry.get('input', {}).get('file_path')
                if file_path:
                    session_data['files_created'].add(file_path)

            elif tool_name == 'Edit':
                file_path = entry.get('input', {}).get('file_path')
                if file_path:
                    session_data['files_modified'].add(file_path)

        # Track tool results for errors
        if entry.get('type') == 'tool_result':
            if entry.get('is_error'):
                error_content = entry.get('content', '')
                session_data['errors'].append({
                    'tool': entry.get('tool_use_id', 'unknown'),
                    'error': str(error_content)[:200]  # Truncate
                })

        # Track task operations
        if entry.get('type') == 'tool_use' and entry.get('name') in ['TaskCreate', 'TaskUpdate']:
            task_input = entry.get('input', {})
            session_data['tasks'].append({
                'action': entry.get('name'),
                'task_id': task_input.get('taskId'),
                'status': task_input.get('status'),
                'subject': task_input.get('subject')
            })

    def get_active_sessions(self):
        """Find sessions modified in last 24 hours"""
        now = datetime.now()
        active = []

        for session_file in self.list_sessions(limit=20):
            mod_time = datetime.fromtimestamp(session_file.stat().st_mtime)
            hours_ago = (now - mod_time).total_seconds() / 3600

            if hours_ago < 24:
                active.append(session_file)

        return active

    def compare_sessions(self, session_ids=None):
        """Compare multiple sessions to find overlapping work"""
        if session_ids is None:
            session_files = self.get_active_sessions()
        else:
            session_files = [self.sessions_dir / f"{sid}.jsonl" for sid in session_ids]

        comparison = {
            'sessions': [],
            'shared_files': set(),
            'file_conflicts': [],
            'total_files_created': 0,
            'total_tasks': 0,
        }

        all_files = defaultdict(list)

        for session_file in session_files:
            if not session_file.exists():
                continue

            session_data = self.parse_session(session_file)
            comparison['sessions'].append({
                'id': session_data['session_id'][:8],
                'modified': session_data['modified'].strftime('%Y-%m-%d %H:%M'),
                'messages': len(session_data['messages']),
                'files': len(session_data['files_created']) + len(session_data['files_modified']),
                'tasks': len(session_data['tasks']),
                'tools': dict(session_data['tools_used'])
            })

            comparison['total_tasks'] += len(session_data['tasks'])

            # Track files across sessions
            for file_path in session_data['files_created']:
                all_files[file_path].append(session_data['session_id'][:8])
                comparison['total_files_created'] += 1

        # Find shared/conflicting files
        for file_path, session_ids in all_files.items():
            if len(session_ids) > 1:
                comparison['shared_files'].add(file_path)
                comparison['file_conflicts'].append({
                    'file': file_path,
                    'sessions': session_ids
                })

        return comparison

    def generate_report(self, output_file=None):
        """Generate markdown report of all sessions"""
        active_sessions = self.get_active_sessions()

        report = "# Claude Code Session Monitor\n\n"
        report += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"**Active Sessions (24h):** {len(active_sessions)}\n\n"
        report += "---\n\n"

        # Summary comparison
        comparison = self.compare_sessions()

        report += "## Session Comparison\n\n"
        report += "| Session | Modified | Messages | Files | Tasks | Top Tools |\n"
        report += "|---------|----------|----------|-------|-------|----------|\n"

        for session in comparison['sessions']:
            top_tools = ', '.join(
                f"{k}({v})" for k, v in sorted(
                    session['tools'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]
            )
            report += f"| {session['id']}... | {session['modified']} | {session['messages']} | {session['files']} | {session['tasks']} | {top_tools} |\n"

        report += f"\n**Total Files Created:** {comparison['total_files_created']}\n"
        report += f"**Total Tasks:** {comparison['total_tasks']}\n\n"

        # File conflicts
        if comparison['file_conflicts']:
            report += "## ⚠️ File Conflicts (Modified in Multiple Sessions)\n\n"
            for conflict in comparison['file_conflicts'][:10]:
                report += f"- `{conflict['file']}`\n"
                report += f"  - Sessions: {', '.join(conflict['sessions'])}\n"

        # Detailed session reports
        report += "\n## Detailed Session Reports\n\n"

        for session_file in active_sessions[:5]:  # Top 5 most recent
            session_data = self.parse_session(session_file)

            report += f"### Session: {session_data['session_id'][:16]}...\n\n"
            report += f"**Modified:** {session_data['modified'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            report += f"**Size:** {session_data['size'] / 1024:.1f} KB\n"
            report += f"**Messages:** {len(session_data['messages'])}\n\n"

            if session_data['files_created']:
                report += "**Files Created:**\n"
                for file in list(session_data['files_created'])[:10]:
                    report += f"- `{file}`\n"
                report += "\n"

            if session_data['tasks']:
                report += "**Tasks:**\n"
                for task in session_data['tasks'][:5]:
                    report += f"- {task['action']}: #{task.get('task_id', '?')} - {task.get('subject', 'N/A')}\n"
                report += "\n"

            if session_data['errors']:
                report += "**Errors:**\n"
                for error in session_data['errors'][:3]:
                    report += f"- {error['error'][:100]}...\n"
                report += "\n"

            report += "---\n\n"

        # Save report
        if output_file:
            output_path = Path(output_file).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report)
            return output_path

        return report


def main():
    import sys

    monitor = SessionMonitor()

    if len(sys.argv) < 2:
        print("Usage: python monitor_sessions.py [command]")
        print("\nCommands:")
        print("  list           - List recent sessions")
        print("  active         - Show active sessions (24h)")
        print("  compare        - Compare active sessions")
        print("  report [file]  - Generate full report")
        print("  watch          - Watch for new session activity")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'list':
        sessions = monitor.list_sessions(limit=10)
        print(f"\n📋 Recent Sessions:\n")
        for session in sessions:
            mod_time = datetime.fromtimestamp(session.stat().st_mtime)
            print(f"  {session.stem[:16]}... - {mod_time.strftime('%Y-%m-%d %H:%M')}")

    elif command == 'active':
        active = monitor.get_active_sessions()
        print(f"\n⚡ Active Sessions (last 24h): {len(active)}\n")
        for session in active:
            session_data = monitor.parse_session(session)
            print(f"  {session_data['session_id'][:16]}...")
            print(f"    Modified: {session_data['modified'].strftime('%Y-%m-%d %H:%M')}")
            print(f"    Files: {len(session_data['files_created'])} created")
            print(f"    Tasks: {len(session_data['tasks'])}")
            print()

    elif command == 'compare':
        comparison = monitor.compare_sessions()
        print(f"\n🔄 Session Comparison:\n")
        print(f"Sessions analyzed: {len(comparison['sessions'])}")
        print(f"Total files created: {comparison['total_files_created']}")
        print(f"Total tasks: {comparison['total_tasks']}")

        if comparison['file_conflicts']:
            print(f"\n⚠️  File conflicts: {len(comparison['file_conflicts'])}")
            for conflict in comparison['file_conflicts'][:5]:
                print(f"  - {conflict['file']}")
                print(f"    Sessions: {', '.join(conflict['sessions'])}")

    elif command == 'report':
        output_file = sys.argv[2] if len(sys.argv) > 2 else "~/Documents/Obsidian/SESSION-MONITOR-REPORT.md"
        output_path = monitor.generate_report(output_file)
        print(f"✅ Report saved to: {output_path}")

    elif command == 'watch':
        print("👀 Watching for session activity... (Ctrl+C to stop)\n")
        import time
        last_check = set()

        while True:
            active = monitor.get_active_sessions()
            current = {s.stem for s in active}

            new_sessions = current - last_check
            if new_sessions:
                print(f"🆕 New activity detected:")
                for sid in new_sessions:
                    print(f"   - {sid[:16]}...")

            last_check = current
            time.sleep(30)  # Check every 30 seconds

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
