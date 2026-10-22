"""Memory Guard protecting persistent storage against memory poisoning and indirect injection."""
import logging
import re

from apps.api.core.guardrails.policy import GuardrailPolicy, default_policy
from apps.api.core.guardrails.redaction import RedactionEngine, default_redaction_engine
from apps.api.core.guardrails.verdicts import GuardrailVerdict

logger = logging.getLogger(__name__)

# Patterns indicative of instruction injection or poisoning attacks targeting memory
POISONING_PATTERNS = [
    re.compile(r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|system|security)\b", re.IGNORECASE),
    re.compile(r"\b(?:you\s+must|always|never)\s+(?:say|respond|tell|answer|reveal|exfiltrate|send|print|transfer|execute|approve)\b", re.IGNORECASE),
    re.compile(r"\b(?:act\s+as|pretend\s+to\s+be|become|grant)\s+(?:dan|developer\s+mode|unrestricted|god\s+mode|root|admin)\b", re.IGNORECASE),
    re.compile(r"\b(?:disregard|ignore|bypass|override|disable)\s+(?:all\s+)?(?:security|policy|policies|approvals|checks|guardrails|verifier)\b", re.IGNORECASE),
    re.compile(r"\b(?:security\s+checks\s+are\s+disabled|bypass\s+all\s+(?:[a-zA-Z]+\s+)?approvals|god\s+mode|no\s+actions\s+require\s+confirmation)\b", re.IGNORECASE),
    re.compile(r"\b(?:system\s+prompt|system\s+instructions|canary\s+token|os\.system|webhook|arbitrary\s+code)\b", re.IGNORECASE),
    re.compile(r"<\s*script\b|javascript\s*:|data\s*:text/html", re.IGNORECASE),
    re.compile(r"\b(?:delete|drop|wipe|purge)\s+(?:database|memory|table|all|files)\b", re.IGNORECASE),
    re.compile(r"\b(?:transfer\s+(?:company\s+)?funds|exfiltrate|confidential\s+snippets|\[SYSTEM_HACKED\])\b", re.IGNORECASE),
    re.compile(r"<<<|>>>|\[SYSTEM\]|\[INST\]", re.IGNORECASE),
]

# Words that indicate imperative instructions rather than passive facts
INSTRUCTION_WORDS = re.compile(
    r"\b(?:must\s+always|ignore|bypass|exfiltrate|execute|curl|fetch|eval|os\.system|sh\b|bash\b)",
    re.IGNORECASE,
)


class MemoryGuard:
    """Hardened write-policy guard ensuring only legitimate user facts enter long-term storage."""

    def __init__(
        self,
        policy: GuardrailPolicy | None = None,
        redaction_engine: RedactionEngine | None = None,
    ):
        self.policy = policy or default_policy
        self.redaction_engine = redaction_engine or default_redaction_engine

    def validate_and_sanitize_fact(
        self,
        fact: str,
        source: str = "user_statement",
        policy: GuardrailPolicy | None = None,
    ) -> tuple[bool, str, GuardrailVerdict]:
        """
        Validate fact before persisting to long-term memory.
        Returns:
            allowed: bool (False if poisoning attempt or invalid)
            sanitized_fact: str (redacted and cleaned)
            verdict: GuardrailVerdict
        """
        pol = policy or self.policy
        clean_fact = fact.strip()

        if not clean_fact:
            return False, "", GuardrailVerdict.block("memory_guard", "Cannot persist empty fact")

        if not pol.memory_guard_enabled:
            return True, clean_fact, GuardrailVerdict.allow("memory_guard", "Memory guard disabled")

        # 1. LENGTH CHECK (Reject bloated injection payloads)
        if len(clean_fact) > 300:
            return (
                False,
                clean_fact,
                GuardrailVerdict.block(
                    "memory_guard",
                    f"Fact rejected: excessive length ({len(clean_fact)} > 300 chars)",
                    matched_rules=["excessive_fact_length"],
                ),
            )

        # 2. INJECTION / POISONING PATTERN DETECTION
        for pattern in POISONING_PATTERNS:
            if pattern.search(clean_fact):
                logger.warning(f"Memory poisoning attempt blocked: '{clean_fact[:60]}...'")
                return (
                    False,
                    clean_fact,
                    GuardrailVerdict.block(
                        "memory_guard",
                        "Fact rejected: contains prompt injection or instruction override directive",
                        matched_rules=["memory_poisoning_injection"],
                    ),
                )

        # 3. SOURCE HARDENING POLICY
        # Only direct user statements or explicit manual additions can become durable memory
        # External tool extracts containing imperative instructions are strictly forbidden
        if source not in ("user_statement", "manual"):
            if INSTRUCTION_WORDS.search(clean_fact):
                logger.warning(f"Imperative instruction from untrusted source '{source}' blocked from memory.")
                return (
                    False,
                    clean_fact,
                    GuardrailVerdict.block(
                        "memory_guard",
                        f"Fact rejected: untrusted source '{source}' cannot store imperative instructions",
                        matched_rules=["untrusted_source_instruction"],
                    ),
                )

        # 4. REDACTION BEFORE STORAGE
        sanitized_fact = clean_fact
        if pol.redaction_enabled:
            redacted_fact, _ = self.redaction_engine.redact(clean_fact)
            sanitized_fact = redacted_fact

        return (
            True,
            sanitized_fact,
            GuardrailVerdict.allow(
                "memory_guard",
                "Fact verified and approved for long-term storage",
                metadata={"source": source, "sanitized_length": len(sanitized_fact)},
            ),
        )


default_memory_guard = MemoryGuard()
