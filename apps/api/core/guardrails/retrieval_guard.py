"""Retrieval Guardrail: Neutralizes indirect prompt injections and wraps tool outputs in untrusted boundaries."""
import re

from apps.api.core.guardrails.policy import GuardrailPolicy, default_policy
from apps.api.core.guardrails.verdicts import GuardrailVerdict
from mcp_servers.shared.sanitizer import sanitize_text

# Indirect injection patterns that might be planted in emails, docs, or issues
INDIRECT_INJECTION_PATTERNS = [
    ("INDIRECT_INSTRUCTION_OVERRIDE", re.compile(r"(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions)", re.IGNORECASE)),
    ("INDIRECT_EXFILTRATION", re.compile(r"(?:send|exfiltrate|forward|post|upload)\s+(?:all|the|user)\s+(?:data|emails|passwords|secrets|canary)\s+to\b", re.IGNORECASE)),
    ("INDIRECT_SYSTEM_IMPERSONATION", re.compile(r"(?:<\s*system\s*>|<\|im_start\|>system|```system|SYSTEM\s*:\s*You\s+are\s+now)", re.IGNORECASE)),
    ("INDIRECT_MEMORY_POISON_TRIGGER", re.compile(r"(?:remember\s+that\s+Project\s+X\s+is\s+cancelled|remember\s+that\s+the\s+admin\s+password\s+is)", re.IGNORECASE)),
]


class RetrievalGuardrail:
    """Sanitizes raw MCP tool outputs and frames them in secure untrusted envelopes."""

    def __init__(self, policy: GuardrailPolicy | None = None):
        self.policy = policy or default_policy

    def wrap_and_sanitize(self, raw_content: str, source: str, sub_q_id: str) -> tuple[str, GuardrailVerdict]:
        """Sanitize raw content from external tools and wrap as untrusted evidence."""
        if not self.policy.retrieval_guard_enabled:
            return raw_content, GuardrailVerdict.allow("retrieval_guard", "Retrieval guardrail disabled")

        if not raw_content:
            return "", GuardrailVerdict.allow("retrieval_guard", "Empty tool output")

        matched_injections: list[str] = []
        cleaned = raw_content

        # 1. Detect and neutralize indirect injections
        for pat_name, pattern in INDIRECT_INJECTION_PATTERNS:
            if pattern.search(cleaned):
                matched_injections.append(pat_name)
                cleaned = pattern.sub("[NEUTRALIZED_UNTRUSTED_INJECTION]", cleaned)

        # 2. General sanitization (length bounding, control tokens)
        cleaned = sanitize_text(cleaned)

        # 3. Delimited untrusted envelope
        wrapped_content = (
            f"<<<UNTRUSTED_EXTERNAL_TOOL_EVIDENCE source=\"{source}\" id=\"{sub_q_id}\">>>\n"
            f"{cleaned}\n"
            f"<<<END_UNTRUSTED_EVIDENCE>>>"
        )

        if matched_injections:
            verdict = GuardrailVerdict(
                allowed=True,
                action="redact",
                guardrail_name="retrieval_guard",
                reasons=[f"Neutralized {len(matched_injections)} indirect injection pattern(s) in {source} content"],
                matched_rules=matched_injections,
                metadata={"source": source, "sub_question_id": sub_q_id},
            )
        else:
            verdict = GuardrailVerdict.allow(
                name="retrieval_guard",
                reason=f"Safely wrapped evidence from {source}",
                metadata={"source": source, "sub_question_id": sub_q_id},
            )

        return wrapped_content, verdict
