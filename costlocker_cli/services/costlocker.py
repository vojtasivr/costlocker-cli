from __future__ import annotations

from datetime import date

import httpx

from costlocker_cli.models import Project, ScheduleEntry


class CostlockerClient:
    def __init__(self, api_key: str, base_url: str = "https://beta.graphql.costlocker.com/graphql"):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Static {api_key}",
            "Content-Type": "application/json",
        }
        self._person_id: str | None = None

    @property
    def person_id(self) -> str:
        if self._person_id is None:
            data = self._post({"query": "query { currentPerson { id } }"})
            self._person_id = data["data"]["currentPerson"]["id"]
        return self._person_id

    def get_projects(self) -> list[Project]:
        query = """
            query getProjects($personId: Int!) {
              assignments(personId: $personId) {
                activity { id name }
                budget { id name }
                subtask { id name }
              }
            }
        """
        data = self._post({"query": query, "variables": {"personId": self.person_id}})
        projects = []
        for item in data["data"]["assignments"]:
            subtask = item.get("subtask") or {}
            projects.append(Project(
                activity_id=item["activity"]["id"],
                activity_name=item["activity"]["name"],
                budget_id=item["budget"]["id"],
                budget_name=item["budget"]["name"],
                subtask_id=subtask.get("id"),
                subtask_name=subtask.get("name"),
            ))
        return projects

    def log_schedule(self, target_date: date, schedule: list[ScheduleEntry]) -> list[dict]:
        return [self._log_entry(target_date, entry) for entry in schedule]

    def _log_entry(self, target_date: date, entry: ScheduleEntry) -> dict:
        mutation = """
            mutation createTimeEntry($input: [CreateTimeEntryInput!]!) {
                createTimeEntry: createTimeEntries(input: $input) {
                    uuid personId
                    assignmentKey {
                        budgetKey { activityId budgetId subtaskId __typename }
                        projectId __typename
                    }
                    taskId __typename
                }
            }
        """
        if entry.budget_id:
            budget_key: dict = {"budgetId": entry.budget_id, "activityId": entry.activity_id}
            if entry.subtask_id is not None:
                budget_key["subtaskId"] = entry.subtask_id
            assignment_key = {"budgetKey": budget_key}
        else:
            assignment_key = {}

        variables = {
            "input": [{
                "personId": self.person_id,
                "assignmentKey": assignment_key,
                "startAt": entry.calculated_start,
                "endAt": entry.calculated_end,
                "description": entry.event_name,
            }]
        }

        try:
            data = self._post({"query": mutation, "variables": variables})
            if "errors" in data:
                return {"success": False, "entry": entry, "errors": data["errors"]}
            return {"success": True, "entry": entry}
        except httpx.HTTPStatusError as e:
            return {"success": False, "entry": entry, "error": str(e)}

    def _post(self, payload: dict) -> dict:
        response = httpx.post(self.base_url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
