from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from costlocker_cli.models import CalendarEvent, TimeEntry

TARGET_DATE = date(2024, 1, 15)  # Monday
TARGET_DATE_STR = "2024-01-15"


def make_event(
    name: str,
    start: str,
    end: str,
    eid: str = "evt1",
    description: str = "",
    tz_aware: bool = False,
) -> CalendarEvent:
    tz = timezone.utc if tz_aware else None
    s = datetime.fromisoformat(f"{TARGET_DATE_STR}T{start}:00").replace(tzinfo=tz)
    e = datetime.fromisoformat(f"{TARGET_DATE_STR}T{end}:00").replace(tzinfo=tz)
    duration = int((e - s).total_seconds() / 60)
    return CalendarEvent(id=eid, event_name=name, start=s, end=e, duration_minutes=duration, description=description)


def make_entry(
    name: str,
    start: str,
    end: str,
    eid: str = "evt1",
    tz_aware: bool = False,
    **kwargs,
) -> TimeEntry:
    tz = timezone.utc if tz_aware else None
    s = datetime.fromisoformat(f"{TARGET_DATE_STR}T{start}:00").replace(tzinfo=tz)
    e = datetime.fromisoformat(f"{TARGET_DATE_STR}T{end}:00").replace(tzinfo=tz)
    duration = int((e - s).total_seconds() / 60)
    return TimeEntry(id=eid, event_name=name, start=s, end=e, duration_minutes=duration, **kwargs)


@pytest.fixture
def target_date() -> date:
    return TARGET_DATE
