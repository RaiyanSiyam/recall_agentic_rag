"""Notion MCP Server supporting both demo mode (seeded 12 tasks + PRDs) and live mode."""
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure parent directory is on sys.path for shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.mcpserver import MCPServer
from shared.sanitizer import sanitize_text

DATA_MODE = os.getenv("DATA_MODE", "demo").lower()
DEMO_DATA_PATH = Path(__file__).parent / "demo_data.json"

server = MCPServer(
    name="notion-server",
    title="Notion MCP Server",
    instructions="Provides live or demo querying of Notion databases, project deliverables, roadmaps, and PRD pages.",
)


def _load_demo_data() -> dict[str, Any]:
    with open(DEMO_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@server.tool(
    name="query_tasks",
    description="Query tasks from the Project X deliverables database. Can filter by keyword, status (e.g., 'In Progress', 'Done', 'Review', 'Not Started'), or assignee.",
)
async def query_tasks(
    query: str = "",
    status: str = "",
    assignee: str = "",
) -> str:
    """Query tasks in the Notion roadmap database."""
    if DATA_MODE == "live":
        try:
            from .live_client import NotionLiveClient
            client = NotionLiveClient()
            results = await client.query_database()
            return sanitize_text(json.dumps(results, indent=2))
        except Exception as e:
            return f"Error connecting to live Notion API: {e}. Falling back to demo data."

    data = _load_demo_data()
    tasks = data.get("tasks", [])
    results = []

    q_lower = query.lower()
    status_lower = status.lower()
    assignee_lower = assignee.lower()

    for t in tasks:
        # Filter checks
        if status_lower and status_lower not in t["status"].lower():
            continue
        if assignee_lower and assignee_lower not in t["assignee"].lower():
            continue

        if q_lower:
            blob = f"{t['task_code']} {t['title']} {t.get('notes', '')} {t.get('category', '')} {t.get('change_reason', '')}".lower()
            if q_lower not in blob and not any(k in blob for k in q_lower.split() if len(k) > 2):
                continue

        results.append({
            "task_id": t["id"],
            "task_code": t["task_code"],
            "title": t["title"],
            "status": t["status"],
            "assignee": t["assignee"],
            "due_date": t["due_date"],
            "previous_due_date": t.get("previous_due_date"),
            "deadline_changed": t.get("deadline_changed", False),
            "change_reason": t.get("change_reason"),
            "category": t.get("category"),
            "url": f"https://notion.so/workspace/{t['id']}",
        })

    return json.dumps({
        "source": "notion",
        "database": data.get("database_name", "Deliverables"),
        "total_tasks_found": len(results),
        "tasks": results,
    }, indent=2)


@server.tool(
    name="list_quarterly_deliverables",
    description="List all scheduled deliverables and tasks for Project X for the current quarter.",
)
async def list_quarterly_deliverables() -> str:
    """Returns the complete list of tasks planned this quarter."""
    return await query_tasks(query="")


@server.tool(
    name="search_pages",
    description="Search Notion documentation, PRDs, and charter pages by keyword.",
)
async def search_pages(query: str) -> str:
    """Search Notion documentation pages."""
    if DATA_MODE == "live":
        try:
            from .live_client import NotionLiveClient
            client = NotionLiveClient()
            results = await client.search_pages(query)
            return sanitize_text(json.dumps(results, indent=2))
        except Exception as e:
            return f"Error connecting to live Notion API: {e}. Falling back to demo data."

    data = _load_demo_data()
    pages = data.get("pages", [])
    results = []
    q_lower = query.lower()

    for p in pages:
        blob = f"{p['title']} {p['content']}".lower()
        if not q_lower or q_lower in blob or any(k in blob for k in q_lower.split() if len(k) > 2):
            results.append({
                "page_id": p["id"],
                "title": p["title"],
                "author": p["author"],
                "last_edited": p["last_edited"],
                "snippet": sanitize_text(p["content"][:300]),
                "url": f"https://notion.so/workspace/{p['id']}",
            })

    return json.dumps({
        "source": "notion",
        "query": query,
        "count": len(results),
        "pages": results,
    }, indent=2)


@server.tool(
    name="get_page",
    description="Retrieve the full content of a Notion page by its ID.",
)
async def get_page(page_id: str) -> str:
    """Retrieve full text of a Notion page."""
    data = _load_demo_data()
    for p in data.get("pages", []):
        if p["id"] == page_id:
            return json.dumps({
                "source": "notion",
                "page_id": p["id"],
                "title": p["title"],
                "author": p["author"],
                "content": sanitize_text(p["content"]),
                "url": f"https://notion.so/workspace/{p['id']}",
            }, indent=2)

    return f"Notion page '{page_id}' not found."


if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run_stdio_async())
