"""Live API client for Notion (used when DATA_MODE=live)."""
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NotionLiveClient:
    """Client for official Notion REST API."""

    def __init__(self):
        self.api_key = os.getenv("NOTION_API_KEY", "")
        self.database_id = os.getenv("NOTION_DATABASE_ID", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    async def query_database(self, filter_params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self.api_key or not self.database_id:
            raise RuntimeError("NOTION_API_KEY and NOTION_DATABASE_ID must be set in live mode.")

        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = filter_params or {}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for row in data.get("results", []):
                props = row.get("properties", {})
                title_prop = props.get("Name", {}).get("title", [])
                title = title_prop[0]["plain_text"] if title_prop else "Untitled"
                status = props.get("Status", {}).get("select", {}).get("name", "Unknown")
                results.append({
                    "id": row["id"],
                    "url": row.get("url", ""),
                    "title": title,
                    "status": status,
                })
            return results

    async def search_pages(self, query: str) -> list[dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("NOTION_API_KEY must be set in live mode.")

        url = "https://api.notion.com/v1/search"
        payload = {"query": query, "page_size": 5}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            resp.raise_for_status()
            return resp.json().get("results", [])
