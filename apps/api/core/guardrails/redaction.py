"""PII and Secret Redaction Engine with Luhn check, regex heuristics, and policy support."""
import re
from typing import Any

from apps.api.core.guardrails.policy import GuardrailPolicy, default_policy
from apps.api.core.guardrails.verdicts import GuardrailVerdict


def is_luhn_valid(card_number_str: str) -> bool:
    """Validate a card number string using the Luhn checksum algorithm."""
    digits_only = re.sub(r"\D", "", card_number_str)
    # Credit cards are 13 to 19 digits long (Visa, Mastercard, Amex, Discover, etc.)
    if len(digits_only) < 13 or len(digits_only) > 19:
        return False

    total = 0
    reverse_digits = digits_only[::-1]
    for i, char in enumerate(reverse_digits):
        d = int(char)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# Precompiled regex patterns
SSN_PATTERN = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")

# Formatted phone number with negative digit lookaround to avoid matching substrings of large IDs
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\([0-9]{3}\)[-.\s]?|[0-9]{3}[-.\s])[0-9]{3}[-.\s][0-9]{4}(?!\d)"
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Potential credit card candidate (13-19 digits with optional spaces/dashes)
CARD_CANDIDATE_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

# Secrets & API tokens
SECRET_PATTERNS = [
    ("OPENAI_KEY", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b")),
    ("ANTHROPIC_KEY", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GITHUB_TOKEN", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b")),
    ("SLACK_TOKEN", re.compile(r"\bxox[baprs]-[0-9A-Za-z_\-]{10,}\b")),
    ("JWT_TOKEN", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("GENERIC_KEY_ASSIGNMENT", re.compile(r"(?:api[_-]?key|access[_-]?token|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{16,})['\"]?", re.IGNORECASE)),
]


class RedactionEngine:
    """Masks PII and sensitive developer secrets before LLM context, memory writes, and logging."""

    def __init__(self, policy: GuardrailPolicy | None = None):
        self.policy = policy or default_policy

    def redact(self, text: str) -> tuple[str, GuardrailVerdict]:
        """Redact sensitive PII and secrets from text according to active policy."""
        if not self.policy.redaction_enabled or not text:
            return text, GuardrailVerdict.allow("redaction_engine", "Redaction disabled or empty text")

        redacted = text
        categories_found: set[str] = set()
        total_redactions = 0

        # 1. API Keys & Secrets
        if self.policy.redact_api_keys:
            for sec_name, pattern in SECRET_PATTERNS:
                if sec_name == "GENERIC_KEY_ASSIGNMENT":
                    def replace_val(m):
                        val = m.group(1)
                        return m.group(0).replace(val, "[REDACTED_API_KEY]")
                    new_text, count = pattern.subn(replace_val, redacted)
                else:
                    new_text, count = pattern.subn("[REDACTED_API_KEY]", redacted)
                if count > 0:
                    redacted = new_text
                    categories_found.add("API_KEY")
                    total_redactions += count

        # 2. Credit Cards (Luhn Check)
        if self.policy.redact_credit_cards:
            matches = list(CARD_CANDIDATE_PATTERN.finditer(redacted))
            # Process in reverse to maintain string index offsets
            for m in reversed(matches):
                candidate = m.group(0).strip()
                if is_luhn_valid(candidate):
                    start, end = m.span()
                    redacted = redacted[:start] + "[REDACTED_CREDIT_CARD]" + redacted[end:]
                    categories_found.add("CREDIT_CARD")
                    total_redactions += 1

        # 3. Social Security Numbers
        if self.policy.redact_ssn:
            redacted, count = SSN_PATTERN.subn("[REDACTED_SSN]", redacted)
            if count > 0:
                categories_found.add("SSN")
                total_redactions += count

        # 4. Email Addresses
        if self.policy.redact_emails:
            redacted, count = EMAIL_PATTERN.subn("[REDACTED_EMAIL]", redacted)
            if count > 0:
                categories_found.add("EMAIL")
                total_redactions += count

        # 5. Phone Numbers
        if self.policy.redact_phones:
            redacted, count = PHONE_PATTERN.subn("[REDACTED_PHONE]", redacted)
            if count > 0:
                categories_found.add("PHONE")
                total_redactions += count

        if total_redactions > 0:
            verdict = GuardrailVerdict.redact(
                name="redaction_engine",
                count=total_redactions,
                categories=sorted(categories_found),
                metadata={"redaction_count": total_redactions},
            )
        else:
            verdict = GuardrailVerdict.allow("redaction_engine", "No PII or secrets detected")

        return redacted, verdict

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact dictionary values."""
        clean: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, str):
                clean[k], _ = self.redact(v)
            elif isinstance(v, dict):
                clean[k] = self.redact_dict(v)
            elif isinstance(v, list):
                clean[k] = [
                    self.redact(item)[0] if isinstance(item, str)
                    else self.redact_dict(item) if isinstance(item, dict)
                    else item
                    for item in v
                ]
            else:
                clean[k] = v
        return clean


default_redaction_engine = RedactionEngine()
