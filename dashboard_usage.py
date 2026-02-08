#!/usr/bin/env python3
"""
Claude Usage & Environmental Impact Dashboard
Displays token usage, costs, and carbon footprint in real-time
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

# Constants
RESOURCE_TRACKER = Path.home() / ".claude/.locks/.resource-tracker.json"
SONNET_INPUT_COST = 3.0 / 1_000_000   # $3 per 1M tokens
SONNET_OUTPUT_COST = 15.0 / 1_000_000  # $15 per 1M tokens
AVG_TOKENS_PER_RESPONSE = 3000  # Conservative estimate
AVG_COST_PER_RESPONSE = 0.054  # Based on Sonnet pricing
CO2_PER_1K_TOKENS = 0.036  # grams of CO₂
MONTHLY_BUDGET = 50.00  # dollars

def load_tracker_data():
    """Load resource tracker JSON"""
    if not RESOURCE_TRACKER.exists():
        return {"sessions": {}, "daily": {}}

    try:
        return json.loads(RESOURCE_TRACKER.read_text())
    except Exception as e:
        return {"sessions": {}, "daily": {}}

def calculate_costs(response_count):
    """Calculate estimated tokens and cost"""
    tokens = response_count * AVG_TOKENS_PER_RESPONSE
    cost = response_count * AVG_COST_PER_RESPONSE
    return tokens, cost

def calculate_carbon(tokens):
    """Calculate carbon footprint in grams CO₂"""
    return (tokens / 1000) * CO2_PER_1K_TOKENS

def get_today_stats(data):
    """Get today's aggregated stats"""
    today = datetime.now().strftime("%Y-%m-%d")
    daily_data = data.get("daily", {}).get(today, {})
    responses = daily_data.get("responses", 0)
    tokens, cost = calculate_costs(responses)
    carbon = calculate_carbon(tokens)
    return responses, tokens, cost, carbon

def get_month_stats(data):
    """Get current month's stats (approximate)"""
    # Rough estimate: today's rate × days in month
    responses_today, _, _, _ = get_today_stats(data)
    day_of_month = datetime.now().day

    if day_of_month == 0:
        return 0, 0, 0, 0

    # Extrapolate
    responses_per_day = responses_today / 1  # Just today for now
    days_in_month = 30  # Approximate

    responses_month = responses_today * day_of_month  # Accumulated so far
    tokens_month, cost_month = calculate_costs(responses_month)
    carbon_month = calculate_carbon(tokens_month)

    return responses_month, tokens_month, cost_month, carbon_month

def create_usage_panel(data):
    """Create resource usage panel"""
    today_resp, today_tokens, today_cost, _ = get_today_stats(data)
    month_resp, month_tokens, month_cost, _ = get_month_stats(data)

    # Budget progress
    budget_pct = (month_cost / MONTHLY_BUDGET) * 100
    budget_bar_length = 20
    filled = int((budget_pct / 100) * budget_bar_length)
    budget_bar = "█" * filled + "░" * (budget_bar_length - filled)

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("TODAY", style="green")
    table.add_column("WEEK", style="yellow")
    table.add_column("MONTH", style="magenta")
    table.add_column("BUDGET", style="cyan")

    week_cost = today_cost * 7  # Rough estimate
    week_tokens = today_tokens * 7

    table.add_row(
        f"${today_cost:.2f}",
        f"${week_cost:.2f}",
        f"${month_cost:.2f}",
        f"${MONTHLY_BUDGET:.2f}"
    )
    table.add_row(
        f"{today_tokens/1000:.1f}K tokens",
        f"{week_tokens/1000:.1f}K tokens",
        f"{month_tokens/1000:.1f}K tokens",
        f"{budget_bar} {budget_pct:.0f}%"
    )

    return Panel(table, title="[bold]RESOURCE USAGE[/bold]", border_style="blue")

