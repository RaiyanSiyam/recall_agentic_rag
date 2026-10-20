"""Gmail MCP Server supporting both demo mode (realistic fixture) and live mode (Gmail API)."""
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
    name="gmail-server",
    title="Gmail MCP Server",
    instructions="Provides live or demo search and inspection of Gmail threads, messages, and executive updates.",
)


def _load_demo_data() -> dict[str, Any]:
    with open(DEMO_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@server.tool(name="search_emails", description="Search Gmail messages and threads by keyword or subject query.")
async def search_emails(query: str, max_results: int = 5) -> str:
    """Search emails by query string."""
    query_lower = query.lower()

    if DATA_MODE == "live":
        try:
            from .live_client import GmailLiveClient
            client = GmailLiveClient()
            results = client.search_emails(query, max_results=max_results)
            return sanitize_text(json.dumps(results, indent=2))
        except Exception as e:
            return f"Error connecting to live Gmail API: {e}. Falling back to demo data."

    # Demo Mode: Keyword search across subject, snippet, body, and sender
    data = _load_demo_data()
    messages = data.get("messages", [])
    matched = []

    # Tokenize query for flexible multi-keyword matching
    keywords = [k.strip() for k in query_lower.split() if len(k.strip()) > 2]

    for msg in messages:
        text_blob = f"{msg['subject']} {msg['snippet']} {msg['body']} {msg['from']}".lower()
        if not keywords:
            matched.append(msg)
        elif any(k in text_blob for k in keywords):
            matched.append(msg)

    # If no strict keyword matches, return all Project X messages as baseline
    if not matched:
        matched = messages

    matched = matched[:max_results]

    formatted_items = []
    for m in matched:
        formatted_items.append({
            "message_id": m["id"],
            "thread_id": m["thread_id"],
            "from": m["from"],
            "date": m["date"],
            "subject": m["subject"],
            "snippet": sanitize_text(m["snippet"]),
            "url": f"https://mail.google.com/mail/u/0/#inbox/{m['id']}",
        })

    return json.dumps({
        "source": "gmail",
        "query": query,
        "count": len(formatted_items),
        "messages": formatted_items,
    }, indent=2)


@server.tool(name="get_email", description="Retrieve the full body and metadata of a specific email message by its ID.")
async def get_email(message_id: str) -> str:
    """Retrieve full content of a specific email message."""
    if DATA_MODE == "live":
        try:
            from .live_client import GmailLiveClient
            client = GmailLiveClient()
            detail = client.get_email(message_id)
            if not detail:
                return f"Message {message_id} not found."
            return sanitize_text(json.dumps(detail, indent=2))
        except Exception as e:
            return f"Error retrieving email from live Gmail: {e}"

    data = _load_demo_data()
    for msg in data.get("messages", []):
        if msg["id"] == message_id:
            return json.dumps({
                "source": "gmail",
                "message_id": msg["id"],
                "thread_id": msg["thread_id"],
                "from": msg["from"],
                "to": msg["to"],
                "date": msg["date"],
                "subject": msg["subject"],
                "body": sanitize_text(msg["body"]),
                "url": f"https://mail.google.com/mail/u/0/#inbox/{msg['id']}",
            }, indent=2)

    return f"Message with ID '{message_id}' not found."


@server.tool(name="list_recent_emails", description="List recent incoming emails related to projects and executive steering.")
async def list_recent_emails(limit: int = 5) -> str:
    """List recent emails."""
    return await search_emails(query="", max_results=limit)


if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run_stdio_async())
