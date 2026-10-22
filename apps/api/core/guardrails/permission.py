"""Permission Layer implementing propose-only gating for destructive and outbound actions."""
import json
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from apps.api.core.guardrails.policy import GuardrailPolicy, default_policy
from apps.api.core.guardrails.verdicts import GuardrailVerdict

logger = logging.getLogger(__name__)

ActionType = Literal[
    "send_email",
    "delete_jira_issue",
    "transition_jira_issue",
    "edit_notion_page",
    "delete_memory",
    "other_destructive",
]

ActionStatus = Literal["pending", "confirmed", "rejected", "expired"]


class PendingAction(BaseModel):
    """Represents a proposed destructive or outbound action requiring human confirmation."""
    token: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:12]}")
    action_type: ActionType
    summary: str
    target_system: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str
    status: ActionStatus = "pending"
    confirmed_at: str | None = None
    execution_log: str | None = None


# Patterns indicating outbound or destructive actions
RISKY_ACTION_PATTERNS = [
    ("send_email", "gmail", re.compile(r"\b(?:send|draft\s+and\s+send|forward|dispatch)\s+(?:an?\s+)?(?:email|message|reply)(?:\s+from\s+.*?)?\s+to\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|[A-Za-z]+)", re.IGNORECASE)),
    ("delete_jira_issue", "jira", re.compile(r"\b(?:delete|drop|remove)\s+(?:(?:jira\s+)?(?:issue|ticket|task)\s+)?(PROJ-\d+|table\s+[A-Za-z0-9_]+|[A-Za-z0-9_-]+)", re.IGNORECASE)),
    ("transition_jira_issue", "jira", re.compile(r"\b(?:close|resolve|reopen|transition|move\s+to\s+done)\s+(?:(?:jira\s+)?(?:issue|ticket|task)\s+)?(PROJ-\d+)", re.IGNORECASE)),
    ("edit_notion_page", "notion", re.compile(r"\b(?:edit|modify|update|overwrite|delete)\s+(?:notion\s+)?(?:page|prd|roadmap|task)\b", re.IGNORECASE)),
    ("delete_memory", "memory", re.compile(r"\b(?:wipe|clear|purge|delete|drop\s+table)(?:\s+all)?\s+(?:memory|memories|facts|persistent_facts|database|past\s+q&a)\b", re.IGNORECASE)),
]


class PermissionLayer:
    """Classifies user requests as read-only or risky. Risky actions pause until explicitly confirmed."""

    def __init__(self, policy: GuardrailPolicy | None = None):
        self.policy = policy or default_policy
        self._actions: dict[str, PendingAction] = {}
        self.outbox_dir = Path(self.policy.outbox_dir)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    def classify_and_propose(
        self, query: str, policy: GuardrailPolicy | None = None
    ) -> tuple[bool, GuardrailVerdict, PendingAction | None]:
        """Classify query. If read-only, allow. If risky, create a PendingAction and return pause verdict."""
        effective_policy = policy or self.policy
        if not effective_policy.permission_guard_enabled or not query:
            return True, GuardrailVerdict.allow("permission_layer", "Permission layer disabled"), None

        # Check for risky intents
        for action_type, target_system, pattern in RISKY_ACTION_PATTERNS:
            match = pattern.search(query)
            if match:
                matched_target = match.group(1) if match.groups() else "target"
                now = datetime.now(UTC)
                expires = now + timedelta(seconds=effective_policy.action_token_expiry_seconds)

                if action_type == "send_email":
                    summary = f"Send outbound email to '{matched_target}' via Gmail"
                elif action_type == "delete_jira_issue":
                    summary = f"Permanently delete Jira issue '{matched_target}'"
                elif action_type == "transition_jira_issue":
                    summary = f"Transition status of Jira issue '{matched_target}'"
                elif action_type == "edit_notion_page":
                    summary = f"Edit/modify Notion documentation page '{matched_target}'"
                elif action_type == "delete_memory":
                    summary = "Purge all long-term memories and persistent facts"
                else:
                    summary = f"Execute proposed {action_type} on {target_system}"

                action = PendingAction(
                    action_type=action_type,  # type: ignore
                    summary=summary,
                    target_system=target_system,
                    payload={"query": query, "matched_target": matched_target},
                    created_at=now.isoformat(),
                    expires_at=expires.isoformat(),
                )

                self._actions[action.token] = action
                self._dispatch_outbox_simulation(action)

                verdict = GuardrailVerdict.pause(
                    name="permission_layer",
                    reason=f"Action paused: {summary}. Human confirmation required.",
                    token=action.token,
                    metadata={"pending_action": action.model_dump()},
                )
                return False, verdict, action

        return True, GuardrailVerdict.allow("permission_layer", "Read-only query allowed to proceed"), None

    def _dispatch_outbox_simulation(self, action: PendingAction):
        """Simulate outbound confirmation dispatch by writing to ./outbox/."""
        proposal_file = self.outbox_dir / f"proposal_{action.token}.json"
        data = {
            "notification": "ACTION CONFIRMATION REQUIRED",
            "token": action.token,
            "action_type": action.action_type,
            "target_system": action.target_system,
            "summary": action.summary,
            "created_at": action.created_at,
            "expires_at": action.expires_at,
            "confirmation_url": f"http://localhost:8000/api/actions/{action.token}/confirm",
            "payload": action.payload,
        }
        with open(proposal_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Dispatched simulated confirmation email to {proposal_file}")

    def confirm_action(self, token: str) -> tuple[bool, str]:
        """Confirm a pending action and simulate execution."""
        action = self._actions.get(token)
        if not action:
            return False, f"Action token '{token}' not found."

        if action.status != "pending":
            return False, f"Action already resolved with status '{action.status}'."

        now = datetime.now(UTC)
        if datetime.fromisoformat(action.expires_at) < now:
            action.status = "expired"
            return False, f"Action token '{token}' has expired."

        # Simulate execution in demo mode
        action.status = "confirmed"
        action.confirmed_at = now.isoformat()
        action.execution_log = f"Simulated execution succeeded: {action.summary} recorded in audit log."

        exec_file = self.outbox_dir / f"executed_{action.token}.json"
        with open(exec_file, "w", encoding="utf-8") as f:
            json.dump(action.model_dump(), f, indent=2)

        return True, action.execution_log

    def reject_action(self, token: str) -> tuple[bool, str]:
        """Reject and cancel a pending action."""
        action = self._actions.get(token)
        if not action:
            return False, f"Action token '{token}' not found."

        if action.status != "pending":
            return False, f"Action already resolved with status '{action.status}'."

        action.status = "rejected"
        action.execution_log = "Action rejected by human operator. Execution cancelled."
        return True, action.execution_log

    def get_action(self, token: str) -> PendingAction | None:
        return self._actions.get(token)

    def list_pending(self) -> list[PendingAction]:
        now = datetime.now(UTC)
        pending = []
        for a in self._actions.values():
            if a.status == "pending":
                if datetime.fromisoformat(a.expires_at) < now:
                    a.status = "expired"
                else:
                    pending.append(a)
        return pending

    def clear(self):
        self._actions.clear()


default_permission_layer = PermissionLayer()
