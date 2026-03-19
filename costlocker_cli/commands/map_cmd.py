from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from costlocker_cli.config import require_config, save_config
from costlocker_cli.services.costlocker import CostlockerClient

console = Console()


def map_command() -> None:
    config = require_config()

    client = CostlockerClient(config["costlocker_api_key"])

    console.print("\n[bold]Configure event -> project mappings[/bold]")
    console.print("Type the calendar event name and assign it to a Costlocker project.\n")

    with console.status("Fetching Costlocker projects..."):
        projects = client.get_projects()

    if not projects:
        console.print("[red]No projects found in Costlocker.[/red]")
        raise typer.Exit(1)

    table = Table(title="Available Costlocker Projects")
    table.add_column("#", style="dim")
    table.add_column("Budget Name", style="cyan")
    table.add_column("Activity Name", style="dim")
    table.add_column("Subtask Name", style="dim")
    table.add_column("Budget ID", style="dim")
    table.add_column("Activity ID", style="dim")
    table.add_column("Subtask ID", style="dim")
    for i, p in enumerate(projects):
        table.add_row(
            str(i + 1),
            p.budget_name,
            p.activity_name,
            p.subtask_name or "",
            str(p.budget_id),
            str(p.activity_id),
            str(p.subtask_id) if p.subtask_id else "",
        )
    console.print(table)

    event_name = typer.prompt("\nCalendar event name to map (can be regex pattern)")
    is_regex = typer.confirm("Is this a regex pattern?", default=False)
    project_idx = typer.prompt("Project number")
    project = projects[int(project_idx) - 1]
    prefix = typer.prompt("Add an optional prefix", default="")

    mappings = config.get("mappings", {})
    mappings[event_name] = {
        "budget_id": project.budget_id,
        "activity_id": project.activity_id,
        "subtask_id": project.subtask_id,
        "name": project.display_name,
        "is_regex": is_regex,
        "prefix": prefix,
    }
    config["mappings"] = mappings

    save_config(config)
    pattern_type = "regex pattern" if is_regex else "exact match"
    console.print(f"\nMapped '[cyan]{event_name}[/cyan]' ({pattern_type}) -> [yellow]{project.display_name}[/yellow]")
