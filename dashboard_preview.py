#!/usr/bin/env python3
"""Show one frame of dashboard output for preview"""

import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

RESOURCE_TRACKER = Path.home() / ".claude/.locks/.resource-tracker.json"

def load_tracker_data():
    if not RESOURCE_TRACKER.exists():
        return {"sessions": {}, "daily": {}}
    try:
        return json.loads(RESOURCE_TRACKER.read_text())
    except Exception:
        return {"sessions": {}, "daily": {}}

console = Console()
data = load_tracker_data()

# Resource Usage Panel
console.print("\n[bold cyan]═══ RESOURCE USAGE DASHBOARD ═══[/bold cyan]\n")

table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
table.add_column("TODAY", style="green")
table.add_column("WEEK", style="yellow")
table.add_column("MONTH", style="magenta")
table.add_column("BUDGET", style="cyan")

# Calculate stats
today_data = data.get("daily", {}).get("2026-02-07", {})
responses_today = today_data.get("responses", 0)
cost_today = responses_today * 0.054
tokens_today = responses_today * 3000

cost_week = cost_today * 7
tokens_week = tokens_today * 7

cost_month = cost_today * 7  # Rough estimate
tokens_month = tokens_today * 7
budget_pct = (cost_month / 50.0) * 100
budget_bar = "█" * int(budget_pct / 5) + "░" * (20 - int(budget_pct / 5))

table.add_row(
    f"${cost_today:.2f}",
    f"${cost_week:.2f}",
    f"${cost_month:.2f}",
    f"$50.00"
)
table.add_row(
    f"{tokens_today/1000:.1f}K tokens",
    f"{tokens_week/1000:.1f}K tokens",
    f"{tokens_month/1000:.1f}K tokens",
    f"{budget_bar} {budget_pct:.0f}%"
)

console.print(Panel(table, title="[bold]RESOURCE USAGE[/bold]", border_style="blue"))

# Sessions
console.print("\n[bold cyan]═══ SESSION BREAKDOWN ═══[/bold cyan]\n")

table = Table(show_header=True, header_style="bold cyan")
table.add_column("Session", style="dim")
table.add_column("Responses", justify="right")
table.add_column("Est. Tokens", justify="right")
table.add_column("Est. Cost", justify="right")

sessions = data.get("sessions", {})
for session_id, session_data in list(sessions.items())[-4:]:
    resp_count = session_data.get("response_count", 0)
    tokens = resp_count * 3000
    cost = resp_count * 0.054

    table.add_row(
        session_id.replace("session-", ""),
        str(resp_count),
        f"{tokens/1000:.1f}K",
        f"${cost:.2f}"
    )

console.print(table)

# Carbon
console.print("\n[bold cyan]═══ ENVIRONMENTAL IMPACT ═══[/bold cyan]\n")

carbon_today = (tokens_today / 1000) * 0.036
carbon_month = (tokens_month / 1000) * 0.036

text = Text()
text.append(f"Carbon footprint (today):    ", style="dim")
text.append(f"{carbon_today:.1f}g CO₂\n", style="yellow")
text.append(f"Carbon footprint (month):    ", style="dim")
text.append(f"{carbon_month:.1f}g CO₂\n\n", style="yellow")
text.append(f"Equivalent to:\n", style="dim")
text.append(f"🚗 {carbon_month/411:.3f} miles driven\n", style="green")
text.append(f"🌳 {carbon_month/21000:.5f} trees for offset", style="green")

console.print(Panel(text, border_style="yellow"))

console.print("\n[dim]Run 'python3 ~/Development/tools/dashboard_usage.py' for live updates[/dim]\n")
