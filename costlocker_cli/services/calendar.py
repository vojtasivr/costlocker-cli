from __future__ import annotations

import pickle
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from costlocker_cli.models import CalendarEvent

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_PATH = Path.home() / ".costlocker" / "google_token.pickle"
CREDENTIALS_PATH = Path.home() / ".costlocker" / "google_credentials.json"


def get_calendar_events(target_date: date) -> list[CalendarEvent]:
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)

    start = datetime.combine(target_date, time.min, UTC)
    end = start + timedelta(days=1)

    result = service.events().list(
        calendarId="primary",
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    raw_events = result.get("items", [])
    return [_parse_event(e) for e in raw_events if _is_timed_event(e)]


def _get_credentials() -> Credentials:
    creds = None

    if TOKEN_PATH.exists():
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Google credentials not found at {CREDENTIALS_PATH}.\n"
                    "Download credentials.json from Google Cloud Console and place it there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return creds


def _is_timed_event(event: dict) -> bool:
    return "dateTime" in event.get("start", {})


def _parse_event(event: dict) -> CalendarEvent:
    start = datetime.fromisoformat(event["start"]["dateTime"])
    end = datetime.fromisoformat(event["end"]["dateTime"])
    return CalendarEvent(
        id=event["id"],
        event_name=event.get("summary", "(No title)"),
        description=event.get("description", ""),
        start=start,
        end=end,
        duration_minutes=int((end - start).total_seconds() / 60),
    )
