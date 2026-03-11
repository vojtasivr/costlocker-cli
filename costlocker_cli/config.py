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


def save_config(config: Dict):
    """Save config to ~/.costlocker/config.json"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def setup_config():
    """Interactive setup wizard."""
    console.print("\n[bold]🔧 Costlocker CLI Setup[/bold]\n")

    existing = load_config() or {}

    console.print("[bold]Step 1: Costlocker API[/bold]")
    console.print("Get your API key from: https://new.costlocker.com/profile/api\n")

    api_key = typer.prompt(
        "Costlocker API key",
        default=existing.get("costlocker_api_key", ""),
        hide_input=True,
    )
    base_url = typer.prompt(
        "Costlocker API base URL",
        default=existing.get("costlocker_base_url", "https://api.costlocker.com/graphql"),
    )

    console.print("\n[bold]Step 2: Google Calendar[/bold]")
    console.print("To set up Google Calendar access:")
    console.print("  1. Go to https://console.cloud.google.com/")
    console.print("  2. Create a project and enable the Google Calendar API")
    console.print("  3. Create OAuth 2.0 credentials (Desktop app)")
    console.print(f"  4. Download credentials.json and save it to: [cyan]{Path.home() / '.costlocker' / 'google_credentials.json'}[/cyan]\n")

    credentials_path = Path.home() / ".costlocker" / "google_credentials.json"
    if credentials_path.exists():
        console.print("[green]✅ Google credentials file found.[/green]")
    else:
        console.print("[yellow]⚠️ Google credentials file not found yet. Add it before running sync.[/yellow]")

    config = {
        "costlocker_api_key": api_key,
        "costlocker_base_url": base_url,
        "mappings": existing.get("mappings", {}),
    }

    save_config(config)
    console.print(f"\n✅ Config saved to [cyan]{CONFIG_PATH}[/cyan]")
    console.print("\nNext steps:")
    console.print("  • Run [bold]costlocker map[/bold] to configure event → project mappings")
    console.print("  • Run [bold]costlocker sync[/bold] to sync today's events")
    console.print("  • Run [bold]costlocker sync --date 2025-02-28[/bold] to sync a specific date\n")
