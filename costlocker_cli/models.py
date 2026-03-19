from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CalendarEvent:
    id: str
    event_name: str
    start: datetime
    end: datetime
    duration_minutes: int
    description: str = ""


@dataclass
class Project:
    budget_id: int
    budget_name: str
    activity_id: int
    activity_name: str
    subtask_id: int | None = None
    subtask_name: str | None = None

    @property
    def display_name(self) -> str:
        name = f"{self.budget_name} - {self.activity_name}"
        if self.subtask_name:
            name += f" - {self.subtask_name}"
        return name


@dataclass
class Mapping:
    name: str
    budget_id: int
    activity_id: int
    subtask_id: int | None = None
    is_regex: bool = False
    prefix: str = ""


@dataclass
class TimeEntry:
    event_name: str
    duration_minutes: int
    start: datetime
    end: datetime
    id: str = ""
    description: str = ""
    project_name: str | None = None
    budget_id: int | None = None
    activity_id: int | None = None
    subtask_id: int | None = None


@dataclass
class ScheduleEntry:
    event_name: str
    duration_minutes: int
    calculated_start: str
    calculated_end: str
    project_name: str | None = None
    budget_id: int | None = None
    activity_id: int | None = None
    subtask_id: int | None = None
    is_empty: bool = False
    description: str = ""
