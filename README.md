# costlocker-cli

A CLI tool to sync Google Calendar and PagerDuty on-call schedules to Costlocker timesheets.

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Run setup
```bash
costlocker setup
```
Configures your Costlocker API key, Google Calendar credentials, and optionally PagerDuty.

### 2. Set up Google Calendar credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Google Calendar API**
3. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
4. Application type: **Desktop app**
5. Download the JSON and save it to `~/.costlocker/google_credentials.json`

On first run, your browser will open for Google OAuth authorization.

### 3. Configure event → project mappings
```bash
costlocker map
```

### 4. Sync events
```bash
costlocker sync                      # Sync today
costlocker sync --date 2025-02-28    # Sync a specific date
costlocker sync --dry-run            # Preview without logging
costlocker sync --interactive        # Confirm each event interactively
```

## Commands

| Command | Description |
|---|---|
| `costlocker setup` | Configure API keys and integrations |
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
  "costlocker_base_url": "https://api.costlocker.com/graphql",
  "mappings": {
    "Standup": {
      "budget_id": 123,
      "activity_id": 456,
      "name": "Alpha Project - Development",
      "is_regex": false,
      "prefix": ""
    },
    "^Ents - |- SU": {
      "budget_id": 789,
      "activity_id": 101,
      "name": "BAU - Meetings",
      "is_regex": true,
      "prefix": ""
    }
  },
  "pagerduty": {
    "api_key": "your-pagerduty-api-key",
    "user_id": "PXXXXXX",
    "schedule_ids": ["PXXXXXX", "PXXXXXX"]
  }
}
```

## How mapping works

Event names are matched in this order:

1. **Exact match** — `"Standup"` matches `"Standup"`
2. **Regex** — pattern `^On-Call` matches any event starting with `"On-Call"`
3. **Case-insensitive** — `"standup"` matches `"Standup"`
4. **Fuzzy match** — `"Stand-up"` matches `"Standup"` (80% similarity threshold)

Unmapped events are shown in the preview but skipped when logging.

## PagerDuty integration

When configured, on-call schedule entries are fetched alongside Google Calendar events and appear in the sync preview. Set up during `costlocker setup` — you'll need your PagerDuty API key and the schedule IDs to watch (found in the schedule URL: `pagerduty.com/schedules#PXXXXXX`).

## Schedule behaviour

The sync fills the workday (08:30–17:00) around your events, inserting a 30-minute lunch break at 11:00–11:30. Empty slots are posted as blank entries.
