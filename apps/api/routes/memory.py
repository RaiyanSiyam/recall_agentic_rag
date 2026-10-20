"""Memory management endpoints for user control and transparency."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.config import settings
from apps.api.core.memory import MemoryManager

router = APIRouter(prefix="/api/memory", tags=["Memory"])
memory_mgr = MemoryManager(db_path=settings.SQLITE_DB_PATH)


class CreateFactRequest(BaseModel):
    fact_text: str
    category: str = "project_fact"
    source: str = "user_manual"


@router.get("")
async def get_memory():
    """Retrieve long-term facts and memory state."""
    facts = memory_mgr.long_term.list_facts()
    return {
        "status": "success",
        "total_facts": len(facts),
        "facts": facts,
    }


@router.post("")
async def add_memory_fact(req: CreateFactRequest):
    """Manually insert a user fact or priority constraint."""
    fact = memory_mgr.long_term.add_fact(
        fact_text=req.fact_text,
        category=req.category,
        source=req.source,
    )
    if not fact:
        raise HTTPException(status_code=400, detail="Failed to add memory fact")
    return {"status": "success", "fact": fact.model_dump()}


@router.delete("/{fact_id}")
async def delete_memory_fact(fact_id: int):
    """Delete a specific user fact by ID."""
    deleted = memory_mgr.long_term.delete_fact(fact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory fact not found")
    return {"status": "success", "message": f"Fact {fact_id} deleted"}


@router.delete("")
async def clear_all_memories():
    """Clear all long-term memories."""
    memory_mgr.long_term.clear_all()
    return {"status": "success", "message": "All memories cleared"}
