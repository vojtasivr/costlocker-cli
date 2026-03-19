import json
from pathlib import Path
from typing import Optional, Dict
import typer
from rich.console import Console

CONFIG_PATH = Path.home() / ".costlocker" / "config.json"
console = Console()


def load_config() -> Optional[Dict]:
    """Load config from ~/.costlocker/config.json"""
    if not CONFIG_PATH.exists():
        return None
    with open(CONFIG_PATH) as f:
        return json.load(f)


def require_config() -> Dict:
    config = load_config()
    if not config:
        console.print("[red]No config found. Run `costlocker setup` first.[/red]")
        raise typer.Exit(1)
    return config


def save_config(config: Dict):
    """Save config to ~/.costlocker/config.json"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def _prompt_time(label: str, default: str) -> str:
    while True:
        value = typer.prompt(f"{label} (HH:MM)", default=default)
        try:
            h, m = value.split(":")
            if 0 <= int(h) <= 23 and 0 <= int(m) <= 59:
                return f"{int(h):02d}:{int(m):02d}"
        except ValueError:
            pass
        console.print(f"[red]Invalid time '{value}', expected HH:MM (e.g. 08:30)[/red]")


def setup_config():
    """Interactive setup wizard."""
    console.print("\n[bold]Costlocker CLI Setup[/bold]\n")

    existing = load_config() or {}

    console.print("[bold]Step 1: Costlocker API[/bold]")
    console.print("Get your API key from: https://new.costlocker.com/profile/api\n")

    api_key = typer.prompt(
        "Costlocker API key",
        default=existing.get("costlocker_api_key", ""),
        hide_input=True,
    )

    console.print("\n[bold]Step 2: Google Calendar[/bold]")
    console.print("To set up Google Calendar access:")
    console.print("  1. Go to https://console.cloud.google.com/")
    console.print("  2. Create a project and enable the Google Calendar API")
    console.print("  3. Create OAuth 2.0 credentials (Desktop app)")
    console.print(f"  4. Download credentials.json and save it to: [cyan]{Path.home() / '.costlocker' / 'google_credentials.json'}[/cyan]\n")

    credentials_path = Path.home() / ".costlocker" / "google_credentials.json"
    if credentials_path.exists():
        console.print("[green]Google credentials file found.[/green]")
    else:
        console.print("[yellow]Google credentials file not found yet. Add it before running sync.[/yellow]")

    console.print("\n[bold]Step 3: Work schedule[/bold]")
    existing_schedule = existing.get("schedule", {})
    work_start = _prompt_time("Work day start time", default=existing_schedule.get("work_start", "08:30"))
    work_end = _prompt_time("Work day end time", default=existing_schedule.get("work_end", "17:00"))
    lunch_start = _prompt_time("Lunch break start time", default=existing_schedule.get("lunch_start", "11:00"))

    console.print("\n[bold]Step 4: PagerDuty (optional)[/bold]")
    setup_pagerduty = typer.confirm("Set up PagerDuty on-call sync?", default=bool(existing.get("pagerduty")))

    existing_pd = existing.get("pagerduty", {})
    pagerduty: Optional[Dict] = None

    if setup_pagerduty:
        pd_api_key = typer.prompt("PagerDuty API key", default=existing_pd.get("api_key", ""), hide_input=True)
        schedule_ids_str = typer.prompt(
            "PagerDuty schedule IDs (comma-separated)",
            default=",".join(existing_pd.get("schedule_ids", [])),
        )
        schedule_ids = [s.strip() for s in schedule_ids_str.split(",") if s.strip()]

        user_id = existing_pd.get("user_id", "")
        if pd_api_key and not user_id:
            try:
                from costlocker_cli.services.pagerduty import PagerDutyClient
                with console.status("Fetching PagerDuty user..."):
                    user_id = PagerDutyClient(pd_api_key).get_current_user_id()
                console.print(f"[green]PagerDuty user ID: {user_id}[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not fetch PagerDuty user ID: {e}[/yellow]")

        pagerduty = {"api_key": pd_api_key, "user_id": user_id, "schedule_ids": schedule_ids}

    console.print("\n[bold]Step 5: Azure DevOps (optional)[/bold]")
    setup_ado = typer.confirm("Set up Azure DevOps sync?", default=bool(existing.get("azure_devops")))

    existing_ado = existing.get("azure_devops", {})
    azure_devops: Optional[Dict] = None

    if setup_ado:
        ado_pat = typer.prompt("Azure DevOps Personal Access Token", default=existing_ado.get("pat", ""), hide_input=True)
        ado_org = typer.prompt("Azure DevOps organization", default=existing_ado.get("organization", ""))
        ado_project = typer.prompt("Azure DevOps project", default=existing_ado.get("project", ""))

        ado_user_id = existing_ado.get("user_id", "")
        if ado_pat and ado_org and not ado_user_id:
            try:
                from costlocker_cli.services.azuredevops import AzureDevOpsClient
                with console.status("Fetching Azure DevOps user..."):
                    ado_user_id = AzureDevOpsClient(ado_pat, ado_org, ado_project).get_current_user_id()
                console.print(f"[green]Azure DevOps user ID: {ado_user_id}[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not fetch Azure DevOps user ID: {e}[/yellow]")

        azure_devops = {"pat": ado_pat, "organization": ado_org, "project": ado_project, "user_id": ado_user_id}

    config = {
        "costlocker_api_key": api_key,
        "schedule": {"work_start": work_start, "work_end": work_end, "lunch_start": lunch_start},
        "mappings": existing.get("mappings", {}),
    }
    if pagerduty:
        config["pagerduty"] = pagerduty
    if azure_devops:
        config["azure_devops"] = azure_devops

    save_config(config)
    console.print(f"\nConfig saved to [cyan]{CONFIG_PATH}[/cyan]")
    console.print("\nNext steps:")
    console.print("  • Run [bold]costlocker map[/bold] to configure event -> project mappings")
    console.print("  • Run [bold]costlocker sync[/bold] to sync today's events")
    console.print("  • Run [bold]costlocker sync --date 2025-02-28[/bold] to sync a specific date\n")
