"""Verifier (self-check step) evaluating retrieval sufficiency before synthesis."""
import logging

from pydantic import BaseModel, Field

from apps.api.core.evidence import EvidenceStore
from apps.api.core.llm import LLMClient
from apps.api.core.planner import Plan, SubQuestion

logger = logging.getLogger(__name__)


class VerificationResult(BaseModel):
    """Self-check evaluation outcome."""
    is_sufficient: bool = Field(
        description="True if collected evidence sufficiently answers all planned sub-questions"
    )
    reasoning: str = Field(description="Evaluation of evidence completeness and quality")
    unanswered_sub_questions: list[str] = Field(
        default_factory=list,
        description="IDs of sub-questions that lack sufficient backing evidence"
    )
    follow_up_sub_questions: list[SubQuestion] = Field(
        default_factory=list,
        description="Targeted follow-up queries to retrieve missing information (max 2 queries)"
    )


VERIFIER_SYSTEM_PROMPT = """You are a self-correction Verifier in an Agentic RAG system.
Your job is to evaluate whether the retrieved evidence items adequately answer the planned sub-questions.

CRITICAL INSTRUCTIONS:
1. Examine each planned sub-question against the collected evidence excerpt texts.
2. If all sub-questions have matching factual support, set `is_sufficient: true` and leave `follow_up_sub_questions: []`.
3. If an important sub-question has NO relevant evidence or only vague fragments:
   - Mark `is_sufficient: false`.
   - Formulate at most 1-2 targeted `follow_up_sub_questions` directed at the right tool to fill the gap.
   - Do NOT ask redundant questions already covered by evidence.
"""


class Verifier:
    """Verifies evidence sufficiency and triggers capped follow-up retrieval loops."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or LLMClient()

    async def verify(
        self,
        original_query: str,
        plan: Plan,
        evidence_store: EvidenceStore,
    ) -> VerificationResult:
        """Evaluate evidence against the planned sub-questions."""
        # Fast path: if evidence store is empty, definitely insufficient
        if evidence_store.is_empty():
            follow_ups = [
                SubQuestion(
                    id=f"retry_{sq.id}",
                    question=sq.question,
                    target_source=sq.target_source,
                    tool_hint=sq.tool_hint,
                    priority=1,
                )
                for sq in plan.sub_questions[:2]
            ]
            return VerificationResult(
                is_sufficient=False,
                reasoning="No evidence was retrieved from initial tool execution.",
                unanswered_sub_questions=[sq.id for sq in plan.sub_questions],
                follow_up_sub_questions=follow_ups,
            )

        evidence_summary = evidence_store.format_citation_block()
        plan_summary = "\n".join(
            f"[{sq.id}] ({sq.target_source.upper()}): {sq.question}"
            for sq in plan.sub_questions
        )

        prompt = (
            f"Original User Question: \"{original_query}\"\n\n"
            f"Planned Sub-Questions:\n{plan_summary}\n\n"
            f"Collected Evidence:\n{evidence_summary}\n\n"
            f"Determine if the collected evidence sufficiently answers all planned sub-questions."
        )

        try:
            result = await self.llm.generate_structured(
                prompt=prompt,
                response_model=VerificationResult,
                system_prompt=VERIFIER_SYSTEM_PROMPT,
            )
            # Bound maximum follow-up queries to prevent query explosion
            result.follow_up_sub_questions = result.follow_up_sub_questions[:2]
            return result
        except Exception as e:
            logger.warning(f"Verification LLM error: {e}. Assuming evidence is sufficient.")
            return VerificationResult(
                is_sufficient=True,
                reasoning="Defaulted to sufficient after verification error.",
                unanswered_sub_questions=[],
                follow_up_sub_questions=[],
            )
