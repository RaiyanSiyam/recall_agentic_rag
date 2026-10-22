"""Unit tests for the Propose-Only Permission Layer and Actions API."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.core.guardrails.permission import PendingAction, PermissionLayer
from apps.api.core.guardrails.policy import GuardrailPolicy
from apps.api.main import app

client = TestClient(app)


@pytest.fixture
def temp_permission_layer(tmp_path: Path):
    policy = GuardrailPolicy(outbox_dir=str(tmp_path / "outbox"))
    return PermissionLayer(policy=policy)


def test_permission_read_only_allowed(temp_permission_layer: PermissionLayer):
    allowed, verdict, action = temp_permission_layer.classify_and_propose(
        "What are the quarterly deliverables for Project X?"
    )
    assert allowed is True
    assert verdict.action == "allow"
    assert action is None


def test_permission_send_email_paused(temp_permission_layer: PermissionLayer):
    allowed, verdict, action = temp_permission_layer.classify_and_propose(
        "Please send email to alice@example.com with the sprint summary."
    )
    assert allowed is False
    assert verdict.action == "pause"
    assert action is not None
    assert action.action_type == "send_email"
    assert "alice@example.com" in action.summary
    assert action.status == "pending"

    # Verify outbox proposal written
    proposal_file = temp_permission_layer.outbox_dir / f"proposal_{action.token}.json"
    assert proposal_file.exists()
    with open(proposal_file, encoding="utf-8") as f:
        data = json.load(f)
        assert data["token"] == action.token
        assert data["action_type"] == "send_email"


def test_permission_delete_jira_paused(temp_permission_layer: PermissionLayer):
    allowed, verdict, action = temp_permission_layer.classify_and_propose(
        "Delete issue PROJ-123 immediately"
    )
    assert allowed is False
    assert verdict.action == "pause"
    assert action is not None
    assert action.action_type == "delete_jira_issue"
    assert "PROJ-123" in action.summary


def test_permission_transition_jira_paused(temp_permission_layer: PermissionLayer):
    allowed, verdict, action = temp_permission_layer.classify_and_propose(
        "Close issue PROJ-999 and mark as completed"
    )
    assert allowed is False
    assert verdict.action == "pause"
    assert action is not None
    assert action.action_type == "transition_jira_issue"


def test_permission_edit_notion_paused(temp_permission_layer: PermissionLayer):
    allowed, verdict, action = temp_permission_layer.classify_and_propose(
        "Edit notion page architecture doc to add details"
    )
    assert allowed is False
    assert verdict.action == "pause"
    assert action is not None
    assert action.action_type == "edit_notion_page"


def test_permission_delete_memory_paused(temp_permission_layer: PermissionLayer):
    allowed, verdict, action = temp_permission_layer.classify_and_propose(
        "Wipe all memory permanently"
    )
    assert allowed is False
    assert verdict.action == "pause"
    assert action is not None
    assert action.action_type == "delete_memory"


def test_permission_confirm_action(temp_permission_layer: PermissionLayer):
    _, _, action = temp_permission_layer.classify_and_propose(
        "Send email to bob@example.com"
    )
    assert action is not None
    token = action.token

    success, msg = temp_permission_layer.confirm_action(token)
    assert success is True
    assert "Simulated execution succeeded" in msg

    updated = temp_permission_layer.get_action(token)
    assert updated is not None
    assert updated.status == "confirmed"
    assert updated.confirmed_at is not None

    exec_file = temp_permission_layer.outbox_dir / f"executed_{token}.json"
    assert exec_file.exists()


def test_permission_reject_action(temp_permission_layer: PermissionLayer):
    _, _, action = temp_permission_layer.classify_and_propose(
        "Delete ticket PROJ-888"
    )
    assert action is not None
    token = action.token

    success, msg = temp_permission_layer.reject_action(token)
    assert success is True
    assert "cancelled" in msg

    updated = temp_permission_layer.get_action(token)
    assert updated is not None
    assert updated.status == "rejected"


def test_permission_expiry(temp_permission_layer: PermissionLayer):
    # Set expiration in past
    action = PendingAction(
        action_type="send_email",
        summary="Test expired",
        target_system="gmail",
        expires_at=(datetime.now(UTC) - timedelta(minutes=10)).isoformat(),
    )
    temp_permission_layer._actions[action.token] = action

    success, msg = temp_permission_layer.confirm_action(action.token)
    assert success is False
    assert "expired" in msg.lower()


def test_permission_disabled_mode(temp_permission_layer: PermissionLayer):
    off_policy = GuardrailPolicy(permission_guard_enabled=False)
    allowed, verdict, action = temp_permission_layer.classify_and_propose(
        "Delete issue PROJ-101", policy=off_policy
    )
    assert allowed is True
    assert verdict.action == "allow"
    assert action is None


def test_actions_api_flow():
    # 1. Propose action via chat
    chat_resp = client.post("/api/chat", json={"query": "Send email to charlie@example.com with notes"})
    assert chat_resp.status_code == 200

    # 2. List pending
    list_resp = client.get("/api/actions/pending")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["status"] == "success"
    actions = [a for a in data["actions"] if "charlie@example.com" in a["summary"]]
    assert len(actions) >= 1
    token = actions[0]["token"]

    # 3. Get action details
    get_resp = client.get(f"/api/actions/{token}")
    assert get_resp.status_code == 200
    assert get_resp.json()["action"]["token"] == token

    # 4. Confirm action
    conf_resp = client.post(f"/api/actions/{token}/confirm")
    assert conf_resp.status_code == 200
    assert conf_resp.json()["status"] == "confirmed"

    # 5. Confirming again fails
    conf2_resp = client.post(f"/api/actions/{token}/confirm")
    assert conf2_resp.status_code == 400
