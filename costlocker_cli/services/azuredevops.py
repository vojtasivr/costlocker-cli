from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone

import httpx


class AzureDevOpsClient:
    def __init__(self, pat: str, organization: str, project: str):
        token = base64.b64encode(f":{pat}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }
        self.base_url = f"https://dev.azure.com/{organization}/{project}/_apis"
        self.organization = organization

    def get_current_user_id(self) -> str:
        response = httpx.get(
            f"https://dev.azure.com/{self.organization}/_apis/connectionData",
            headers=self.headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["authenticatedUser"]["id"]

    def get_daily_items(self, target_date: date, user_id: str) -> list[tuple[str, str]]:
        """Returns list of (name, kind) where kind is 'bli' or 'cr'."""
        items: list[tuple[str, str]] = []
        items.extend(self._get_pull_requests(target_date, user_id))
        items.extend(self._get_product_backlog_items(target_date))
        return items

    def _get_pull_requests(self, target_date: date, user_id: str) -> list[tuple[str, str]]:
        day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        result: dict[str, str] = {}  # name -> kind, preserving insertion order + dedup

        # PRs created by user on this day
        for pr in self._fetch_prs({"searchCriteria.creatorId": user_id}, day_start, day_end):
            for name, kind in self._pr_display_names(pr):
                result.setdefault(name, kind)

        # PRs where user is reviewer — include only if approved or commented
        for pr in self._fetch_prs({"searchCriteria.reviewerId": user_id}, day_start, day_end):
            user_reviewer = next(
                (r for r in pr.get("reviewers", []) if r.get("id") == user_id), None
            )
            if user_reviewer is None:
                continue
            vote = user_reviewer.get("vote", 0)
            if vote >= 5:
                for name, kind in self._pr_display_names(pr):
                    result.setdefault(name, kind)
            elif self._user_has_comment(pr["repository"]["id"], pr["pullRequestId"], user_id):
                for name, kind in self._pr_display_names(pr):
                    result.setdefault(name, kind)

        return list(result.items())

    def _fetch_prs(self, criteria: dict, day_start: datetime, day_end: datetime) -> list[dict]:
        params = {
            **criteria,
            "searchCriteria.minTime": day_start.isoformat(),
            "searchCriteria.maxTime": day_end.isoformat(),
            "searchCriteria.status": "all",
            "api-version": "7.0",
        }
        response = httpx.get(
            f"{self.base_url}/git/pullrequests",
            headers=self.headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("value", [])

    def _pr_display_names(self, pr: dict) -> list[tuple[str, str]]:
        """Return linked PBIs as ('BLI ...', 'bli') if any, else PR title as ('...', 'cr')."""
        repo_id = pr["repository"]["id"]
        pr_id = pr["pullRequestId"]
        linked_pbis = self._get_pr_linked_pbis(repo_id, pr_id)
        if linked_pbis:
            return [(f"{title} - CR", "bli") for title in linked_pbis]
        return [(pr["title"], "cr")]

    def _get_pr_linked_pbis(self, repo_id: str, pr_id: int) -> list[str]:
        response = httpx.get(
            f"{self.base_url}/git/repositories/{repo_id}/pullRequests/{pr_id}/workitems",
            headers=self.headers,
            params={"api-version": "7.0"},
            timeout=10,
        )
        response.raise_for_status()
        refs = response.json().get("value", [])
        if not refs:
            return []

        ids = ",".join(str(item["id"]) for item in refs)
        response = httpx.get(
            f"{self.base_url}/wit/workitems",
            headers=self.headers,
            params={"ids": ids, "fields": "System.Title,System.WorkItemType", "api-version": "7.0"},
            timeout=10,
        )
        response.raise_for_status()
        return [
            f"BLI {item['id']}: {item['fields']['System.Title']}"
            for item in response.json().get("value", [])
            if item["fields"].get("System.WorkItemType") == "Product Backlog Item"
        ]

    def _user_has_comment(self, repo_id: str, pr_id: int, user_id: str) -> bool:
        response = httpx.get(
            f"{self.base_url}/git/repositories/{repo_id}/pullRequests/{pr_id}/threads",
            headers=self.headers,
            params={"api-version": "7.0"},
            timeout=10,
        )
        response.raise_for_status()
        for thread in response.json().get("value", []):
            for comment in thread.get("comments", []):
                if comment.get("author", {}).get("id") == user_id:
                    return True
        return False

    def _get_product_backlog_items(self, target_date: date) -> list[tuple[str, str]]:
        day_start = f"{target_date}T00:00:00Z"
        day_end = f"{target_date + timedelta(days=1)}T00:00:00Z"

        wiql = {
            "query": (
                "SELECT [System.Id], [System.Title] FROM WorkItems "
                "WHERE [System.WorkItemType] = 'Product Backlog Item' "
                f"AND [System.ChangedDate] >= '{day_start}' "
                f"AND [System.ChangedDate] < '{day_end}' "
                "AND [System.ChangedBy] = @Me"
            )
        }

        response = httpx.post(
            f"{self.base_url}/wit/wiql",
            headers=self.headers,
            json=wiql,
            params={"api-version": "7.0"},
            timeout=10,
        )
        response.raise_for_status()

        work_item_refs = response.json().get("workItems", [])
        if not work_item_refs:
            return []

        ids = ",".join(str(item["id"]) for item in work_item_refs)
        response = httpx.get(
            f"{self.base_url}/wit/workitems",
            headers=self.headers,
            params={"ids": ids, "fields": "System.Title", "api-version": "7.0"},
            timeout=10,
        )
        response.raise_for_status()

        return [
            (f"BLI {item['id']}: {item['fields']['System.Title']}", "bli")
            for item in response.json().get("value", [])
        ]