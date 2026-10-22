"""Output Guardrail combining secondary PII/secret sweep, canary-token scanning, and leakage defense."""
import logging
import re

from apps.api.core.guardrails.canary import CanaryManager, default_canary_manager
from apps.api.core.guardrails.policy import GuardrailPolicy, default_policy
from apps.api.core.guardrails.redaction import RedactionEngine, default_redaction_engine
from apps.api.core.guardrails.verdicts import GuardrailVerdict

logger = logging.getLogger(__name__)

UNTRUSTED_ENVELOPE_PATTERN = re.compile(
    r"<<<UNTRUSTED_EXTERNAL_TOOL_EVIDENCE[^>]*>>>|<<<END_UNTRUSTED_EVIDENCE>>>|<<<END_EXTERNAL_TOOL_EVIDENCE>>>",
    re.IGNORECASE,
)


class OutputGuardrail:
    """Protects generated responses from canary token leakage, PII/secret leaks, and delimiter escapes."""

    def __init__(
        self,
        policy: GuardrailPolicy | None = None,
        canary_manager: CanaryManager | None = None,
        redaction_engine: RedactionEngine | None = None,
    ):
        self.policy = policy or default_policy
        self.canary_mgr = canary_manager or default_canary_manager
        self.redaction_engine = redaction_engine or default_redaction_engine

    def evaluate_and_sanitize(
        self,
        text: str,
        policy: GuardrailPolicy | None = None,
    ) -> tuple[bool, str, list[GuardrailVerdict]]:
        """
        Evaluate generated output against canary leaks and sensitive data disclosure.
        Returns:
            allowed: bool (False if canary leaked)
            sanitized_text: str (clean text or safe block response)
            verdicts: list[GuardrailVerdict]
        """
        pol = policy or self.policy
        verdicts: list[GuardrailVerdict] = []

        if not text:
            return True, text, [GuardrailVerdict.allow("output_guard", "Empty text allowed")]

        if not pol.output_guard_enabled:
            return True, text, [GuardrailVerdict.allow("output_guard", "Output guard disabled")]

        # 1. CANARY TOKEN SCAN (Strict Leakage Defense)
        if pol.canary_check_enabled:
            canary_verdict = self.canary_mgr.scan_output(text)
            verdicts.append(canary_verdict)
            if not canary_verdict.allowed:
                logger.error("Canary token leak detected in generated response! Blocking output.")
                blocked_msg = "Execution blocked: Confidential security token leakage prevented by Output Guardrail."
                return False, blocked_msg, verdicts

        # 2. SECONDARY PII / SECRET REDACTION SWEEP
        sanitized_text = text
        if pol.redaction_enabled:
            redacted_text, redaction_verdict = self.redaction_engine.redact(sanitized_text)
            if redaction_verdict.action == "redact":
                verdicts.append(redaction_verdict)
                sanitized_text = redacted_text

        # 3. STRIP UNTRUSTED DELIMITER ENVELOPES IF LEAKED
        if UNTRUSTED_ENVELOPE_PATTERN.search(sanitized_text):
            sanitized_text = UNTRUSTED_ENVELOPE_PATTERN.sub("", sanitized_text)
            sanitized_text = re.sub(r"  +", " ", sanitized_text).strip()
            verdicts.append(
                GuardrailVerdict(
                    allowed=True,
                    action="redact",
                    guardrail_name="output_delimiter_guard",
                    reasons=["Stripped internal untrusted evidence delimiter tokens from output"],
                    matched_rules=["internal_delimiter_leak"],
                )
            )

        verdicts.append(GuardrailVerdict.allow("output_guard", "Output passed all security checks"))

        return True, sanitized_text, verdicts
