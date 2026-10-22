"""Unit tests for the PII and Secret Redaction Engine."""
import pytest

from apps.api.core.guardrails.policy import GuardrailPolicy
from apps.api.core.guardrails.redaction import RedactionEngine, is_luhn_valid


class TestLuhnCheck:
    def test_valid_luhn_numbers(self):
        # Known test card numbers satisfying Luhn
        assert is_luhn_valid("4532 0151 1283 0366") is True
        assert is_luhn_valid("4532-0151-1283-0366") is True
        assert is_luhn_valid("4111111111111111") is True
        assert is_luhn_valid("378282246310005") is True  # 15-digit Amex

    def test_invalid_luhn_numbers(self):
        # Card numbers with invalid checksums
        assert is_luhn_valid("1234567890123456") is False
        assert is_luhn_valid("4111111111111112") is False
        assert is_luhn_valid("12345") is False  # Too short


class TestRedactionEngine:
    @pytest.fixture
    def engine(self):
        return RedactionEngine(policy=GuardrailPolicy.from_mode("strict"))

    def test_redact_ssn(self, engine):
        text = "Employee record: Alex Rivera SSN is 123-45-6789 in staging database."
        redacted, verdict = engine.redact(text)
        assert "[REDACTED_SSN]" in redacted
        assert "123-45-6789" not in redacted
        assert verdict.action == "redact"
        assert "SSN" in verdict.matched_rules

    def test_redact_credit_card_luhn_only(self, engine):
        # Valid Luhn card number must be redacted
        valid_card = "Card number: 4532 0151 1283 0366 on file."
        redacted, verdict = engine.redact(valid_card)
        assert "[REDACTED_CREDIT_CARD]" in redacted
        assert "4532 0151 1283 0366" not in redacted

        # Non-Luhn 16-digit string (e.g., commit hash or item ID) must NOT be redacted as credit card
        order_id = "Tracking order ID 1234567890123456 in warehouse."
        redacted_id, _ = engine.redact(order_id)
        assert "[REDACTED_CREDIT_CARD]" not in redacted_id
        assert "1234567890123456" in redacted_id

    def test_redact_api_keys_and_tokens(self, engine):
        text = (
            "OpenAI: sk-proj-12345678901234567890abcdef\n"
            "AWS: AKIA1234567890ABCDEF\n"
            "GitHub: ghp_123456789012345678901234567890123456\n"
            "Custom: api_key='secret-production-token-999'"
        )
        redacted, verdict = engine.redact(text)
        assert "sk-proj" not in redacted
        assert "AKIA" not in redacted
        assert "ghp_" not in redacted
        assert "secret-production-token-999" not in redacted
        assert redacted.count("[REDACTED_API_KEY]") == 4
        assert "API_KEY" in verdict.matched_rules

    def test_redact_email_and_phone(self, engine):
        text = "Contact Sarah Chen at sarah.chen@techcorp.internal or call 555-234-5678."
        redacted, verdict = engine.redact(text)
        assert "[REDACTED_EMAIL]" in redacted
        assert "[REDACTED_PHONE]" in redacted
        assert "sarah.chen@techcorp.internal" not in redacted
        assert "555-234-5678" not in redacted

    def test_balanced_mode_allows_emails(self):
        balanced_engine = RedactionEngine(policy=GuardrailPolicy.from_mode("balanced"))
        text = "Send email to sarah.chen@techcorp.internal with SSN 123-45-6789."
        redacted, verdict = balanced_engine.redact(text)
        assert "sarah.chen@techcorp.internal" in redacted  # Allowed in balanced mode
        assert "[REDACTED_SSN]" in redacted                # SSN still masked

    def test_off_mode_redacts_nothing(self):
        off_engine = RedactionEngine(policy=GuardrailPolicy.from_mode("off"))
        text = "My SSN is 123-45-6789 and key is sk-proj-12345678901234567890abcdef."
        redacted, verdict = off_engine.redact(text)
        assert redacted == text
        assert verdict.action == "allow"

    def test_redact_dict_recursive(self, engine):
        data = {
            "user": "David Kim",
            "metadata": {
                "email": "david.kim@techcorp.internal",
                "phone": "(555) 987-6543",
                "notes": ["Check SSN 123-45-6789", "clean item"],
            },
        }
        clean = engine.redact_dict(data)
        assert clean["metadata"]["email"] == "[REDACTED_EMAIL]"
        assert clean["metadata"]["phone"] == "[REDACTED_PHONE]"
        assert clean["metadata"]["notes"][0] == "Check SSN [REDACTED_SSN]"
        assert clean["metadata"]["notes"][1] == "clean item"
