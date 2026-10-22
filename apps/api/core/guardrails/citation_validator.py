"""Citation Validator ensuring every [n] maps to verified evidence and stripping hallucinated citations."""
import logging
import re

from apps.api.core.evidence import EvidenceStore
from apps.api.core.guardrails.policy import GuardrailPolicy, default_policy
from apps.api.core.guardrails.verdicts import GuardrailVerdict

logger = logging.getLogger(__name__)

CITATION_REGEX = re.compile(r"\[(\d+)\]")


class CitationValidator:
    """Validates citations in generated answers against EvidenceStore records."""

    def __init__(self, policy: GuardrailPolicy | None = None):
        self.policy = policy or default_policy

    def validate(
        self,
        text: str,
        evidence_store: EvidenceStore,
        policy: GuardrailPolicy | None = None,
    ) -> tuple[str, GuardrailVerdict]:
        """
        Validate all [n] citations in the text.
        Returns the sanitized text (with hallucinated citations stripped/flagged) and a GuardrailVerdict.
        """
        pol = policy or self.policy
        if not pol.citation_validation_enabled or not text:
            return text, GuardrailVerdict.allow("citation_validator", "Citation validation disabled or empty text")

        valid_ids = {ev.evidence_id for ev in evidence_store.get_all()}
        found_matches = list(CITATION_REGEX.finditer(text))

        if not found_matches:
            # If evidence existed but synthesizer provided zero citations, flag warning
            if not evidence_store.is_empty():
                return text, GuardrailVerdict(
                    allowed=True,
                    action="allow",
                    guardrail_name="citation_validator",
                    reasons=["No citations provided in synthesized answer"],
                    matched_rules=["missing_citations"],
                    metadata={"valid_citations": 0, "invalid_citations": 0},
                )
            return text, GuardrailVerdict.allow("citation_validator", "No evidence required for empty result")

        valid_citations: set[int] = set()
        invalid_citations: set[int] = set()

        for match in found_matches:
            cid = int(match.group(1))
            if cid in valid_ids:
                valid_citations.add(cid)
            else:
                invalid_citations.add(cid)

        # If all citations are valid, return allow verdict
        if not invalid_citations:
            return text, GuardrailVerdict.allow(
                "citation_validator",
                f"All {len(valid_citations)} citations validated against evidence store",
                metadata={"valid_citations": list(valid_citations), "invalid_citations": []},
            )

        # Strip hallucinated/invalid citations from text
        def replace_invalid(match: re.Match[str]) -> str:
            cid = int(match.group(1))
            if cid not in valid_ids:
                return ""  # Strip hallucinated citation marker
            return match.group(0)

        cleaned_text = CITATION_REGEX.sub(replace_invalid, text)
        # Clean up any resulting double spaces
        cleaned_text = re.sub(r"  +", " ", cleaned_text).strip()

        verdict = GuardrailVerdict(
            allowed=True,
            action="redact" if pol.mode != "strict" else "allow",
            guardrail_name="citation_validator",
            reasons=[
                f"Stripped {len(invalid_citations)} hallucinated citation(s): "
                f"{sorted(invalid_citations)}. Valid citations: {sorted(valid_citations)}."
            ],
            matched_rules=[f"invalid_citation_{cid}" for cid in sorted(invalid_citations)],
            metadata={
                "valid_citations": list(valid_citations),
                "invalid_citations": list(invalid_citations),
                "original_length": len(text),
                "cleaned_length": len(cleaned_text),
            },
        )

        return cleaned_text, verdict
