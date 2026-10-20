"""Shared models for MCP server tools."""
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class MCPToolResult(BaseModel):
    """Standardized tool response envelope."""
    success: bool = True
    source: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    query: str = ""
    error: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
