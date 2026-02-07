#!/usr/bin/env python3
"""Fixed Unified Dashboard - Live Updating, No Infinite Scroll

ISSUES FIXED:
1. Infinite scroll - Using Rich Live for proper refresh
2. Shows stopped processes with investigation
3. All scraping jobs enumerated with code status
4. Knowledge base counting fixed
5. Packaged for easy access (run script)

Usage: python3 dashboard_fixed.py
"""

import os
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
from rich.columns import Columns
import time

# Paths
RESOURCE_TRACKER = Path.home() / ".claude/.locks/.resource-tracker.json"
SCRAPING_QUEUE = Path.home() / "Documents/Obsidian/SCRAPING-QUEUE.md"

# Subscription model
SUBSCRIPTION_COST = 200.00
THROTTLE_WARNING_THRESHOLD = 50

console = Console()


def load_tracker_data():
    """Load resource tracking data"""
    if not RESOURCE_TRACKER.exists():
        return {"sessions": {}, "daily": {}}
    try:
        return json.loads(RESOURCE_TRACKER.read_text())
    except Exception:
        return {"sessions": {}, "daily": {}}


def get_knowledge_base_stats():
    """Count articles across all knowledge bases - FIXED"""
    dev_dir = Path.home() / "Development"

    # All possible knowledge base locations
    sources = {
        # Existing (old structure)
        "cherie-hu-blog": "articles",
        "lenny-newsletter": "articles",
        "chatprd-blog": "articles",
        "jesse-cannon-blog": "articles",
        "indie-trinity": "articles",

        # New (raw structure)
        "obsidian-docs": "raw",
        "notion-docs": "raw",
        "claude-docs": "raw",
        "claude-code-docs": "raw",
        "don-norman-jnd": "raw",
        "don-norman-nngroup": "raw",
    }

    stats = {}
    total = 0

    for source, subdir in sources.items():
        source_path = dev_dir / source / subdir

        if source_path.exists():
            count = len(list(source_path.glob("*.md")))
            if count > 0:
                stats[source] = count
                total += count

    return stats, total


def check_launchd_services():
    """Check PopChaos launchd services - IMPROVED"""
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
                    exit_code = parts[1]
                    name = parts[2]

                    running = pid != "-"

                    # Determine status with more detail
                    if running:
                        status = "🟢 Running"
                        detail = f"PID {pid}"
                    elif exit_code != "0":
                        status = "🔴 Crashed"
                        detail = f"Exit {exit_code}"
                    else:
                        status = "🟡 Stopped"
                        detail = "Not running"

                    services.append({
                        "name": name.replace("com.popchaos.", ""),
                        "status": status,
                        "detail": detail,
                        "running": running
                    })

        return services
    except Exception as e:
        return [{"name": "Error", "status": "❌ Failed", "detail": str(e), "running": False}]


