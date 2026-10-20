"""Live API client for Atlassian Jira Cloud (used when DATA_MODE=live)."""
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class JiraLiveClient:
    """Client for Jira Cloud REST API v3."""

    def __init__(self):
        self.domain = os.getenv("JIRA_DOMAIN", "")
        self.email = os.getenv("JIRA_USER_EMAIL", "")
        self.api_token = os.getenv("JIRA_API_TOKEN", "")
        self.project_key = os.getenv("JIRA_PROJECT_KEY", "PROJ")

    def _get_auth(self):
        if not self.domain or not self.email or not self.api_token:
            raise RuntimeError("JIRA_DOMAIN, JIRA_USER_EMAIL, and JIRA_API_TOKEN must be set in live mode.")
        return httpx.BasicAuth(self.email, self.api_token)

    async def search_issues(self, jql: str) -> list[dict[str, Any]]:
        auth = self._get_auth()
        url = f"https://{self.domain}/rest/api/3/search"
        params = {"jql": jql, "maxResults": 10}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, auth=auth, params=params)
            resp.raise_for_status()
            data = resp.json()
            issues = []
            for item in data.get("issues", []):
                fields = item.get("fields", {})
                issues.append({
                    "key": item["key"],
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", "Unknown"),
                    "priority": fields.get("priority", {}).get("name", "Medium"),
                    "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
                })
            return issues

    async def get_issue(self, issue_key: str) -> dict[str, Any] | None:
        auth = self._get_auth()
        url = f"https://{self.domain}/rest/api/3/issue/{issue_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, auth=auth)
            resp.raise_for_status()
            item = resp.json()
            fields = item.get("fields", {})
            return {
                "key": item["key"],
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", "Unknown"),
                "priority": fields.get("priority", {}).get("name", "Medium"),
                "description": fields.get("description", ""),
            }