def create_session_panel(data):
    """Create session breakdown panel"""
    sessions = data.get("sessions", {})

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Session", style="dim")
    table.add_column("Responses", justify="right")
    table.add_column("Est. Tokens", justify="right")
    table.add_column("Est. Cost", justify="right")

    # Show last 5 sessions
    for session_id, session_data in list(sessions.items())[-5:]:
        resp_count = session_data.get("response_count", 0)
        tokens, cost = calculate_costs(resp_count)

        table.add_row(
            session_id.replace("session-", ""),
            str(resp_count),
            f"{tokens/1000:.1f}K",
            f"${cost:.2f}"
        )

    return Panel(table, title="[bold]SESSION BREAKDOWN[/bold]", border_style="green")

def create_carbon_panel(data):
    """Create environmental impact panel"""
    today_resp, today_tokens, _, today_carbon = get_today_stats(data)
    month_resp, month_tokens, _, month_carbon = get_month_stats(data)

    # Conversions
    miles_driven = month_carbon / 411  # 411g CO₂ per mile (avg car)
    trees_needed = month_carbon / 21000  # 21kg CO₂ per tree per year (rough)

    text = Text()
    text.append(f"Carbon footprint (today):    ", style="dim")
    text.append(f"{today_carbon:.1f}g CO₂\n", style="yellow")
    text.append(f"Carbon footprint (month):    ", style="dim")
    text.append(f"{month_carbon:.1f}g CO₂\n\n", style="yellow")
    text.append(f"Equivalent to:\n", style="dim")
    text.append(f"🚗 {miles_driven:.2f} miles driven\n", style="green")
    text.append(f"🌳 {trees_needed:.4f} trees needed for offset", style="green")

    return Panel(text, title="[bold]ENVIRONMENTAL IMPACT[/bold]", border_style="yellow")

def create_alerts_panel(data):
    """Create alerts panel"""
    today_resp, _, today_cost, _ = get_today_stats(data)
    month_resp, _, month_cost, _ = get_month_stats(data)

    alerts = []

    # Budget alerts
    budget_pct = (month_cost / MONTHLY_BUDGET) * 100
    if budget_pct > 80:
        alerts.append(("⚠️", f"High usage: {budget_pct:.0f}% of ${MONTHLY_BUDGET}/month budget", "red"))
    elif budget_pct > 60:
        alerts.append(("⚠️", f"Approaching budget ({budget_pct:.0f}% of ${MONTHLY_BUDGET}/month)", "yellow"))

    # Current session alerts
    current_session = max(data.get("sessions", {}).items(), key=lambda x: x[1].get("last_response", 0), default=(None, {}))[1]
    session_responses = current_session.get("response_count", 0)

    if session_responses > 50:
        alerts.append(("ℹ️", f"{session_responses} responses this session (consider /clear)", "cyan"))

    if not alerts:
        alerts.append(("✅", "All systems nominal", "green"))

    text = Text()
    for icon, message, style in alerts:
        text.append(f"{icon}  {message}\n", style=style)

    return Panel(text, title="[bold]ALERTS[/bold]", border_style="red")

def create_dashboard():
    """Create full dashboard layout"""
    data = load_tracker_data()

    layout = Layout()
    layout.split_column(
        Layout(create_usage_panel(data), size=7),
        Layout(create_session_panel(data), size=10),
        Layout(create_carbon_panel(data), size=10),
        Layout(create_alerts_panel(data), size=6)
    )

    return layout

def main():
    """Main dashboard loop"""
    console = Console()

    console.print("\n[bold cyan]Claude Usage & Environmental Dashboard[/bold cyan]")
    console.print("[dim]Refreshing every 10 seconds. Press Ctrl+C to exit.[/dim]\n")

    try:
        with Live(create_dashboard(), refresh_per_second=0.1, console=console) as live:
            while True:
                time.sleep(10)
                live.update(create_dashboard())
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard closed.[/dim]")

if __name__ == "__main__":
    main()