def enumerate_scraping_jobs():
    """Enumerate ALL scraping jobs - active, queued, completed"""

    jobs = {
        "active": [],
        "queued": [],
        "completed": [],
        "code_status": {}
    }

    # Check for active scraping processes
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        for line in result.stdout.split("\n"):
            if "python" in line and "scrape" in line:
                # Extract scraper name
                if "scrape_obsidian" in line:
                    jobs["active"].append({
                        "name": "Obsidian Docs",
                        "script": "scrape_obsidian.py",
                        "pid": line.split()[1]
                    })
                elif "scrape_all" in line:
                    jobs["active"].append({
                        "name": "Scrape All",
                        "script": "scrape-all.sh",
                        "pid": line.split()[1]
                    })
                elif "knowledge_scraper" in line:
                    jobs["active"].append({
                        "name": "Knowledge Scraper",
                        "script": "knowledge_scraper.py",
                        "pid": line.split()[1]
                    })
    except Exception:
        pass

    # Check scraping queue file
    if SCRAPING_QUEUE.exists():
        content = SCRAPING_QUEUE.read_text()

        # Parse queue status
        for line in content.split("\n"):
            if "| Queued |" in line:
                # Extract source name
                parts = line.split("|")
                if len(parts) >= 2:
                    source = parts[1].strip()
                    if source and source != "Source":
                        jobs["queued"].append(source)
            elif "| Completed ✅ |" in line:
                parts = line.split("|")
                if len(parts) >= 2:
                    source = parts[1].strip()
                    if source and source != "Source":
                        jobs["completed"].append(source)

    # Check code status
    scrapers = [
        "knowledge_scraper.py",
        "scrape_obsidian.py",
        "scraper.py",
        "plugin_doc_scraper.py"
    ]

    for scraper in scrapers:
        path = Path.home() / "Development" / "tools" / scraper
        if path.exists():
            # Check if it has security fixes
            content = path.read_text()
            has_security_fix = "os.path.basename" in content and "replace('..', '')" in content

            jobs["code_status"][scraper] = {
                "exists": True,
                "security_fixed": has_security_fix,
                "last_modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            }

    return jobs


def render_scraping_jobs_panel(jobs):
    """Render detailed scraping jobs panel"""
    text = Text()

    # Active jobs
    text.append("🔄 ACTIVE JOBS:\n", style="bold yellow")
    if jobs["active"]:
        for job in jobs["active"]:
            text.append(f"  • {job['name']}\n", style="green")
            text.append(f"    Script: {job['script']}\n", style="dim")
            text.append(f"    PID: {job['pid']}\n\n", style="dim")
    else:
        text.append("  None running\n\n", style="dim")

    # Queued
    text.append("⏳ QUEUED:\n", style="bold cyan")
    if jobs["queued"]:
        for source in jobs["queued"][:5]:  # Show first 5
            text.append(f"  • {source}\n", style="cyan")
    else:
        text.append("  Queue empty\n", style="dim")

    if len(jobs["queued"]) > 5:
        text.append(f"  ... and {len(jobs['queued']) - 5} more\n", style="dim")

    text.append("\n")

    # Completed
    text.append("✅ COMPLETED:\n", style="bold green")
    if jobs["completed"]:
        text.append(f"  {len(jobs['completed'])} sources scraped\n", style="green")
    else:
        text.append("  None yet\n", style="dim")

    return Panel(text, title="[bold]🌐 SCRAPING JOBS[/bold]", border_style="green")


def render_code_status_panel(code_status):
    """Render scraper code status"""
    text = Text()

    text.append("SCRAPER CODE STATUS:\n\n", style="bold cyan")

    for script, status in code_status.items():
        if status["exists"]:
            # Security status
            if status["security_fixed"]:
                sec_icon = "🔒"
                sec_text = "Security patched"
                sec_style = "green"
            else:
                sec_icon = "⚠️"
                sec_text = "Needs security patch"
                sec_style = "yellow"

            text.append(f"{sec_icon} {script}\n", style="bold")
            text.append(f"  {sec_text}\n", style=sec_style)
            text.append(f"  Modified: {status['last_modified']}\n\n", style="dim")

    text.append("\n🔄 Backfill Status:\n", style="bold magenta")
    text.append("  Old scrapers → Still using old code\n", style="yellow")
    text.append("  New scrapers → Security patched\n", style="green")
    text.append("  Migration will update all\n", style="dim")

    return Panel(text, title="[bold]💻 CODE STATUS[/bold]", border_style="blue")


def render_services_panel(services):
    """Render launchd services with investigation"""
    text = Text()

    if services:
        for service in services:
            text.append(f"{service['status']}  {service['name']}\n", style="white")
            text.append(f"   {service['detail']}\n\n", style="dim")
    else:
        text.append("No PopChaos services found\n", style="dim")

    # Add investigation note for stopped services
    stopped = [s for s in services if not s["running"]]
    if stopped:
        text.append("\n⚠️ INVESTIGATION:\n", style="bold yellow")
        text.append("Stopped services may be:\n", style="dim")
        text.append("• Not started yet (normal)\n", style="dim")
        text.append("• Disabled intentionally\n", style="dim")
        text.append("• Failed to start (check logs)\n\n", style="dim")
        text.append("Check: launchctl list | grep popchaos\n", style="cyan")

    return Panel(text, title="[bold]⚙️ LAUNCHD SERVICES[/bold]", border_style="yellow")


def render_knowledge_base_panel(stats, total):
    """Render knowledge base statistics - FIXED"""
    text = Text()
    text.append(f"Total Articles: {total:,}\n\n", style="bold green")

    # Show all sources
    for source, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        source_name = source.replace("-", " ").title()
        text.append(f"  {source_name[:25]:<25} {count:>5,}\n", style="cyan")

    return Panel(text, title="[bold]📚 KNOWLEDGE BASE[/bold]", border_style="magenta")


def render_session_table(data):
    """Render last 20 sessions"""
    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))

    table.add_column("Session", width=10)
    table.add_column("Resp", justify="right", width=6)
    table.add_column("Trend", width=8)
    table.add_column("Status", width=10)

    sessions = data.get("sessions", {})
    session_items = sorted(sessions.items(), key=lambda x: x[1].get("last_updated", ""), reverse=True)[:20]

    for i, (session_id, session_data) in enumerate(session_items):
        resp_count = session_data.get("response_count", 0)

        # Trend
        if i < len(session_items) - 1:
            prev_count = session_items[i+1][1].get("response_count", 0)
            if resp_count > prev_count * 1.5:
                trend = "📈 High"
            elif resp_count < prev_count * 0.5:
                trend = "📉 Low"
            else:
                trend = "➡️ Norm"
        else:
            trend = "—"

        # Status
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
            session_id.replace("session-", "")[:8],
            str(resp_count),
            trend,
            status
        )

    return Panel(table, title="[bold cyan]📊 CLAUDE SESSIONS (Last 20)[/bold cyan]", border_style="cyan")


