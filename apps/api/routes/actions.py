"""Endpoints for managing and confirming proposed risky actions."""
from fastapi import APIRouter, HTTPException

from apps.api.core.guardrails.permission import default_permission_layer

router = APIRouter(prefix="/api/actions", tags=["Actions"])


@router.get("/pending")
async def list_pending_actions():
    """List all active actions awaiting human confirmation."""
    pending = default_permission_layer.list_pending()
    return {
        "status": "success",
        "count": len(pending),
        "actions": [a.model_dump() for a in pending],
    }


@router.get("/{token}")
async def get_action_details(token: str):
    """Retrieve details and status for a specific action token."""
    action = default_permission_layer.get_action(token)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action token '{token}' not found.")
    return {"status": "success", "action": action.model_dump()}


@router.post("/{token}/confirm")
async def confirm_action(token: str):
    """Confirm and execute a proposed action with a valid token."""
    success, msg = default_permission_layer.confirm_action(token)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    action = default_permission_layer.get_action(token)
    return {
        "status": "confirmed",
        "message": msg,
        "action": action.model_dump() if action else None,
    }


@router.post("/{token}/reject")
async def reject_action(token: str):
    """Reject and abort a proposed action."""
    success, msg = default_permission_layer.reject_action(token)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    action = default_permission_layer.get_action(token)
    return {
        "status": "rejected",
        "message": msg,
        "action": action.model_dump() if action else None,
    }
