from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from costlocker_cli.config import load_config
from costlocker_cli.mapper import EventMapper
from costlocker_cli.models import ScheduleEntry, TimeEntry
from costlocker_cli.services.calendar import get_calendar_events
from costlocker_cli.services.costlocker import CostlockerClient
from costlocker_cli.services.scheduler import prepare_schedule

console = Console()


def sync_command(date_str: Optional[str], dry_run: bool, interactive: bool) -> None:
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    console.print(f"\nSyncing events for [bold]{target_date}[/bold]\n")

    config = load_config()
    if not config:
        console.print("[red]No config found. Run `costlocker setup` first.[/red]")
        raise typer.Exit(1)

    with console.status("Fetching Google Calendar events..."):
        events = get_calendar_events(target_date)

    pd_config = config.get("pagerduty")
    if pd_config and pd_config.get("api_key") and pd_config.get("schedule_ids"):
        with console.status("Fetching PagerDuty on-call schedule..."):
            try:
                from costlocker_cli.services.pagerduty import PagerDutyClient
                pd_events = PagerDutyClient(pd_config["api_key"]).get_oncall_events(
                    target_date,
                    pd_config["schedule_ids"],
                    pd_config["user_id"],
                )
                events = events + pd_events
            except Exception as e:
                console.print(f"[yellow]PagerDuty fetch failed, skipping: {e}[/yellow]")

    if not events:
        console.print("No events found for this date.")
        raise typer.Exit(0)

    mapper = EventMapper(config.get("mappings", {}))
    entries = mapper.map(events)

    _print_entries_table(entries)

    if dry_run:
        console.print("\n[yellow]Dry run — nothing was logged.[/yellow]")
        raise typer.Exit(0)

    entries_to_log = entries
    if interactive:
        entries_to_log = [
            e for e in entries
            if typer.confirm(f"Log '{e.event_name}' ({e.duration_minutes}m) to {e.project_name or 'unmapped'}?")
        ]

    if not entries_to_log:
        console.print("[yellow]No entries to log.[/yellow]")
        raise typer.Exit(0)

    client = CostlockerClient(config["costlocker_api_key"])
    schedule_config = config.get("schedule", {})
    schedule = prepare_schedule(
        target_date,
        entries_to_log,
        work_start_time=schedule_config.get("work_start", "08:30"),
        work_end_time=schedule_config.get("work_end", "17:00"),
        lunch_start_time=schedule_config.get("lunch_start", "11:00"),
    )

    _print_schedule_table(schedule, target_date)

    if not typer.confirm("Post this schedule to Costlocker?"):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    with console.status("Logging to Costlocker..."):
        results = client.log_schedule(target_date, schedule)

    success = sum(1 for r in results if r["success"])
    console.print(f"\nLogged [bold]{success}/{len(schedule)}[/bold] entries to Costlocker.\n")

    for r in results:
        if not r["success"]:
            entry: ScheduleEntry = r["entry"]
            console.print(f"[red]Failed to log '{entry.event_name}' ({entry.duration_minutes}m)[/red]")
            if "errors" in r:
                for error in r["errors"]:
                    console.print(f"   [red]{error.get('message', error)}[/red]")
            elif "error" in r:
                console.print(f"   [red]{r['error']}[/red]")


def _print_entries_table(entries: list[TimeEntry]) -> None:
    table = Table(title="Events to log")
    table.add_column("Calendar Event", style="cyan")
    table.add_column("Duration", style="green")
    table.add_column("Costlocker Project", style="yellow")
    table.add_column("Status", style="white")
    for entry in entries:
        status = "mapped" if entry.budget_id else "unmapped"
        table.add_row(entry.event_name, f"{entry.duration_minutes}m", entry.project_name or "—", status)
    console.print(table)


def _print_schedule_table(schedule: list[ScheduleEntry], target_date: date) -> None:
    table = Table(title=f"Schedule for {target_date}")
    table.add_column("Time", style="cyan", no_wrap=True)
    table.add_column("Duration", style="magenta")
    table.add_column("Event", style="white")
    table.add_column("Project", style="green")
    for entry in schedule:
        start = datetime.fromisoformat(entry.calculated_start).strftime("%H:%M")
        end = datetime.fromisoformat(entry.calculated_end).strftime("%H:%M")
        event_name = "[dim](empty)[/dim]" if entry.is_empty else entry.event_name
        table.add_row(f"{start} - {end}", f"{entry.duration_minutes}m", event_name, entry.project_name or "-")
    console.print("\n")
    console.print(table)
    console.print("\n")
