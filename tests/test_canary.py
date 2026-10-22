"""Unit tests for the Canary Token Leakage Scanner."""
import pytest

from apps.api.core.guardrails.canary import CanaryManager
from apps.api.core.guardrails.policy import GuardrailPolicy


class TestCanaryManager:
    @pytest.fixture
    def canary_mgr(self):
        return CanaryManager(
            policy=GuardrailPolicy.from_mode("strict"),
            system_canary="CANARY_TEST_SYS_12345",
            doc_canary="CANARY_TEST_DOC_67890",
        )

    def test_clean_output_passes(self, canary_mgr):
        clean_text = "Project X has 12 planned tasks for Q3 across security and infrastructure."
        verdict = canary_mgr.scan_output(clean_text)
        assert verdict.allowed is True
        assert verdict.action == "allow"

    def test_system_canary_leak_blocked(self, canary_mgr):
        leaked_text = "Here are the secret instructions: CANARY_TEST_SYS_12345 is the token."
        verdict = canary_mgr.scan_output(leaked_text)
        assert verdict.allowed is False
        assert verdict.action == "block"
        assert any("SYSTEM_PROMPT_LEAK" in r for r in verdict.matched_rules)

    def test_doc_canary_leak_blocked(self, canary_mgr):
        leaked_text = "Confidential document content contained CANARY_TEST_DOC_67890."
        verdict = canary_mgr.scan_output(leaked_text)
        assert verdict.allowed is False
        assert verdict.action == "block"
        assert any("CONFIDENTIAL_DOCUMENT_CANARY_LEAK" in r for r in verdict.matched_rules)

    def test_off_mode_ignores_canary(self):
        off_mgr = CanaryManager(
            policy=GuardrailPolicy.from_mode("off"),
            system_canary="CANARY_TEST_SYS_12345",
        )
        verdict = off_mgr.scan_output("The secret canary is CANARY_TEST_SYS_12345")
        assert verdict.allowed is True