def render_usage_panel(data):
    """Render usage tracking"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_data = data.get("daily", {}).get(today, {})

    responses_today = today_data.get("responses", 0)
    throttle_pct = (responses_today / THROTTLE_WARNING_THRESHOLD) * 100

    if throttle_pct < 50:
        risk_level = "✅ Safe"
        risk_color = "green"
    elif throttle_pct < 80:
        risk_level = "⚠️ Moderate"
        risk_color = "yellow"
    else:
        risk_level = "🔴 High Risk"
        risk_color = "red"

    text = Text()
    text.append(f"Subscription: ${SUBSCRIPTION_COST:.0f}/mo\n", style="cyan")
    text.append(f"Today: {responses_today} responses\n\n", style="white")
    text.append(f"Throttle Risk: ", style="dim")
    text.append(f"{risk_level}\n", style=risk_color)
    text.append(f"Limit: {THROTTLE_WARNING_THRESHOLD}/day\n", style="dim")

    return Panel(text, title="[bold]💰 USAGE[/bold]", border_style="blue")


def get_system_memory():
    """Monitor system and Claude Code memory usage"""
    memory_stats = {}

    try:
        # Claude temp directory
        claude_temp = subprocess.run(
            ["du", "-sh", "/private/tmp/claude-501"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if claude_temp.returncode == 0:
            memory_stats["claude_temp"] = claude_temp.stdout.split()[0]
        else:
            memory_stats["claude_temp"] = "N/A"

        # Claude directory
        claude_dir = subprocess.run(
            ["du", "-sh", str(Path.home() / ".claude")],
            capture_output=True,
            text=True,
            timeout=5
        )
        if claude_dir.returncode == 0:
            memory_stats["claude_dir"] = claude_dir.stdout.split()[0]
        else:
            memory_stats["claude_dir"] = "N/A"

        # Terminal memory (ps aux)
        ps_result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )

        terminal_mem_mb = 0
        for line in ps_result.stdout.split("\n"):
            if "Terminal.app" in line and "grep" not in line:
                parts = line.split()
                if len(parts) > 5:
                    # Column 6 is RSS in KB on macOS
                    terminal_mem_mb = int(parts[5]) / 1024
                    break

        memory_stats["terminal_mb"] = round(terminal_mem_mb, 1)

        # Disk free
        df_result = subprocess.run(
            ["df", "-h", "/"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if df_result.returncode == 0:
            lines = df_result.stdout.split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    memory_stats["disk_free"] = parts[3]
                    memory_stats["disk_used_pct"] = parts[4]

    except Exception as e:
        memory_stats["error"] = str(e)

    return memory_stats


def render_memory_panel(memory_stats):
    """Render system memory monitoring panel"""
    text = Text()

    # Terminal memory with warning
    terminal_mb = memory_stats.get("terminal_mb", 0)
    if terminal_mb > 1000:  # > 1GB
        mem_icon = "🔴"
        mem_style = "red bold"
    elif terminal_mb > 500:  # > 500MB
        mem_icon = "⚠️"
        mem_style = "yellow"
    else:
        mem_icon = "✅"
        mem_style = "green"

    text.append(f"{mem_icon} Terminal: {terminal_mb} MB\n", style=mem_style)

    # Claude directories
    text.append(f"📁 Claude temp: {memory_stats.get('claude_temp', 'N/A')}\n", style="white")
    text.append(f"📁 Claude dir: {memory_stats.get('claude_dir', 'N/A')}\n", style="white")

    # Disk space with warning
    disk_used_pct = memory_stats.get("disk_used_pct", "0%")
    disk_pct_val = int(disk_used_pct.rstrip("%"))

    if disk_pct_val > 90:
        disk_icon = "🔴"
        disk_style = "red bold"
    elif disk_pct_val > 75:
        disk_icon = "⚠️"
        disk_style = "yellow"
    else:
        disk_icon = "✅"
        disk_style = "green"

    text.append(f"\n{disk_icon} Disk: {memory_stats.get('disk_free', 'N/A')} free ({disk_used_pct})\n", style=disk_style)

    # Error handling
    if "error" in memory_stats:
        text.append(f"\n❌ Error: {memory_stats['error']}\n", style="red dim")

    return Panel(text, title="[bold]💾 SYSTEM MEMORY[/bold]", border_style="red")


def generate_layout():
    """Generate dashboard layout"""
    data = load_tracker_data()
    stats, total = get_knowledge_base_stats()
    services = check_launchd_services()
    jobs = enumerate_scraping_jobs()
    memory_stats = get_system_memory()

    layout = Layout()

    layout.split_column(
        Layout(name="header", size=1),
        Layout(name="sessions", size=14),
        Layout(name="row1", size=12),
        Layout(name="row2", size=18),
        Layout(name="footer", size=1)
    )

    # Header
    header_text = Text()
    header_text.append("═══ CLAUDE CODE UNIFIED DASHBOARD ═══", style="bold cyan")
    header_text.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
    layout["header"].update(Panel(header_text, style="cyan"))

    # Sessions
    layout["sessions"].update(render_session_table(data))

    # Row 1: Usage + Memory + Scraping Jobs
    layout["row1"].split_row(
        Layout(render_usage_panel(data), name="usage"),
        Layout(render_memory_panel(memory_stats), name="memory"),
        Layout(render_scraping_jobs_panel(jobs), name="scraping")
    )

    # Row 2: Knowledge Base + Code Status + Services
    layout["row2"].split_row(
        Layout(render_knowledge_base_panel(stats, total), name="kb"),
        Layout(render_code_status_panel(jobs["code_status"]), name="code"),
        Layout(render_services_panel(services), name="services")
    )

    # Footer
    footer_text = Text()
    footer_text.append("Press Ctrl+C to exit", style="dim")
    footer_text.append(" | ", style="dim")
    footer_text.append("Updates every 5s", style="dim")
    layout["footer"].update(Panel(footer_text, style="dim"))

    return layout


def main():
    """Main dashboard with proper live updating"""
    try:
        with Live(generate_layout(), refresh_per_second=0.2, screen=True) as live:
            while True:
                time.sleep(5)
                live.update(generate_layout())
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]\n")


if __name__ == "__main__":
    main()
