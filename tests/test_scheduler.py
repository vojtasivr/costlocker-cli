from __future__ import annotations

from costlocker_cli.services.scheduler import prepare_schedule
from tests.conftest import TARGET_DATE, make_entry


def durations(schedule):
    return [e.duration_minutes for e in schedule]


def names(schedule):
    return [e.event_name for e in schedule]


def starts(schedule):
    return [e.calculated_start for e in schedule]


def empty_flags(schedule):
    return [e.is_empty for e in schedule]


# ---------------------------------------------------------------------------
# No entries — entire day filled with gaps
# ---------------------------------------------------------------------------


class TestNoEntries:
    def test_full_day_produces_two_empty_slots(self):
        # Default: 08:30–17:00, lunch 11:00–11:30
        # Expected: [08:30–11:00 (150 min), 11:30–17:00 (330 min)]
        schedule = prepare_schedule(TARGET_DATE, [])
        assert len(schedule) == 2
        assert all(e.is_empty for e in schedule)
        assert durations(schedule) == [150, 330]

    def test_custom_work_hours_no_entries(self):
        schedule = prepare_schedule(TARGET_DATE, [], work_start_time="09:00", work_end_time="18:00")
        # lunch splits: 09:00–11:00 (120 min), 11:30–18:00 (390 min)
        assert durations(schedule) == [120, 390]

    def test_lunch_after_work_end_no_split(self):
        # Lunch is outside the work window — no lunch split
        schedule = prepare_schedule(
            TARGET_DATE, [], work_start_time="08:00", work_end_time="10:00", lunch_start_time="12:00"
        )
        assert len(schedule) == 1
        assert schedule[0].duration_minutes == 120
        assert schedule[0].is_empty


# ---------------------------------------------------------------------------
# Single entry
# ---------------------------------------------------------------------------


class TestSingleEntry:
    def test_entry_at_start_fills_rest_of_day(self):
        # Entry: 08:30–09:00 → gap [09:00–11:00, 11:30–17:00]
        schedule = prepare_schedule(TARGET_DATE, [make_entry("Standup", "08:30", "09:00")])
        assert len(schedule) == 3
        assert not schedule[0].is_empty  # the entry itself
        assert schedule[1].is_empty
        assert schedule[2].is_empty
        assert durations(schedule) == [30, 120, 330]

    def test_entry_in_middle_creates_gaps_before_and_after(self):
        # Entry: 10:00–12:00
        # Gap before: 08:30–10:00 = 90 min (no lunch split, ends before 11:00)
        # Gap after: 12:00–17:00 = 300 min (lunch already past)
        schedule = prepare_schedule(TARGET_DATE, [make_entry("Review", "10:00", "12:00")])
        assert len(schedule) == 3
        assert empty_flags(schedule) == [True, False, True]
        assert durations(schedule) == [90, 120, 300]

    def test_entry_at_end_fills_start_of_day(self):
        # Entry: 13:00–17:00
        # Gap before: 08:30–11:00 (150 min), 11:30–13:00 (90 min)
        schedule = prepare_schedule(TARGET_DATE, [make_entry("Afternoon", "13:00", "17:00")])
        assert len(schedule) == 3
        assert empty_flags(schedule) == [True, True, False]
        assert durations(schedule) == [150, 90, 240]

    def test_entry_fills_exact_work_day_no_gaps(self):
        schedule = prepare_schedule(TARGET_DATE, [make_entry("All Day", "08:30", "17:00")])
        assert len(schedule) == 1
        assert not schedule[0].is_empty

    def test_entry_spanning_lunch_gap_split_around_it(self):
        # Gap before entry: 08:30–09:00 = 30 min
        # Entry: 09:00–14:00 (spans lunch but entry itself is not split)
        # Gap after: 14:00–17:00 = 180 min
        schedule = prepare_schedule(TARGET_DATE, [make_entry("Workshop", "09:00", "14:00")])
        assert len(schedule) == 3
        assert durations(schedule) == [30, 300, 180]
        assert empty_flags(schedule) == [True, False, True]


# ---------------------------------------------------------------------------
# Multiple entries
# ---------------------------------------------------------------------------


class TestMultipleEntries:
    def test_two_consecutive_entries_no_gap_between_them(self):
        entries = [
            make_entry("Standup", "09:00", "09:30", eid="e1"),
            make_entry("Planning", "09:30", "10:30", eid="e2"),
        ]
        schedule = prepare_schedule(TARGET_DATE, entries)
        # Gap: 08:30–09:00, entry1, entry2, gap: 09:30... wait entry2 ends 10:30
        # Gap after: 10:30–11:00, 11:30–17:00
        non_empty = [e for e in schedule if not e.is_empty]
        assert len(non_empty) == 2
        assert non_empty[0].event_name == "Standup"
        assert non_empty[1].event_name == "Planning"

    def test_gap_between_two_entries_split_by_lunch(self):
        entries = [
            make_entry("Morning", "09:00", "10:00", eid="e1"),
            make_entry("Afternoon", "12:00", "13:00", eid="e2"),
        ]
        schedule = prepare_schedule(TARGET_DATE, entries)
        # Gap before Morning: 08:30–09:00 = 30 min
        # Morning entry
        # Gap: 10:00–12:00, split by lunch → 10:00–11:00 (60 min), 11:30–12:00 (30 min)
        # Afternoon entry
        # Gap after: 13:00–17:00 = 240 min
        assert len(schedule) == 6
        assert durations(schedule) == [30, 60, 60, 30, 60, 240]

    def test_ordering_preserved(self):
        entries = [
            make_entry("A", "09:00", "09:30", eid="e1"),
            make_entry("B", "10:00", "10:30", eid="e2"),
            make_entry("C", "14:00", "15:00", eid="e3"),
        ]
        schedule = prepare_schedule(TARGET_DATE, entries)
        non_empty_names = [e.event_name for e in schedule if not e.is_empty]
        assert non_empty_names == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Timezone stripping
# ---------------------------------------------------------------------------


class TestTimezoneStripping:
    def test_tz_aware_entry_has_naive_datetimes_in_schedule(self):
        entry = make_entry("On-call", "09:00", "10:00", tz_aware=True)
        assert entry.start.tzinfo is not None

        schedule = prepare_schedule(TARGET_DATE, [entry])
        for se in schedule:
            # calculated_start/end are ISO strings — verify they have no "+00:00" offset
            assert "+" not in se.calculated_start
            assert "+" not in se.calculated_end


# ---------------------------------------------------------------------------
# Schedule entry fields
# ---------------------------------------------------------------------------


class TestScheduleEntryFields:
    def test_project_fields_copied_from_time_entry(self):
        entry = make_entry(
            "Work",
            "09:00",
            "10:00",
            project_name="Alpha",
            budget_id=1,
            activity_id=10,
            subtask_id=100,
            description="some desc",
        )
        schedule = prepare_schedule(TARGET_DATE, [entry])
        work_entry = next(e for e in schedule if not e.is_empty)
        assert work_entry.project_name == "Alpha"
        assert work_entry.budget_id == 1
        assert work_entry.activity_id == 10
        assert work_entry.subtask_id == 100
        assert work_entry.description == "some desc"

    def test_empty_entry_has_no_project(self):
        schedule = prepare_schedule(TARGET_DATE, [])
        for entry in schedule:
            assert entry.project_name is None
            assert entry.budget_id is None
