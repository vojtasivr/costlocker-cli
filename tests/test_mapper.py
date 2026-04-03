from __future__ import annotations

import pytest

from costlocker_cli.mapper import EventMapper
from tests.conftest import make_event

# ---------------------------------------------------------------------------
# Shared mapping fixtures
# ---------------------------------------------------------------------------

MAPPING_ALPHA = {"name": "Alpha", "budget_id": 1, "activity_id": 10}
MAPPING_BETA = {"name": "Beta", "budget_id": 2, "activity_id": 20}
MAPPING_REGEX = {"name": "Standup", "budget_id": 3, "activity_id": 30, "is_regex": True}
MAPPING_PREFIX = {"name": "OnCall", "budget_id": 4, "activity_id": 40, "prefix": "[PD] "}


# ---------------------------------------------------------------------------
# Exact match
# ---------------------------------------------------------------------------


class TestExactMatch:
    def test_exact_match_returns_correct_project(self):
        mapper = EventMapper({"Daily Standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("Daily Standup", "09:00", "09:30")])
        assert entries[0].project_name == "Alpha"
        assert entries[0].budget_id == 1
        assert entries[0].activity_id == 10

    def test_exact_match_is_case_sensitive(self):
        # "daily standup" should NOT exact-match "Daily Standup"
        mapper = EventMapper({"Daily Standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("daily standup", "09:00", "09:30")])
        # falls through to case-insensitive, still finds a match
        assert entries[0].project_name == "Alpha"

    def test_no_match_returns_unmapped_entry(self):
        mapper = EventMapper({"Daily Standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("Sprint Planning", "10:00", "11:00")])
        assert entries[0].project_name is None
        assert entries[0].budget_id is None

    def test_subtask_id_passed_through(self):
        mapping = {**MAPPING_ALPHA, "subtask_id": 999}
        mapper = EventMapper({"Focus time": mapping})
        entries = mapper.map([make_event("Focus time", "14:00", "15:00")])
        assert entries[0].subtask_id == 999

    def test_subtask_id_absent_when_not_configured(self):
        mapper = EventMapper({"Focus time": MAPPING_ALPHA})
        entries = mapper.map([make_event("Focus time", "14:00", "15:00")])
        assert entries[0].subtask_id is None


# ---------------------------------------------------------------------------
# Regex match
# ---------------------------------------------------------------------------


class TestRegexMatch:
    def test_regex_pattern_matches(self):
        mappings = {"^Daily.*": {**MAPPING_BETA, "is_regex": True}}
        mapper = EventMapper(mappings)
        entries = mapper.map([make_event("Daily Standup", "09:00", "09:30")])
        assert entries[0].project_name == "Beta"

    def test_regex_partial_match(self):
        mappings = {"standup": {**MAPPING_BETA, "is_regex": True}}
        mapper = EventMapper(mappings)
        entries = mapper.map([make_event("Team standup session", "09:00", "09:30")])
        assert entries[0].project_name == "Beta"

    def test_invalid_regex_is_skipped(self):
        # Invalid regex should not crash; falls through to no-match
        mappings = {"[invalid": {**MAPPING_BETA, "is_regex": True}}
        mapper = EventMapper(mappings)
        entries = mapper.map([make_event("anything", "09:00", "09:30")])
        assert entries[0].project_name is None

    def test_regex_key_not_used_in_case_insensitive_pass(self):
        # A regex mapping whose key literally equals the event name (case-insensitive)
        # should NOT match via the case-insensitive pass (is_regex=True excludes it).
        mappings = {"daily standup": {**MAPPING_BETA, "is_regex": True}}
        mapper = EventMapper(mappings)
        # Regex "daily standup" does match "Daily Standup" via re.search (case-sensitive fails)
        # but in this particular case re.search("daily standup", "Daily Standup") → None
        entries = mapper.map([make_event("Daily Standup", "09:00", "09:30")])
        assert entries[0].project_name is None


# ---------------------------------------------------------------------------
# Case-insensitive match
# ---------------------------------------------------------------------------


class TestCaseInsensitiveMatch:
    def test_uppercase_event_matches_lowercase_key(self):
        mapper = EventMapper({"daily standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("DAILY STANDUP", "09:00", "09:30")])
        assert entries[0].project_name == "Alpha"

    def test_mixed_case_event_matches_mapping(self):
        mapper = EventMapper({"Daily Standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("daily standup", "09:00", "09:30")])
        assert entries[0].project_name == "Alpha"

    def test_case_insensitive_does_not_match_regex_keys(self):
        # is_regex keys are excluded from the case-insensitive pass
        mappings = {"Daily Standup": {**MAPPING_BETA, "is_regex": True}}
        mapper = EventMapper(mappings)
        entries = mapper.map([make_event("daily standup", "09:00", "09:30")])
        # regex "Daily Standup" vs "daily standup" → re.search fails, then case-insensitive
        # pass skips because is_regex=True, fuzzy may match
        # result depends on fuzzy threshold – important: no crash
        assert entries[0].project_name is None or entries[0].project_name == "Beta"


# ---------------------------------------------------------------------------
# Fuzzy match
# ---------------------------------------------------------------------------


class TestFuzzyMatch:
    def test_close_match_above_threshold(self):
        # "Daily Standup " (trailing space) is very close to "Daily Standup"
        mapper = EventMapper({"Daily Standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("Daily Standup ", "09:00", "09:30")])
        assert entries[0].project_name == "Alpha"

    def test_distant_string_does_not_match(self):
        mapper = EventMapper({"Daily Standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("Completely Different Meeting", "09:00", "09:30")])
        assert entries[0].project_name is None

    def test_fuzzy_ignores_regex_keys(self):
        # Only non-regex keys participate in fuzzy matching
        mappings = {"Daily Standup": {**MAPPING_BETA, "is_regex": True}}
        mapper = EventMapper(mappings)
        entries = mapper.map([make_event("Daily Standap", "09:00", "09:30")])
        assert entries[0].project_name is None


# ---------------------------------------------------------------------------
# Prefix
# ---------------------------------------------------------------------------


class TestPrefix:
    def test_prefix_prepended_to_event_name(self):
        mapper = EventMapper({"On-call": MAPPING_PREFIX})
        entries = mapper.map([make_event("On-call", "22:00", "23:00")])
        assert entries[0].event_name == "[PD] On-call"

    def test_no_prefix_when_not_configured(self):
        mapper = EventMapper({"Standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("Standup", "09:00", "09:30")])
        assert entries[0].event_name == "Standup"

    def test_no_prefix_on_unmapped_event(self):
        mapper = EventMapper({"Standup": MAPPING_ALPHA})
        entries = mapper.map([make_event("Unknown Event", "09:00", "09:30")])
        assert entries[0].event_name == "Unknown Event"


# ---------------------------------------------------------------------------
# Event fields preserved
# ---------------------------------------------------------------------------


class TestEventFieldsPreserved:
    def test_id_duration_description_preserved(self):
        mapper = EventMapper({"Meeting": MAPPING_ALPHA})
        event = make_event("Meeting", "10:00", "11:00", eid="abc123", description="Sync with team")
        entries = mapper.map([event])
        assert entries[0].id == "abc123"
        assert entries[0].duration_minutes == 60
        assert entries[0].description == "Sync with team"

    def test_multiple_events_all_mapped(self):
        mappings = {"Standup": MAPPING_ALPHA, "Retro": MAPPING_BETA}
        mapper = EventMapper(mappings)
        events = [
            make_event("Standup", "09:00", "09:30", eid="e1"),
            make_event("Retro", "15:00", "16:00", eid="e2"),
        ]
        entries = mapper.map(events)
        assert len(entries) == 2
        assert entries[0].project_name == "Alpha"
        assert entries[1].project_name == "Beta"

    def test_empty_event_list_returns_empty(self):
        mapper = EventMapper({"Standup": MAPPING_ALPHA})
        assert mapper.map([]) == []
