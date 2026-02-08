#!/usr/bin/env python3
"""Unified Dashboard - Sessions, Tasks, Usage, Scraping Status

Combines all monitoring into one view:
- Active Claude Code sessions (last 20+)
- Background tasks and launchd services
- Resource usage (subscription-based, NOT token costs)
- Scraping queue progress
- System health
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
import time

# Paths
RESOURCE_TRACKER = Path.home() / ".claude/.locks/.resource-tracker.json"
SCRAPING_QUEUE = Path.home() / "Documents/Obsidian/SCRAPING-QUEUE.md"

# Subscription model
SUBSCRIPTION_COST = 200.00  # $200/month flat fee
THROTTLE_WARNING_THRESHOLD = 50  # Responses per day (estimated safe limit)

console = Console()


def load_tracker_data():
    """Load resource tracking data"""
    if not RESOURCE_TRACKER.exists():
        return {"sessions": {}, "daily": {}}
    try:
        return json.loads(RESOURCE_TRACKER.read_text())
    except Exception:
        return {"sessions": {}, "daily": {}}


def check_claude_sessions():
    """Find all active Claude Code sessions"""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        sessions = []
        for line in result.stdout.split("\n"):
            if "claude" in line.lower() and "node" in line.lower():
                parts = line.split()
                if len(parts) >= 11:
                    sessions.append({
                        "pid": parts[1],
                        "cpu": parts[2],
                        "mem": parts[3],
                        "command": " ".join(parts[10:])[:60]
                    })

        return sessions
    except Exception:
        return []


def check_launchd_services():
    """Check PopChaos launchd services"""
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
                    name = parts[2]
                    running = pid != "-"
                    services.append({
                        "name": name.replace("com.popchaos.", ""),
                        "running": running,
                        "status": "🟢 Running" if running else "🔴 Stopped"
                    })

        return services
    except Exception:
        return []


def check_scraping_status():
    """Check scraping queue progress"""
    if not SCRAPING_QUEUE.exists():
        return {}

    content = SCRAPING_QUEUE.read_text()

    # Count by status
    in_progress = content.count("| In Progress |")
    completed = content.count("| Completed ✅ |")
    queued = content.count("| Queued |")

    # Find active scraping processes
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        active_scrapers = []
        for line in result.stdout.split("\n"):
            if "scrape" in line.lower() and "python" in line.lower():
                if "obsidian" in line:
                    active_scrapers.append("Obsidian")
                elif "notion" in line:
                    active_scrapers.append("Notion")
                elif "claude" in line:
                    active_scrapers.append("Claude")

        return {
            "in_progress": in_progress,
            "completed": completed,
            "queued": queued,
            "active_scrapers": active_scrapers
        }
    except Exception:
        return {
            "in_progress": in_progress,
            "completed": completed,
            "queued": queued,
            "active_scrapers": []
        }


def get_knowledge_base_stats():
    """Count articles across all knowledge bases"""
    dev_dir = Path.home() / "Development"

    sources = [
        "cherie-hu-blog",
        "lenny-newsletter",
        "chatprd-blog",
        "jesse-cannon-blog",
        "indie-trinity",
        "obsidian-docs",
        "notion-docs",
        "claude-docs",
        "don-norman-jnd",
        "don-norman-nngroup"
    ]

    stats = {}
    total = 0

    for source in sources:
        source_path = dev_dir / source

        # Check both old (articles/) and new (raw/) locations
        articles_dir = source_path / "articles"
        raw_dir = source_path / "raw"

        count = 0
        if articles_dir.exists():
            count += len(list(articles_dir.glob("*.md")))
        if raw_dir.exists():
            count += len(list(raw_dir.glob("*.md")))

        if count > 0:
            stats[source] = count
            total += count

    return stats, total


def render_session_table(data):
    """Render last 20 sessions with trends"""
    table = Table(title="[bold cyan]📊 CLAUDE CODE SESSIONS (Last 20)[/bold cyan]", show_header=True, header_style="bold cyan")

    table.add_column("Session", style="dim", width=12)
    table.add_column("Responses", justify="right", width=10)
    table.add_column("Est. Usage", justify="right", width=12)
    table.add_column("Trend", width=8)
    table.add_column("Status", width=10)

    sessions = data.get("sessions", {})
    session_items = sorted(sessions.items(), key=lambda x: x[1].get("last_updated", ""), reverse=True)[:20]

    for i, (session_id, session_data) in enumerate(session_items):
        resp_count = session_data.get("response_count", 0)

        # Simple trend indicator
        if i < len(session_items) - 1:
            prev_count = session_items[i+1][1].get("response_count", 0)
            if resp_count > prev_count * 1.5:
                trend = "📈 High"
            elif resp_count < prev_count * 0.5:
                trend = "📉 Low"
            else:
                trend = "➡️ Normal"
        else:
            trend = "—"

        # Status based on recency
        last_updated = session_data.get("last_updated", "")
        try:
            last_time = datetime.fromisoformat(last_updated)
            now = datetime.now()
            age_hours = (now - last_time).total_seconds() / 3600

            if age_hours < 1:
                status = "🟢 Active"
            elif age_hours < 24:
                status = "🟡 Recent"
            else:
                status = "⚪ Old"
        except:
            status = "⚪ Unknown"

        table.add_row(
            session_id.replace("session-", "")[:10] + "...",
            str(resp_count),
            f"{resp_count * 3:.1f}K tok",
            trend,
            status
        )

    return table


def render_usage_panel(data):
    """Render usage tracking (subscription model)"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_data = data.get("daily", {}).get(today, {})

    responses_today = today_data.get("responses", 0)

    # Estimate weekly/monthly from today's data
    responses_week = responses_today * 7
    responses_month = responses_today * 30

    # Usage vs throttle risk
    throttle_pct = (responses_today / THROTTLE_WARNING_THRESHOLD) * 100

    if throttle_pct < 50:
        usage_color = "green"
        risk_level = "✅ Safe"
    elif throttle_pct < 80:
        usage_color = "yellow"
        risk_level = "⚠️ Moderate"
    else:
        usage_color = "red"
        risk_level = "🔴 High Risk"

    text = Text()
    text.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", style="cyan")
    text.append("   SUBSCRIPTION: Claude Code Pro\n", style="bold white")
    text.append(f"   Cost: ${SUBSCRIPTION_COST:.2f}/month (flat)\n", style="cyan")
    text.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n", style="cyan")

    text.append(f"Today:     {responses_today:>4} responses\n", style="white")
    text.append(f"This Week: {responses_week:>4} responses (est)\n", style="dim")
    text.append(f"This Month: {responses_month:>4} responses (est)\n\n", style="dim")

    text.append(f"Throttle Risk: ", style="dim")
    text.append(f"{risk_level} ({throttle_pct:.0f}%)\n", style=usage_color)
    text.append(f"Safe limit: {THROTTLE_WARNING_THRESHOLD} responses/day\n", style="dim")

    return Panel(text, title="[bold]💰 USAGE TRACKING[/bold]", border_style="blue")


