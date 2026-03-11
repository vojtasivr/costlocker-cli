from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Any

from costlocker_cli.models import CalendarEvent, Mapping, TimeEntry


class EventMapper:
    def __init__(self, mappings: dict[str, Any]):
        self.mappings = mappings

    def map(self, events: list[CalendarEvent]) -> list[TimeEntry]:
        return [self._map_event(event) for event in events]

    def _map_event(self, event: CalendarEvent) -> TimeEntry:
        mapping = self._find_mapping(event.event_name)
        return TimeEntry(
            id=event.id,
            event_name=f"{mapping.prefix}{event.event_name}" if mapping else event.event_name,
            description=event.description,
            start=event.start,
            end=event.end,
            duration_minutes=event.duration_minutes,
            project_name=mapping.name if mapping else None,
            budget_id=mapping.budget_id if mapping else None,
            activity_id=mapping.activity_id if mapping else None,
            subtask_id=mapping.subtask_id if mapping else None,
        )

    def _find_mapping(self, event_name: str) -> Mapping | None:
        # Exact match
        if event_name in self.mappings:
            return _to_mapping(self.mappings[event_name])

        # Regex match
        for key, value in self.mappings.items():
            if value.get("is_regex", False):
                try:
                    if re.search(key, event_name):
                        return _to_mapping(value)
                except re.error:
                    continue

        # Case-insensitive match
        for key, value in self.mappings.items():
            if not value.get("is_regex", False) and key.lower() == event_name.lower():
                return _to_mapping(value)

        # Fuzzy match
        non_regex = [k for k, v in self.mappings.items() if not v.get("is_regex", False)]
        close = get_close_matches(event_name, non_regex, n=1, cutoff=0.8)
        if close:
            return _to_mapping(self.mappings[close[0]])

        return None


def _to_mapping(raw: dict) -> Mapping:
    return Mapping(
        name=raw.get("name", ""),
        budget_id=raw["budget_id"],
        activity_id=raw["activity_id"],
        subtask_id=raw.get("subtask_id"),
        is_regex=raw.get("is_regex", False),
        prefix=raw.get("prefix", ""),
    )
