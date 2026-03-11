from typing import List, Dict
from difflib import get_close_matches
import re


class EventMapper:
    def __init__(self, mappings: Dict):
        """
        mappings: dict of event_name -> { budget_id, project_name, is_regex (optional) }
        Loaded from a config file.
        """
        self.mappings = mappings

    def map(self, events: List[Dict]) -> List[Dict]:
        """Map calendar events to Costlocker time entries."""
        entries = []
        for event in events:
            event_name = event["event_name"]

            mapping = self._find_mapping(event_name)
            entry = {**event}

            if mapping:
                entry["project_name"] = mapping.get("name")
                entry["budget_id"] = mapping.get("budget_id")
                entry["activity_id"] = mapping.get("activity_id")
                if "subtask_id" in mapping:
                    entry["subtask_id"] = mapping["subtask_id"]
                entry["event_name"] = event_name
            else:
                entry["project_name"] = None
                entry["budget_id"] = None
                entry["activity_id"] = None
                entry["event_name"] = event_name

            entries.append(entry)
        return entries

    def _find_mapping(self, event_name: str) -> Dict | None:
        """Find a mapping for an event name. Supports exact, regex, and fuzzy matching."""
        # Exact match first
        if event_name in self.mappings:
            return self.mappings[event_name]

        # Regex match
        for key, value in self.mappings.items():
            if value.get("is_regex", False):
                try:
                    if re.search(key, event_name):
                        return value
                except re.error:
                    # Invalid regex, skip
                    continue

        # Case-insensitive match
        for key, value in self.mappings.items():
            if not value.get("is_regex", False) and key.lower() == event_name.lower():
                return value

        # Fuzzy match (similarity > 0.8) - only for non-regex patterns
        non_regex_keys = [k for k, v in self.mappings.items() if not v.get("is_regex", False)]
        close = get_close_matches(event_name, non_regex_keys, n=1, cutoff=0.8)
        if close:
            return self.mappings[close[0]]

        return None
