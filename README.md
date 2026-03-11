# costlocker-cli

A CLI tool to sync Google Calendar events to Costlocker timesheets.

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Run setup
```bash
costlocker setup
```
This will ask for your Costlocker API key and guide you through Google Calendar setup.

### 2. Set up Google Calendar credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable **Google Calendar API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Desktop app**
6. Download the JSON and save it to: `~/.costlocker/google_credentials.json`

On first run, your browser will open for Google OAuth authorization.

### 3. Configure event → project mappings
```bash
costlocker map
```

### 4. Sync events
```bash
# Sync today
costlocker sync

# Sync a specific date
costlocker sync --date 2025-02-28

# Preview without logging
costlocker sync --dry-run

# Confirm each event interactively
costlocker sync --interactive
```

## Commands

| Command | Description |
|---|---|
| `costlocker setup` | Configure API keys |
| `costlocker map` | Add event → project mappings |
| `costlocker list-mappings` | Show all mappings |
| `costlocker sync` | Sync today's events |
| `costlocker sync --date YYYY-MM-DD` | Sync a specific date |
| `costlocker sync --dry-run` | Preview without logging |
| `costlocker sync --interactive` | Confirm each event |

## Config file

Config is stored at `~/.costlocker/config.json`:

```json
{
  "costlocker_api_key": "your-api-key",
  "costlocker_base_url": "https://new.costlocker.com/api/public/v2",
  "mappings": {
    "Standup": {
      "project_id": 123,
      "project_name": "Alpha Project",
    },
    "Code Review": {
      "project_id": 123,
      "project_name": "Alpha Project",
    }
  }
}
```

## How mapping works

Event names are matched in this order:
1. **Exact match** — `"Standup"` matches `"Standup"`
2. **Case-insensitive** — `"standup"` matches `"Standup"`
3. **Fuzzy match** — `"Stand-up"` matches `"Standup"` (80% similarity threshold)

Unmapped events are shown in the preview but skipped when logging.
