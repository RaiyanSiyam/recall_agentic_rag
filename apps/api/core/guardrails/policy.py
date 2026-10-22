"""Guardrail Policy Configuration supporting strict, balanced, and off modes."""
import os
from typing import Literal

from pydantic import BaseModel, Field

GuardrailMode = Literal["strict", "balanced", "off"]


class GuardrailPolicy(BaseModel):
    """Central configuration for all guardrail stages in the pipeline."""
    mode: GuardrailMode = Field(default="strict", description="Active guardrail mode: strict, balanced, or off")

    # Feature toggles
    input_guard_enabled: bool = True
    permission_guard_enabled: bool = True
    retrieval_guard_enabled: bool = True
    redaction_enabled: bool = True
    citation_validation_enabled: bool = True
    output_guard_enabled: bool = True
    memory_guard_enabled: bool = True
    canary_check_enabled: bool = True

    # Redaction fine-tuning
    redact_ssn: bool = True
    redact_credit_cards: bool = True
    redact_api_keys: bool = True
    redact_emails: bool = True
    redact_phones: bool = True

    # Permission settings
    action_token_expiry_seconds: int = 900  # 15 minutes
    outbox_dir: str = "./outbox"

    @classmethod
    def from_mode(cls, mode: str | None = None) -> "GuardrailPolicy":
        selected_mode = (mode or os.getenv("GUARDRAIL_MODE", "strict")).lower()
        if selected_mode not in ("strict", "balanced", "off"):
            selected_mode = "strict"

        if selected_mode == "off":
            return cls(
                mode="off",
                input_guard_enabled=False,
                permission_guard_enabled=False,
                retrieval_guard_enabled=False,
                redaction_enabled=False,
                citation_validation_enabled=False,
                output_guard_enabled=False,
                memory_guard_enabled=False,
                canary_check_enabled=False,
                redact_ssn=False,
                redact_credit_cards=False,
                redact_api_keys=False,
                redact_emails=False,
                redact_phones=False,
            )
        elif selected_mode == "balanced":
            return cls(
                mode="balanced",
                input_guard_enabled=True,
                permission_guard_enabled=True,
                retrieval_guard_enabled=True,
                redaction_enabled=True,
                citation_validation_enabled=True,
                output_guard_enabled=True,
                memory_guard_enabled=True,
                canary_check_enabled=True,
                redact_emails=False,  # Allow standard email mentions in balanced mode
                redact_phones=True,
                redact_ssn=True,
                redact_credit_cards=True,
                redact_api_keys=True,
            )
        else:  # strict
            return cls(
                mode="strict",
                input_guard_enabled=True,
                permission_guard_enabled=True,
                retrieval_guard_enabled=True,
                redaction_enabled=True,
                citation_validation_enabled=True,
                output_guard_enabled=True,
                memory_guard_enabled=True,
                canary_check_enabled=True,
                redact_ssn=True,
                redact_credit_cards=True,
                redact_api_keys=True,
                redact_emails=True,
                redact_phones=True,
            )


# Default global policy instance
default_policy = GuardrailPolicy.from_mode()
