from __future__ import annotations

from datetime import date, datetime, timedelta

from costlocker_cli.models import ScheduleEntry, TimeEntry

DEFAULT_WORK_START = "08:30"
DEFAULT_WORK_END = "17:00"
DEFAULT_LUNCH_START = "11:00"
LUNCH_DURATION_MINUTES = 30


def prepare_schedule(
    target_date: date,
    entries: list[TimeEntry],
    work_start_time: str = DEFAULT_WORK_START,
    work_end_time: str = DEFAULT_WORK_END,
    lunch_start_time: str = DEFAULT_LUNCH_START,
) -> list[ScheduleEntry]:
    work_start = datetime.fromisoformat(f"{target_date}T{work_start_time}:00")
    work_end = datetime.fromisoformat(f"{target_date}T{work_end_time}:00")
    lunch_start = datetime.fromisoformat(f"{target_date}T{lunch_start_time}:00")
    lunch_end = lunch_start + timedelta(minutes=LUNCH_DURATION_MINUTES)

    sorted_entries = sorted(entries, key=lambda e: e.start)

    schedule_entries = [_to_schedule_entry(e) for e in sorted_entries]

    schedule: list[ScheduleEntry] = []
    current = work_start

    for entry in schedule_entries:
        entry_start = datetime.fromisoformat(entry.calculated_start)
        entry_end = datetime.fromisoformat(entry.calculated_end)

        if current < entry_start:
            schedule.extend(_fill_gap(current, entry_start, lunch_start, lunch_end))
            current = entry_start

        schedule.append(entry)
        current = entry_end

    if current < work_end:
        schedule.extend(_fill_gap(current, work_end, lunch_start, lunch_end))

    return schedule


def _to_schedule_entry(entry: TimeEntry) -> ScheduleEntry:
    start = entry.start.replace(tzinfo=None) if entry.start.tzinfo else entry.start
    end = entry.end.replace(tzinfo=None) if entry.end.tzinfo else entry.end
    return ScheduleEntry(
        event_name=entry.event_name,
        duration_minutes=entry.duration_minutes,
        calculated_start=start.isoformat(),
        calculated_end=end.isoformat(),
        project_name=entry.project_name,
        budget_id=entry.budget_id,
        activity_id=entry.activity_id,
        subtask_id=entry.subtask_id,
    )


def _fill_gap(
    gap_start: datetime,
    gap_end: datetime,
    lunch_start: datetime,
    lunch_end: datetime,
) -> list[ScheduleEntry]:
    result = []
    current = gap_start

    if current < lunch_start < gap_end:
        result.append(_empty_entry(current, lunch_start))
        current = lunch_end

    if current < gap_end:
        result.append(_empty_entry(current, gap_end))

    return [e for e in result if e.duration_minutes > 0]


def _empty_entry(start: datetime, end: datetime) -> ScheduleEntry:
    return ScheduleEntry(
        event_name="",
        duration_minutes=int((end - start).total_seconds() / 60),
        calculated_start=start.isoformat(),
        calculated_end=end.isoformat(),
        is_empty=True,
    )
