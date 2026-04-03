# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
python -m pytest

# Run a single test file
python -m pytest tests/test_mapper.py

# Run a single test
python -m pytest tests/test_mapper.py::TestExactMatch::test_exact_match

# Run tests with coverage
python -m pytest --cov

# Lint
python -m ruff check .

# Format/fix lint issues
python -m ruff check --fix .

# Run the CLI
costlocker sync
costlocker sync --date 2024-01-15 --interactive
```

## Architecture

This is a CLI tool (`typer`) that syncs events from Google Calendar, PagerDuty, and Azure DevOps into Costlocker timesheets.

**Data flow for `costlocker sync`:**
1. Fetch timed events from Google Calendar (OAuth2, token cached at `~/.costlocker/google_token.pickle`)
2. Optionally fetch PagerDuty on-call shifts (filtered to non-office-hours on weekdays, full duration on weekends)
3. Map event names → Costlocker projects via `EventMapper` (exact → regex → case-insensitive → fuzzy 80%)
4. Optionally fetch Azure DevOps items (PRs + PBIs) and fill empty schedule slots round-robin
5. `prepare_schedule()` fills workday gaps with empty slots and inserts a lunch break
6. Post all entries to Costlocker via GraphQL (`createTimeEntries` mutation)

**Key modules:**
- `models.py` — Dataclasses: `CalendarEvent` → `TimeEntry` → `ScheduleEntry` (pipeline stages)
- `mapper.py` — `EventMapper`: maps event names to projects using multi-strategy matching
- `services/scheduler.py` — `prepare_schedule()`: pure function, fills day gaps, inserts lunch
- `services/pagerduty.py` — Splits on-call around office hours (8:00-16:00 UTC), clamps to target day
- `services/costlocker.py` — GraphQL client; lazy-loads `person_id` via `currentPerson` query
- `services/azuredevops.py` — Fetches PRs (created/reviewed) and PBIs modified on target day
- `commands/sync.py` — Orchestrates the full sync pipeline

**Config** stored at `~/.costlocker/config.json`. Run `costlocker setup` to configure interactively.

**Testing** uses `respx` for mocked HTTP (PagerDuty), standard pytest fixtures in `conftest.py`. `TARGET_DATE = 2024-01-15` (Monday) is the canonical test date.
