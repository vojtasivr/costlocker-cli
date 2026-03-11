import typer
from datetime import date
from typing import Optional
from rich.console import Console
from rich.table import Table

from gcalendar import get_calendar_events
from costlocker import CostlockerClient
from mapper import EventMapper
from config import load_config, setup_config
from config import save_config

app = typer.Typer(help="Sync Google Calendar events to Costlocker timesheets", no_args_is_help=True)
console = Console()


@app.command()
def sync(
    date_str: Optional[str] = typer.Option(None, "--date", "-d", help="Date to sync (YYYY-MM-DD). Defaults to today."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be logged without actually logging it."),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactively confirm each event before logging."),
):
    """Fetch Google Calendar events and log them to Costlocker."""
    target_date = date.fromisoformat(date_str) if date_str else date.today()
    console.print(f"\nSyncing events for [bold]{target_date}[/bold]\n")

    config = load_config()
    if not config:
        console.print("[red]No config found. Run `costlocker setup` first.[/red]")
        raise typer.Exit(1)

    # Fetch calendar events
    with console.status("Fetching Google Calendar events..."):
        events = get_calendar_events(target_date)

    if not events:
        console.print("No events found for this date.")
        raise typer.Exit(0)

    # Map events to Costlocker entries
    mapper = EventMapper(config.get("mappings", {}))
    entries = mapper.map(events)

    # Show preview table
    table = Table(title="Events to log")
    table.add_column("Calendar Event", style="cyan")
    table.add_column("Duration", style="green")
    table.add_column("Costlocker Project", style="yellow")
    table.add_column("Status", style="white")

    for entry in entries:
        status = "mapped" if entry.get("budget_id") else "unmapped"
        table.add_row(
            entry["event_name"],
            f"{entry['duration_minutes']}m",
            entry.get("project_name", "—"),
            status,
        )

    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run — nothing was logged.[/yellow]")
        raise typer.Exit(0)

    # Interactive confirmation
    entries_to_log = entries
    if interactive:
        entries_to_log = [e for e in entries if typer.confirm(
            f"Log '{e['event_name']}' ({e['duration_minutes']}m) to {e.get('project_name', 'unmapped')}?"
        )]

    if not entries_to_log:
        console.print("[yellow]No entries to log.[/yellow]")
        raise typer.Exit(0)

    # Prepare schedule
    client = CostlockerClient(config["costlocker_api_key"], config["costlocker_base_url"])
    schedule = client.prepare_schedule(target_date, entries_to_log)

    # Pretty print schedule
    from datetime import datetime

    table = Table(title=f"Schedule for {target_date}")
    table.add_column("Time", style="cyan", no_wrap=True)
    table.add_column("Duration", style="magenta")
    table.add_column("Event", style="white")
    table.add_column("Project", style="green")

    for entry in schedule:
        start_time = datetime.fromisoformat(entry["calculated_start"]).strftime("%H:%M")
        end_time = datetime.fromisoformat(entry["calculated_end"]).strftime("%H:%M")
        duration = f"{entry['duration_minutes']}m"
        event_name = entry.get("event_name", "(empty)")
        project_name = entry.get("project_name", "-")

        if entry.get("is_empty"):
            event_name = "[dim](empty)[/dim]"

        table.add_row(f"{start_time} - {end_time}", duration, event_name, project_name)

    console.print("\n")
    console.print(table)
    console.print("\n")

    # Confirm before posting
    if not typer.confirm("Post this schedule to Costlocker?"):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)

    # Post to Costlocker
    with console.status("Logging to Costlocker..."):
        results = client.log_schedule(target_date, schedule)

    success = sum(1 for r in results if r["success"])
    console.print(f"\n✅ Logged [bold]{success}/{len(schedule)}[/bold] entries to Costlocker.\n")

    # Log errors
    for r in results:
        if not r["success"]:
            entry = r["entry"]
            console.print(f"[red]❌ Failed to log '{entry['event_name']}' ({entry['duration_minutes']}m)[/red]")
            if "errors" in r:
                for error in r["errors"]:
                    console.print(f"   [red]{error.get('message', error)}[/red]")
            elif "error" in r:
                console.print(f"   [red]{r['error']}[/red]")


@app.command()
def setup():
    """Interactive setup — configure API keys and calendar access."""
    setup_config()


@app.command()
def map():
    """Manage mappings between calendar event names and Costlocker projects."""
    config = load_config()
    if not config:
        console.print("[red]No config found. Run `costlocker setup` first.[/red]")
        raise typer.Exit(1)

    client = CostlockerClient(config["costlocker_api_key"], config["costlocker_base_url"])

    console.print("\n[bold]Configure event → project mappings[/bold]")
    console.print("Type the calendar event name and assign it to a Costlocker project.\n")

    with console.status("Fetching Costlocker projects..."):
        projects = client.get_projects()

    if not projects:
        console.print("[red]No projects found in Costlocker.[/red]")
        raise typer.Exit(1)

    # Show available projects
    table = Table(title="Available Costlocker Projects")
    table.add_column("#", style="dim")
    table.add_column("Budget Name", style="cyan")
    table.add_column("Activity Name", style="dim")
    table.add_column("Subtask Name", style="dim")
    table.add_column("Budget ID", style="dim")
    table.add_column("Activity ID", style="dim")
    table.add_column("Subtask ID", style="dim")
    for i, p in enumerate(projects):
        table.add_row(str(i + 1), p["budget_name"], p["activity_name"], p["subtask_name"],str(p["budget_id"]),str(p["activity_id"]), str(p["subtask_id"]))
    console.print(table)

    event_name = typer.prompt("\nCalendar event name to map (can be regex pattern)")
    is_regex = typer.confirm("Is this a regex pattern?", default=False)
    project_idx = typer.prompt("Project number")
    project = projects[int(project_idx) - 1]
    project_name = f"{project['budget_name']} - {project['activity_name']}"
    if project.get("subtask_name"):
        project_name += f" - {project['subtask_name']}"
    prefix = typer.prompt("Add an optional prefix")

    mappings = config.get("mappings", {})
    mappings[event_name] = {
        "budget_id": project["budget_id"],
        "activity_id": project["activity_id"],
        "subtask_id": project["subtask_id"],
        "name": project_name,
        "is_regex": is_regex,
        "prefix": prefix,
    }
    config["mappings"] = mappings

    save_config(config)
    pattern_type = "regex pattern" if is_regex else "exact match"
    console.print(f"\n✅ Mapped '[cyan]{event_name}[/cyan]' ({pattern_type}) → [yellow]{project_name}[/yellow]")


@app.command()
def list_mappings():
    """Show all configured event → project mappings."""
    config = load_config()
    mappings = config.get("mappings", {}) if config else {}

    if not mappings:
        console.print("No mappings configured yet. Run `costlocker map` to add some.")
        raise typer.Exit(0)

    table = Table(title="Configured Mappings")
    table.add_column("Calendar Event", style="cyan")
    table.add_column("Costlocker Project", style="yellow")
    for event, mapping in mappings.items():
        table.add_row(event, mapping.get("name", ""))
    console.print(table)


def main():
    app()

if __name__ == "__main__":
    main()