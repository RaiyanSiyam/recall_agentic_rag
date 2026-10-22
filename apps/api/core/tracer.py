"""Observability Tracer tracking runs, latencies, tokens, and verification loops."""
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class RunTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    query: str
    data_mode: str = "demo"
    llm_provider: str = "gemini"
    policy_mode: str = "strict"
    plan: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    verifications: list[dict[str, Any]] = Field(default_factory=list)
    guardrail_verdicts: list[dict[str, Any]] = Field(default_factory=list)
    security_blocked: bool = False
    block_reason: str | None = None
    redactions_count: int = 0
    action_paused: bool = False
    pending_action: dict[str, Any] | None = None
    evidence_count: int = 0
    citations_count: int = 0
    final_answer: str = ""
    duration_ms: float = 0.0
    failed_sources: list[str] = Field(default_factory=list)


class Tracer:
    """In-memory trace store with lookup and listing endpoints."""

    def __init__(self, max_traces: int = 50):
        self.max_traces = max_traces
        self._traces: dict[str, RunTrace] = {}

    def record(self, trace: RunTrace) -> RunTrace:
        self._traces[trace.trace_id] = trace
        # Evict oldest if exceeding limit
        if len(self._traces) > self.max_traces:
            oldest_id = next(iter(self._traces))
            del self._traces[oldest_id]
        return trace

    def get(self, trace_id: str) -> RunTrace | None:
        return self._traces.get(trace_id)

    def list_all(self) -> list[dict[str, Any]]:
        return [
            {
                "trace_id": t.trace_id,
                "timestamp": t.timestamp,
                "query": t.query,
                "policy_mode": t.policy_mode,
                "security_blocked": t.security_blocked,
                "redactions_count": t.redactions_count,
                "action_paused": t.action_paused,
                "pending_action": t.pending_action,
                "evidence_count": t.evidence_count,
                "citations_count": t.citations_count,
                "duration_ms": t.duration_ms,
                "failed_sources": t.failed_sources,
            }
            for t in reversed(list(self._traces.values()))
        ]


global_tracer = Tracer()
