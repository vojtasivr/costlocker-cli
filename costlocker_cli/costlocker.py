from datetime import date
from typing import List, Dict, Optional
import httpx


class CostlockerClient:
    def __init__(self, api_key: str, base_url: str = "https://beta.graphql.costlocker.com/graphql"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Static {api_key}",
            "Content-Type": "application/json",
        }
        self._person_id = None

    @property
    def person_id(self) -> str:
        """Fetch and cache the current person ID."""
        if self._person_id is None:
            query = """
                query getCurrentPerson {
                    currentPerson {
                        id
                    }
                }
            """
            response = httpx.post(
                self.base_url,
                headers=self.headers,
                json={"query": query},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            self._person_id = data["data"]["currentPerson"]["id"]
        return self._person_id

    def get_projects(self) -> List[Dict]:
        query = """
            query getProjects(
              $personId: Int!
            ) {
              assignments(
                personId: $personId
              ) {
                activity {
                  id
                  name
                }
                budget {
                  id
                  name
                }
                subtask {
                  activityId
                  budgetId
                  id
                  name
                }
              }
            }
        """

        variables = {"personId": self.person_id}

        response = httpx.post(
            self.base_url,
            headers=self.headers,
            json={"query": query, "variables": variables},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        projects = []
        for item in data.get("data").get("assignments"):
            projects.append({
                "activity_id": item.get("activity").get("id"),
                "activity_name": item.get("activity").get("name"),
                "budget_id": item.get("budget").get("id"),
                "budget_name": item.get("budget").get("name"),
                "subtask_id": (item.get("subtask") or {}).get("id"),
                "subtask_name": (item.get("subtask") or {}).get("name"),
            })
        return projects

    def prepare_schedule(self, target_date: date, entries: List[Dict]) -> List[Dict]:
        """Prepare schedule with gaps filled and lunch break."""
        from datetime import datetime, timedelta

        work_day_start = datetime.fromisoformat(f"{target_date.isoformat()}T08:30:00")
        work_day_end = work_day_start + timedelta(hours=8, minutes=30)  # 8 hours + 30 min lunch
        lunch_start = datetime.fromisoformat(f"{target_date.isoformat()}T11:00:00")
        lunch_end = datetime.fromisoformat(f"{target_date.isoformat()}T11:30:00")

        # Sort entries by start time
        sorted_entries = sorted(entries, key=lambda e: e.get("start", work_day_start))

        # Set calculated times from actual event times (remove timezone info for comparison)
        for entry in sorted_entries:
            start = entry.get("start", work_day_start)
            end = entry.get("end", work_day_start)
            # Remove timezone info if present
            if hasattr(start, 'tzinfo') and start.tzinfo is not None:
                start = start.replace(tzinfo=None)
            if hasattr(end, 'tzinfo') and end.tzinfo is not None:
                end = end.replace(tzinfo=None)
            entry["calculated_start"] = start.isoformat()
            entry["calculated_end"] = end.isoformat()

        schedule = []
        current_time = work_day_start

        for entry in sorted_entries:
            entry_start = datetime.fromisoformat(entry["calculated_start"])
            entry_end = datetime.fromisoformat(entry["calculated_end"])

            # Fill gap before this entry (excluding lunch time)
            if current_time < entry_start:
                # Check if gap overlaps with lunch
                if current_time < lunch_start < entry_start:
                    # Fill until lunch
                    if current_time < lunch_start:
                        gap_minutes = int((lunch_start - current_time).total_seconds() / 60)
                        if gap_minutes > 0:
                            schedule.append({
                                "event_name": "",
                                "duration_minutes": gap_minutes,
                                "calculated_start": current_time.isoformat(),
                                "calculated_end": lunch_start.isoformat(),
                                "is_empty": True,
                            })
                    # Skip lunch time
                    current_time = max(lunch_end, entry_start) if entry_start <= lunch_end else lunch_end
                    # Fill from lunch end to entry start if needed
                    if current_time < entry_start:
                        gap_minutes = int((entry_start - current_time).total_seconds() / 60)
                        if gap_minutes > 0:
                            schedule.append({
                                "event_name": "",
                                "duration_minutes": gap_minutes,
                                "calculated_start": current_time.isoformat(),
                                "calculated_end": entry_start.isoformat(),
                                "is_empty": True,
                            })
                elif lunch_start <= current_time < lunch_end:
                    # We're in lunch time, skip to lunch end
                    current_time = lunch_end
                    if current_time < entry_start:
                        gap_minutes = int((entry_start - current_time).total_seconds() / 60)
                        if gap_minutes > 0:
                            schedule.append({
                                "event_name": "",
                                "duration_minutes": gap_minutes,
                                "calculated_start": current_time.isoformat(),
                                "calculated_end": entry_start.isoformat(),
                                "is_empty": True,
                            })
                else:
                    # No lunch overlap, just fill the gap
                    gap_minutes = int((entry_start - current_time).total_seconds() / 60)
                    if gap_minutes > 0:
                        schedule.append({
                            "event_name": "",
                            "duration_minutes": gap_minutes,
                            "calculated_start": current_time.isoformat(),
                            "calculated_end": entry_start.isoformat(),
                            "is_empty": True,
                        })

            schedule.append(entry)
            current_time = entry_end

        # Fill remaining time until end of work day (excluding lunch if not passed)
        if current_time < work_day_end:
            if current_time < lunch_start < work_day_end:
                # Fill until lunch
                if current_time < lunch_start:
                    gap_minutes = int((lunch_start - current_time).total_seconds() / 60)
                    if gap_minutes > 0:
                        schedule.append({
                            "event_name": "",
                            "duration_minutes": gap_minutes,
                            "calculated_start": current_time.isoformat(),
                            "calculated_end": lunch_start.isoformat(),
                            "is_empty": True,
                        })
                current_time = lunch_end

            # Fill from current time to end of day
            if current_time < work_day_end:
                gap_minutes = int((work_day_end - current_time).total_seconds() / 60)
                if gap_minutes > 0:
                    schedule.append({
                        "event_name": "",
                        "duration_minutes": gap_minutes,
                        "calculated_start": current_time.isoformat(),
                        "calculated_end": work_day_end.isoformat(),
                        "is_empty": True,
                    })

        # Return schedule for preview before posting
        return schedule

    def log_schedule(self, target_date: date, schedule: List[Dict]) -> List[Dict]:
        """Post a prepared schedule to Costlocker."""
        results = []
        for entry in schedule:
            result = self._log_single_entry(target_date, entry)
            results.append(result)
        return results

    def _log_single_entry(self, target_date: date, entry: Dict) -> Dict:
        """Log a single time entry."""
        mutation = """
            mutation createTimeEntry($input: [CreateTimeEntryInput!]!) {
                createTimeEntry: createTimeEntries(input: $input) {
                    uuid
                    personId
                    assignmentKey {
                        budgetKey {
                            activityId
                            budgetId
                            subtaskId
                            __typename
                        }
                        projectId
                        __typename
                    }
                    taskId
                    __typename
                }
            }
        """

        # Use calculated times from schedule or default
        start_time = entry.get("calculated_start", f"{target_date.isoformat()}T08:30:00")
        end_time = entry.get("calculated_end", start_time)
        if entry.get("budget_id"):
            budget_key = {
                "budgetId": entry.get("budget_id"),
                "activityId": entry.get("activity_id"),
            }
            if "subtask_id" in entry:
                budget_key["subtaskId"] = entry["subtask_id"]
            assignment_key = {"budgetKey": budget_key}
        else:
            assignment_key = {}

        variables = {
            "input": [{
                "personId": self.person_id,
                "assignmentKey": assignment_key,
                "startAt": start_time,
                "endAt": end_time,
                "description": entry.get("event_name", ""),
            }]
        }

        try:
            response = httpx.post(
                self.base_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                return {"success": False, "entry": entry, "errors": data["errors"]}

            return {"success": True, "entry": entry, "response": data}
        except httpx.HTTPStatusError as e:
            return {"success": False, "entry": entry, "error": str(e)}
