"""Jira MCP Server supporting both demo mode (seeded blockers, changed deadlines) and live mode."""
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
    name="jira-server",
    title="Jira MCP Server",
    instructions="Provides live or demo search and inspection of Jira sprint issues, blockers, bug reports, and changed deadlines.",
)


def _load_demo_data() -> dict[str, Any]:
    with open(DEMO_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@server.tool(
    name="search_issues",
    description="Search Jira issues by keyword, blocker status, or issue status (e.g. 'Open', 'In Progress', 'Done').",
)
async def search_issues(
    query: str = "",
    is_blocker: bool | None = None,
    status: str = "",
) -> str:
    """Search Jira issues."""
    if DATA_MODE == "live":
        try:
            from .live_client import JiraLiveClient
            client = JiraLiveClient()
            jql = f"project = {client.project_key}"
            if query:
                jql += f" AND text ~ '{query}'"
            if is_blocker:
                jql += " AND priority in ('Highest', 'Blocker')"
            results = await client.search_issues(jql)
            return sanitize_text(json.dumps(results, indent=2))
        except Exception as e:
            return f"Error connecting to live Jira API: {e}. Falling back to demo data."

    data = _load_demo_data()
    issues = data.get("issues", [])
    results = []

    q_lower = query.lower()
    status_lower = status.lower()

    for issue in issues:
        # Blocker filter
        if is_blocker is not None and issue.get("is_blocker", False) != is_blocker:
            continue

        # Status filter
        if status_lower and status_lower not in issue.get("status", "").lower():
            continue

        # Query filter
        if q_lower:
            blob = f"{issue['key']} {issue['summary']} {issue.get('description', '')} {issue.get('assignee', '')} {issue.get('blocker_details', '')} {issue.get('deadline_change_details', '')}".lower()
            if q_lower not in blob and not any(k in blob for k in q_lower.split() if len(k) > 2):
                continue

        results.append({
            "key": issue["key"],
            "summary": issue["summary"],
            "status": issue["status"],
            "priority": issue["priority"],
            "assignee": issue.get("assignee", "Unassigned"),
            "is_blocker": issue.get("is_blocker", False),
            "blocker_details": issue.get("blocker_details"),
            "deadline_changed": issue.get("deadline_changed", False),
            "deadline_change_details": issue.get("deadline_change_details"),
            "due_date": issue.get("due_date"),
            "description": sanitize_text(issue.get("description", "")),
            "url": f"https://atlassian.net/browse/{issue['key']}",
        })

    return json.dumps({
        "source": "jira",
        "project": data.get("project_key", "PROJ"),
        "total_issues_found": len(results),
        "issues": results,
    }, indent=2)


@server.tool(
    name="get_blockers",
    description="Retrieve all active blockers and highest-priority impeding issues reported for Project X.",
)
async def get_blockers() -> str:
    """Retrieve all critical blockers reported in Jira."""
    return await search_issues(is_blocker=True)


@server.tool(
    name="get_changed_deadlines",
    description="Retrieve all Jira issues that have had their due dates or delivery deadlines modified or rescheduled.",
)
async def get_changed_deadlines() -> str:
    """Retrieve issues with updated deadlines."""
    data = _load_demo_data()
    issues = data.get("issues", [])
    changed = []
    for issue in issues:
        if issue.get("deadline_changed"):
            changed.append({
                "key": issue["key"],
                "summary": issue["summary"],
                "status": issue["status"],
                "due_date": issue.get("due_date"),
                "previous_due_date": issue.get("previous_due_date"),
                "details": issue.get("deadline_change_details"),
                "url": f"https://atlassian.net/browse/{issue['key']}",
            })

    return json.dumps({
        "source": "jira",
        "count": len(changed),
        "changed_deadlines": changed,
    }, indent=2)


@server.tool(
    name="get_sprint_status",
    description="Get current active sprint overview, metrics, and state.",
)
async def get_sprint_status() -> str:
    """Get active sprint information."""
    data = _load_demo_data()
    sprint = data.get("sprint", {})
    issues = data.get("issues", [])
    statuses = {}
    for i in issues:
        st = i.get("status", "Unknown")
        statuses[st] = statuses.get(st, 0) + 1

    return json.dumps({
        "source": "jira",
        "sprint": sprint,
        "issue_breakdown": statuses,
        "total_issues": len(issues),
    }, indent=2)


@server.tool(
    name="get_issue",
    description="Retrieve full details for a specific Jira issue key (e.g. 'PROJ-102').",
)
async def get_issue(issue_key: str) -> str:
    """Retrieve full content of a specific Jira issue."""
    data = _load_demo_data()
    for issue in data.get("issues", []):
        if issue["key"].upper() == issue_key.upper():
            return json.dumps({
                "source": "jira",
                "key": issue["key"],
                "summary": issue["summary"],
                "status": issue["status"],
                "priority": issue["priority"],
                "assignee": issue.get("assignee"),
                "reporter": issue.get("reporter"),
                "is_blocker": issue.get("is_blocker", False),
                "blocker_details": issue.get("blocker_details"),
                "description": sanitize_text(issue.get("description", "")),
                "url": f"https://atlassian.net/browse/{issue['key']}",
            }, indent=2)

    return f"Issue with key '{issue_key}' not found."


if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run_stdio_async())
