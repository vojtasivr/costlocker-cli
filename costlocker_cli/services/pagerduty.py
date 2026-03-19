from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import httpx

from costlocker_cli.models import CalendarEvent

BASE_URL = "https://api.pagerduty.com"


class PagerDutyClient:
    def __init__(self, api_key: str):
        self.headers = {
            "Authorization": f"Token token={api_key}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
        }

    def get_current_user_id(self) -> str:
        response = httpx.get(f"{BASE_URL}/users/me", headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()["user"]["id"]

    def get_oncall_events(self, target_date: date, schedule_ids: list[str], user_id: str) -> list[CalendarEvent]:
        day_start = datetime.combine(target_date, time.min, timezone.utc)
        day_end = day_start + timedelta(days=1)

        events: list[CalendarEvent] = []
        for schedule_id in schedule_ids:
            events.extend(self._get_schedule_entries(schedule_id, day_start, day_end, user_id))
        return events

    def _get_schedule_entries(
        self,
        schedule_id: str,
        since: datetime,
        until: datetime,
        user_id: str,
    ) -> list[CalendarEvent]:
        response = httpx.get(
            f"{BASE_URL}/schedules/{schedule_id}",
            headers=self.headers,
            params={"since": since.isoformat(), "until": until.isoformat()},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        schedule_name = data["schedule"]["name"]
        raw_entries = data["schedule"]["final_schedule"]["rendered_schedule_entries"]

        is_weekday = since.weekday() < 5  # Monday=0, Friday=4
        office_start = since.replace(hour=8) if is_weekday else None
        office_end = since.replace(hour=16) if is_weekday else None

        result = []
        for entry in raw_entries:
            if entry["user"]["id"] != user_id:
                continue

            entry_start = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
            entry_end = datetime.fromisoformat(entry["end"].replace("Z", "+00:00"))

            # Clamp to the requested day
            entry_start = max(entry_start, since)
            entry_end = min(entry_end, until)

            base_id = f"pd-{schedule_id}-{entry['start']}"

            if office_start is None:
                # Weekend: log as-is
                duration_minutes = int((entry_end - entry_start).total_seconds() / 60)
                if duration_minutes > 0:
                    result.append(CalendarEvent(
                        id=base_id,
                        event_name=schedule_name,
                        description=f"PagerDuty on-call: {schedule_name}",
                        start=entry_start,
                        end=entry_end,
                        duration_minutes=duration_minutes,
                    ))
                continue

            # Weekday: split around office hours (8:00–16:00 UTC)
            segments = []
            if entry_start < office_start:
                seg_end = min(entry_end, office_start)
                duration = int((seg_end - entry_start).total_seconds() / 60)
                if duration > 0:
                    segments.append((base_id, entry_start, seg_end, duration))
            if entry_end > office_end:
                seg_start = max(entry_start, office_end)
                duration = int((entry_end - seg_start).total_seconds() / 60)
                if duration > 0:
                    segments.append((f"{base_id}-after", seg_start, entry_end, duration))

            for seg_id, seg_start, seg_end, duration_minutes in segments:
                result.append(CalendarEvent(
                    id=seg_id,
                    event_name=schedule_name,
                    description=f"PagerDuty on-call: {schedule_name}",
                    start=seg_start,
                    end=seg_end,
                    duration_minutes=duration_minutes,
                ))

        return result
