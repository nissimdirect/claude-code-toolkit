#!/usr/bin/env python3
"""
Claude Background Tasks & System Status Dashboard
Displays running services, active tasks, and scraping status
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn

# Constants
RESOURCE_TRACKER = Path.home() / ".claude/.locks/.resource-tracker.json"
LOCKS_DIR = Path.home() / ".claude/.locks"

def load_tracker_data():
    """Load resource tracker JSON"""
    if not RESOURCE_TRACKER.exists():
        return {"sessions": {}, "daily": {}}

    try:
        return json.loads(RESOURCE_TRACKER.read_text())
    except Exception:
        return {"sessions": {}, "daily": {}}

def get_current_session_info(data):
    """Get current session info"""
    sessions = data.get("sessions", {})
    if not sessions:
        return "Unknown", 0, "0m"

    # Find most recent session
    current = max(sessions.items(), key=lambda x: x[1].get("last_response", 0))
    session_id = current[0].replace("session-", "")
    resp_count = current[1].get("response_count", 0)

    # Calculate uptime
    first_resp = current[1].get("first_response", time.time())
    uptime_seconds = time.time() - first_resp
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    # Response rate
    if uptime_seconds > 0:
        resp_per_hour = (resp_count / uptime_seconds) * 3600
    else:
        resp_per_hour = 0

    return session_id, resp_count, uptime_str, resp_per_hour

def check_launchd_services():
    """Check status of launchd services"""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )

        services = []
        for line in result.stdout.split("\n"):
            if "popchaos" in line.lower():
                parts = line.split()
                if len(parts) >= 3:
                    pid = parts[0]
                    status = parts[1]
                    name = parts[2]

                    running = pid != "-"
                    services.append({
                        "name": name.replace("com.popchaos.", ""),
                        "running": running,
                        "status": "Running" if running else "Stopped"
                    })

        return services
    except Exception:
        return []

def create_session_panel(data):
    """Create session status panel"""
    session_id, resp_count, uptime, resp_rate = get_current_session_info(data)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("", style="dim")
    table.add_column("", style="bold")

    table.add_row("Session:", session_id)
    table.add_row("Uptime:", uptime)
    table.add_row("Responses:", str(resp_count))
    table.add_row("Avg:", f"{resp_rate:.1f} resp/hr")

    return Panel(table, title="[bold]CLAUDE SYSTEM STATUS[/bold]", border_style="cyan")

def create_services_panel():
    """Create background services panel"""
    services = check_launchd_services()

    if not services:
        text = Text("No PopChaos services found", style="dim")
        return Panel(text, title="[bold]BACKGROUND SERVICES[/bold]", border_style="yellow")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("", style="bold")
    table.add_column("", style="dim")
    table.add_column("", style="dim")

    for service in services:
        icon = "✅" if service["running"] else "❌"
        status_style = "green" if service["running"] else "red"
        table.add_row(
            f"{icon} {service['name']}",
            Text(service['status'], style=status_style),
            "Last: --"  # TODO: Add last run time from logs
        )

    return Panel(table, title="[bold]BACKGROUND SERVICES[/bold]", border_style="green")

def create_tasks_panel():
    """Create active tasks panel"""
    # TODO: Read from task progress JSON when implemented
    # For now, show placeholder

    tasks = [
        {"id": 42, "name": "Don Norman corpus", "progress": 0.3},
        {"id": 43, "name": "Art critics corpus", "progress": 0.2},
        {"id": 37, "name": "Grant site scraping", "progress": 0.7},
    ]

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Progress", width=12)
    table.add_column("", width=8)
    table.add_column("Task")

    for task in tasks:
        progress_pct = int(task["progress"] * 100)
        bar_length = 10
        filled = int((progress_pct / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        table.add_row(
            f"#{task['id']}",
            f"[{bar}]",
            f"{progress_pct}%",
            task["name"]
        )

    return Panel(table, title="[bold]ACTIVE TASKS[/bold]", border_style="magenta")

def create_scraping_panel():
    """Create recent scraping status panel"""
    # Hardcoded for now - would read from scraping logs in production

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("", width=4)
    table.add_column("", style="bold")
    table.add_column("", justify="right", style="dim")
    table.add_column("", style="dim")

    table.add_row("✅", "Plugin docs", "29/30 companies", "COMPLETE")
    table.add_row("🔄", "Grant sites", "7/10 sites", "IN PROGRESS")
    table.add_row("⏸️", "Art critics", "0/7 critics", "QUEUED")

    return Panel(table, title="[bold]RECENT SCRAPING[/bold]", border_style="yellow")

def create_dashboard():
    """Create full dashboard layout"""
    data = load_tracker_data()

    layout = Layout()
    layout.split_column(
        Layout(create_session_panel(data), size=7),
        Layout(create_services_panel(), size=7),
        Layout(create_tasks_panel(), size=9),
        Layout(create_scraping_panel(), size=8)
    )

    return layout

def main():
    """Main dashboard loop"""
    console = Console()

    console.print("\n[bold cyan]Claude Background Tasks Dashboard[/bold cyan]")
    console.print("[dim]Refreshing every 5 seconds. Press Ctrl+C to exit.[/dim]\n")

    try:
        with Live(create_dashboard(), refresh_per_second=0.2, console=console) as live:
            while True:
                time.sleep(5)
                live.update(create_dashboard())
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard closed.[/dim]")

if __name__ == "__main__":
    main()
