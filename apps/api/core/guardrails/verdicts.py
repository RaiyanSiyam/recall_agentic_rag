"""Typed Verdict models for all guardrails in the hardened pipeline."""
from typing import Any, Literal

from pydantic import BaseModel, Field

GuardrailAction = Literal["allow", "block", "redact", "pause"]


class GuardrailVerdict(BaseModel):
    """Standardized verdict returned by every guardrail layer."""
    allowed: bool = Field(description="Whether the request/data is permitted to proceed")
    action: GuardrailAction = Field(description="Action taken: allow, block, redact, or pause")
    guardrail_name: str = Field(description="Identifier of the guardrail module")
    reasons: list[str] = Field(default_factory=list, description="Human-readable explanation of the verdict")
    matched_rules: list[str] = Field(default_factory=list, description="Identifiers of specific rules or patterns triggered")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context (e.g. pending action token, counts)")

    @classmethod
    def allow(cls, name: str, reason: str = "Passed all checks", metadata: dict[str, Any] | None = None) -> "GuardrailVerdict":
        return cls(
            allowed=True,
            action="allow",
            guardrail_name=name,
            reasons=[reason] if reason else [],
            metadata=metadata or {},
        )

    @classmethod
    def block(cls, name: str, reason: str, matched_rules: list[str] | None = None, metadata: dict[str, Any] | None = None) -> "GuardrailVerdict":
        return cls(
            allowed=False,
            action="block",
            guardrail_name=name,
            reasons=[reason],
            matched_rules=matched_rules or [],
            metadata=metadata or {},
        )

    @classmethod
    def pause(cls, name: str, reason: str, token: str, metadata: dict[str, Any] | None = None) -> "GuardrailVerdict":
        meta = metadata or {}
        meta["confirmation_token"] = token
        return cls(
            allowed=False,
            action="pause",
            guardrail_name=name,
            reasons=[reason],
            metadata=meta,
        )

    @classmethod
    def redact(cls, name: str, count: int, categories: list[str], metadata: dict[str, Any] | None = None) -> "GuardrailVerdict":
        return cls(
            allowed=True,
            action="redact",
            guardrail_name=name,
            reasons=[f"Redacted {count} sensitive item(s) across {', '.join(categories)}"],
            matched_rules=categories,
            metadata=metadata or {"redaction_count": count},
        )
