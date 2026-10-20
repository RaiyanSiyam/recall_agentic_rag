"""Observability traces endpoints."""
from fastapi import APIRouter, HTTPException

from apps.api.core.tracer import global_tracer

router = APIRouter(prefix="/api/traces", tags=["Traces"])


@router.get("")
async def list_traces():
    """List recent agent run traces."""
    return {"traces": global_tracer.list_all()}


@router.get("/{trace_id}")
async def get_trace(trace_id: str):
    """Retrieve full trace details for a specific run."""
    trace = global_tracer.get(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace.model_dump()
