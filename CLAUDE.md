# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`costlocker-cli` is a Python CLI tool that syncs Google Calendar events to Costlocker timesheets. It fetches timed calendar events, maps them to Costlocker projects, fills schedule gaps, and posts time entries via the Costlocker GraphQL API.

## Setup & Installation

```bash
pip install -e .
```

Requires Python >=3.11. No test or lint framework is configured.

## CLI Usage

```bash
costlocker setup                        # Configure API key and Google OAuth
costlocker map                          # Add/edit event → project mappings
costlocker list-mappings                # Show all mappings
costlocker sync                         # Sync today's events
costlocker sync --date 2025-02-28       # Sync a specific date
costlocker sync --dry-run               # Preview without logging
costlocker sync --interactive           # Confirm each event interactively
```

## Architecture

Data flows: **Google Calendar → `gcalendar.py`** (OAuth2, fetches timed events) → **`mapper.py`** (matches event names to projects) → **`costlocker.py`** (fills schedule gaps, POSTs via GraphQL) → **Costlocker API**

### Modules

- **`main.py`** — Typer CLI entry point; all commands and Rich terminal output live here
- **`config.py`** — Loads/saves `~/.costlocker/config.json`; interactive setup wizard
- **`gcalendar.py`** — Google Calendar OAuth2 + event fetching; token cached at `~/.costlocker/google_token.pickle`; all-day events are excluded
- **`costlocker.py`** — GraphQL API client; `prepare_schedule()` fills workday gaps (8:30–17:00) and inserts a 30-min lunch at 11:00–11:30; `log_schedule()` posts entries
- **`mapper.py`** — Matches event names to projects in order: exact → regex → case-insensitive → fuzzy (80% threshold); hardcodes BAU meeting patterns (events starting with `"Ents - "` or containing `"- SU"`)

### Config & Credentials

| File | Purpose |
|---|---|
| `~/.costlocker/config.json` | API key, base URL, event→project mappings |
| `~/.costlocker/google_credentials.json` | OAuth2 client credentials (download from Google Cloud Console) |
| `~/.costlocker/google_token.pickle` | Cached OAuth2 refresh token |