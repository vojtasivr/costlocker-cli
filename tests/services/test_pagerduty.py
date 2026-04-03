from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from costlocker_cli.services.pagerduty import BASE_URL, PagerDutyClient

SCHEDULE_ID = "SCH001"
USER_ID = "USER1"
OTHER_USER_ID = "USER2"
SCHEDULE_URL = f"{BASE_URL}/schedules/{SCHEDULE_ID}"
SCHEDULE_NAME = "Primary On-Call"

MONDAY = date(2024, 1, 15)   # weekday
SATURDAY = date(2024, 1, 20)  # weekend


def _schedule_response(entries: list[dict]) -> dict:
    return {
        "schedule": {
            "name": SCHEDULE_NAME,
            "final_schedule": {"rendered_schedule_entries": entries},
        }
    }


def _entry(start: str, end: str, user_id: str = USER_ID) -> dict:
    return {"user": {"id": user_id}, "start": start, "end": end}


@pytest.fixture
def client() -> PagerDutyClient:
    return PagerDutyClient(api_key="test-key")


# ---------------------------------------------------------------------------
# Weekday on-call logic (office hours 08:00–16:00 UTC)
# ---------------------------------------------------------------------------


class TestWeekdayOncall:
    @respx.mock
    def test_entry_fully_before_office_hours(self, client):
        # 05:00–07:00 UTC → 120 min, entirely before office
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T05:00:00Z", "2024-01-15T07:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert len(events) == 1
        assert events[0].duration_minutes == 120

    @respx.mock
    def test_entry_fully_during_office_hours_yields_no_events(self, client):
        # 09:00–15:00 UTC → completely inside office hours, nothing logged
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T09:00:00Z", "2024-01-15T15:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert events == []

    @respx.mock
    def test_entry_fully_after_office_hours(self, client):
        # 17:00–23:00 UTC → 360 min, entirely after office
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T17:00:00Z", "2024-01-15T23:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert len(events) == 1
        assert events[0].duration_minutes == 360

    @respx.mock
    def test_entry_spanning_full_day_split_into_two_segments(self, client):
        # 06:00–20:00 UTC → before: 06:00–08:00 (120 min), after: 16:00–20:00 (240 min)
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T06:00:00Z", "2024-01-15T20:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert len(events) == 2
        total_duration = sum(e.duration_minutes for e in events)
        assert total_duration == 360  # 120 + 240

    @respx.mock
    def test_before_segment_ends_at_office_start(self, client):
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T06:00:00Z", "2024-01-15T20:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        before = next(e for e in events if "after" not in e.id)
        assert before.end == datetime(2024, 1, 15, 8, 0, tzinfo=UTC)

    @respx.mock
    def test_after_segment_starts_at_office_end(self, client):
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T06:00:00Z", "2024-01-15T20:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        after = next(e for e in events if "after" in e.id)
        assert after.start == datetime(2024, 1, 15, 16, 0, tzinfo=UTC)

    @respx.mock
    def test_entry_starting_exactly_at_office_start_has_no_before_segment(self, client):
        # 08:00–20:00 → no before segment, after: 16:00–20:00 (240 min)
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T08:00:00Z", "2024-01-15T20:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert len(events) == 1
        assert events[0].duration_minutes == 240

    @respx.mock
    def test_entry_ending_exactly_at_office_end_has_no_after_segment(self, client):
        # 06:00–16:00 → before: 06:00–08:00 (120 min), no after segment
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T06:00:00Z", "2024-01-15T16:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert len(events) == 1
        assert events[0].duration_minutes == 120


# ---------------------------------------------------------------------------
# Weekend on-call logic (full duration)
# ---------------------------------------------------------------------------


class TestWeekendOncall:
    @respx.mock
    def test_weekend_entry_logged_in_full(self, client):
        # Saturday: 09:00–17:00 → 480 min, no office-hours filtering
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-20T09:00:00Z", "2024-01-20T17:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(SATURDAY, [SCHEDULE_ID], USER_ID)
        assert len(events) == 1
        assert events[0].duration_minutes == 480

    @respx.mock
    def test_weekend_entry_during_office_hours_still_logged(self, client):
        # Unlike weekday, 09:00–15:00 on Saturday is fully logged
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-20T09:00:00Z", "2024-01-20T15:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(SATURDAY, [SCHEDULE_ID], USER_ID)
        assert len(events) == 1
        assert events[0].duration_minutes == 360


# ---------------------------------------------------------------------------
# User filtering
# ---------------------------------------------------------------------------


class TestUserFiltering:
    @respx.mock
    def test_entry_for_different_user_is_skipped(self, client):
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T05:00:00Z", "2024-01-15T07:00:00Z", user_id=OTHER_USER_ID),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert events == []

    @respx.mock
    def test_only_target_users_entries_included(self, client):
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T05:00:00Z", "2024-01-15T07:00:00Z", user_id=USER_ID),
                _entry("2024-01-15T05:00:00Z", "2024-01-15T07:00:00Z", user_id=OTHER_USER_ID),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert len(events) == 1


# ---------------------------------------------------------------------------
# Day clamping
# ---------------------------------------------------------------------------


class TestDayClamping:
    @respx.mock
    def test_entry_extending_beyond_midnight_clamped_to_day_end(self, client):
        # Entry spans into the next day — should be clamped to 00:00 of target date
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T22:00:00Z", "2024-01-16T06:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        # 22:00 is after office end (16:00) → logged. Clamped to 00:00 next day.
        # Duration: 22:00 to 00:00 = 120 min
        assert len(events) == 1
        assert events[0].duration_minutes == 120

    @respx.mock
    def test_entry_starting_before_midnight_clamped_to_day_start(self, client):
        # Entry from previous day extends into target day
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-14T20:00:00Z", "2024-01-15T07:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        # Clamped to 00:00–07:00 = 420 min, before office hours
        assert len(events) == 1
        assert events[0].duration_minutes == 420


# ---------------------------------------------------------------------------
# Event metadata
# ---------------------------------------------------------------------------


class TestEventMetadata:
    @respx.mock
    def test_event_name_equals_schedule_name(self, client):
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T05:00:00Z", "2024-01-15T07:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert events[0].event_name == SCHEDULE_NAME

    @respx.mock
    def test_description_references_schedule_name(self, client):
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T05:00:00Z", "2024-01-15T07:00:00Z"),
            ]))
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID], USER_ID)
        assert SCHEDULE_NAME in events[0].description

    @respx.mock
    def test_multiple_schedule_ids_all_queried(self, client):
        schedule_b_url = f"{BASE_URL}/schedules/SCH002"
        respx.get(SCHEDULE_URL).mock(
            return_value=httpx.Response(200, json=_schedule_response([
                _entry("2024-01-15T05:00:00Z", "2024-01-15T07:00:00Z"),
            ]))
        )
        respx.get(schedule_b_url).mock(
            return_value=httpx.Response(200, json={
                "schedule": {
                    "name": "Secondary On-Call",
                    "final_schedule": {"rendered_schedule_entries": [
                        _entry("2024-01-15T17:00:00Z", "2024-01-15T20:00:00Z"),
                    ]},
                }
            })
        )
        events = client.get_oncall_events(MONDAY, [SCHEDULE_ID, "SCH002"], USER_ID)
        assert len(events) == 2
