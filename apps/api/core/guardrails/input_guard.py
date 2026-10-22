"""Input Guardrail combining regex heuristics and mock-compatible classifier for prompt injection."""
import re

from apps.api.core.guardrails.policy import GuardrailPolicy, default_policy
from apps.api.core.guardrails.verdicts import GuardrailVerdict

# Heuristic patterns for direct prompt injection and jailbreak attempts
INJECTION_RULES = [
    ("INSTRUCTION_BYPASS", re.compile(r"\b(?:ignore|disregard|forget|override|bypass|reset)\s+(?:all\s+)?(?:previous|prior|above|system|everything\s+above)?\s*(?:instructions|rules|prompts|directions|guidelines|policies|guardrails|commands)\b", re.IGNORECASE)),
    ("DISREGARD_COMMANDS", re.compile(r"\b(?:disregard\s+(?:prior\s+commands|everything\s+above))\b", re.IGNORECASE)),
    ("SYSTEM_OVERRIDE", re.compile(r"\b(?:system\s+override|system\s+reset|admin\s+override|sudo\s+mode|root\s+access)\b", re.IGNORECASE)),
    ("DEVELOPER_JAILBREAK", re.compile(r"\b(?:you\s+are\s+now\s+(?:in\s+)?(?:developer\s+mode|dan|unfiltered|jailbroken|an\s+evil\s+ai))\b", re.IGNORECASE)),
    ("SAFETY_BYPASS_ROLEPLAY", re.compile(r"\b(?:pretend|act\s+like|simulate|act\s+as\s+an?)\s+(?:unfiltered|unrestricted|evil|dan|you\s+have\s+no\s+(?:ethics|rules|filters|guidelines)|without\s+(?:ethical\s+boundaries|security\s+policies|restrictions))\b", re.IGNORECASE)),
    ("SYSTEM_PROMPT_EXTRACTION", re.compile(r"\b(?:repeat|print|output|display|show|reveal|echo)\s+(?:all\s+)?(?:initial\s+instructions|system\s+prompt|rules\s+above|verbatim\s+instructions|secret\s+key|canary)\b", re.IGNORECASE)),
    ("DELIMITER_HIJACK", re.compile(r"(?:<\|im_start\|>|<\|im_end\|>|\[\s*INST\s*\]|\[\s*/INST\s*\]|\[\s*SYSTEM\s*\]|```system|<\s*system\s*>)", re.IGNORECASE)),
    ("SECRET_EXFILTRATION_PROBE", re.compile(r"\b(?:api[_\-\s]?(?:keys?|tokens?)|secret[_\-\s]?(?:keys?|tokens?|notion)|auth(?:orization)?\s+headers?|bearer\s+tokens?|private\s+keys?|environment\s+variables?|db\s+password|passwords?|credentials?|aws[_\s]?secret(?:[_\s]?access[_\s]?key)?|openai[_\s]?api[_\s]?key|anthropic[_\s]?api[_\s]?key|signing\s+(?:secrets?|keys?)|sk-(?:proj-)?[A-Za-z0-9_\-]*|jwt[_\s]?(?:secret|token)?)\b", re.IGNORECASE)),
    ("CANARY_EXTRACTION_PROBE", re.compile(r"\b(?:canary|canary[_-]?token|canary[_-]?doc|canary[_-]?system)\b", re.IGNORECASE)),
]


class InputGuardrail:
    """Evaluates incoming user questions for prompt injection, jailbreaks, and system probing."""

    def __init__(self, policy: GuardrailPolicy | None = None):
        self.policy = policy or default_policy

    def evaluate(self, query: str) -> GuardrailVerdict:
        """Inspect user query and return an allow or block verdict."""
        if not self.policy.input_guard_enabled or not query:
            return GuardrailVerdict.allow("input_guardrail", "Input guardrail disabled or empty query")

        q_clean = query.strip()
        matched_rules: list[str] = []
        reasons: list[str] = []

        # 1. Regex rule checks
        for rule_name, pattern in INJECTION_RULES:
            if pattern.search(q_clean):
                matched_rules.append(rule_name)
                reasons.append(f"Detected suspicious pattern matching rule: {rule_name}")

        # 2. Heuristic scoring for obfuscated injections
        q_lower = q_clean.lower()
        suspicion_score = 0.0

        if any(term in q_lower for term in ["ignore", "override", "bypass", "jailbreak", "unfiltered"]):
            suspicion_score += 0.3
        if any(term in q_lower for term in ["system prompt", "developer mode", "canary", "instructions verbatim"]):
            suspicion_score += 0.4
        if any(term in q_lower for term in ["<script>", "javascript:", "eval(", "exec("]):
            suspicion_score += 0.4

        threshold = 0.4 if self.policy.mode == "strict" else 0.7
        if suspicion_score >= threshold and not matched_rules:
            matched_rules.append("HEURISTIC_INJECTION_RISK")
            reasons.append(f"Input heuristic risk score ({suspicion_score:.2f}) exceeded threshold ({threshold:.2f})")

        # 3. Decision
        if matched_rules:
            return GuardrailVerdict.block(
                name="input_guardrail",
                reason=f"Prompt injection or jailbreak attempt blocked: {'; '.join(reasons)}",
                matched_rules=matched_rules,
                metadata={"risk_score": suspicion_score, "query_preview": q_clean[:80]},
            )

        return GuardrailVerdict.allow("input_guardrail", "Query passed injection heuristics", metadata={"risk_score": suspicion_score})