def render_scraping_panel():
    """Render scraping queue status"""
    status = check_scraping_status()

    text = Text()
    text.append("Queue Status:\n\n", style="bold cyan")
    text.append(f"  ✅ Completed:    {status.get('completed', 0):>3}\n", style="green")
    text.append(f"  🔄 In Progress:  {status.get('in_progress', 0):>3}\n", style="yellow")
    text.append(f"  ⏳ Queued:       {status.get('queued', 0):>3}\n\n", style="dim")

    active = status.get('active_scrapers', [])
    if active:
        text.append("Active Scrapers:\n", style="bold")
        for scraper in active:
            text.append(f"  🔹 {scraper}\n", style="cyan")
    else:
        text.append("No active scrapers\n", style="dim")

    return Panel(text, title="[bold]🌐 SCRAPING STATUS[/bold]", border_style="green")


def render_knowledge_base_panel():
    """Render knowledge base statistics"""
    stats, total = get_knowledge_base_stats()

    text = Text()
    text.append(f"Total Articles: {total:,}\n\n", style="bold green")

    # Top 5 sources
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:5]
    for source, count in sorted_stats:
        source_name = source.replace("-", " ").title()
        text.append(f"  {source_name[:20]:<20} {count:>5}\n", style="cyan")

    return Panel(text, title="[bold]📚 KNOWLEDGE BASE[/bold]", border_style="magenta")


def render_services_panel():
    """Render launchd services"""
    services = check_launchd_services()

    text = Text()
    if services:
        for service in services:
            text.append(f"{service['status']}  {service['name']}\n", style="white")
    else:
        text.append("No PopChaos services found\n", style="dim")

    return Panel(text, title="[bold]⚙️ LAUNCHD SERVICES[/bold]", border_style="yellow")


def render_dashboard():
    """Render full dashboard"""
    data = load_tracker_data()

    console.clear()
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold white]           CLAUDE CODE UNIFIED DASHBOARD                    [/bold white]")
    console.print(f"[dim]           {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                                  [/dim]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════════════[/bold cyan]\n")

    # Top row: Sessions table (full width)
    console.print(render_session_table(data))
    console.print()

    # Second row: Usage and Scraping side by side
    from rich.columns import Columns
    console.print(Columns([render_usage_panel(data), render_scraping_panel()]))
    console.print()

    # Third row: Knowledge Base and Services
    console.print(Columns([render_knowledge_base_panel(), render_services_panel()]))

    console.print("\n[dim]Press Ctrl+C to exit | Refreshes every 5 seconds[/dim]\n")


def main():
    """Main dashboard loop"""
    try:
        while True:
            render_dashboard()
            time.sleep(5)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]\n")


if __name__ == "__main__":
    main()
