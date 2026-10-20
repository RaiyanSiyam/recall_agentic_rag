"""Agent Pipeline Orchestrator coordinating Planning, Execution, Verification, and Synthesis."""
import logging
import time
from datetime import UTC, datetime
from typing import Any

from apps.api.core.evidence import Evidence, EvidenceStore
from apps.api.core.llm import LLMClient
from apps.api.core.planner import Plan, Planner
from apps.api.core.router import Router
from apps.api.core.synthesizer import Synthesizer
from apps.api.core.verifier import VerificationResult, Verifier

logger = logging.getLogger(__name__)


class AgentRunResult:
    """Complete trace and output of an agent run."""

    def __init__(
        self,
        query: str,
        plan: Plan,
        evidence: list[Evidence],
        answer: str,
        citations: list[Evidence],
        traces: list[dict[str, Any]],
        verifications: list[dict[str, Any]],
        iterations: int,
        duration_ms: float,
        failed_sources: list[str] | None = None,
    ):
        self.query = query
        self.plan = plan
        self.evidence = evidence
        self.answer = answer
        self.citations = citations
        self.traces = traces
        self.verifications = verifications
        self.iterations = iterations
        self.duration_ms = duration_ms
        self.failed_sources = failed_sources or []
        self.timestamp = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "plan": self.plan.model_dump(),
            "evidence": [ev.model_dump() for ev in self.evidence],
            "answer": self.answer,
            "citations": [c.model_dump() for c in self.citations],
            "traces": self.traces,
            "verifications": self.verifications,
            "iterations": self.iterations,
            "duration_ms": self.duration_ms,
            "failed_sources": self.failed_sources,
            "timestamp": self.timestamp,
        }


class AgenticRAG:
    """Core Agent coordinating Planner, parallel Router, Verifier loop, and Synthesizer."""

    def __init__(self, llm_client: LLMClient | None = None, max_iterations: int = 2):
        self.llm = llm_client or LLMClient()
        self.planner = Planner(self.llm)
        self.verifier = Verifier(self.llm)
        self.synthesizer = Synthesizer(self.llm)
        self.max_iterations = max_iterations

    async def run(
        self,
        query: str,
        memories: list[str] | None = None,
        conversation_context: str | None = None,
    ) -> AgentRunResult:
        start_time = time.perf_counter()
        evidence_store = EvidenceStore()
        router = Router(evidence_store)

        # 1. Decompose query into targeted sub-questions
        plan = await self.planner.plan(
            query=query,
            memories=memories,
            conversation_context=conversation_context,
        )

        current_sub_questions = list(plan.sub_questions)
        verifications_log: list[dict[str, Any]] = []
        iteration = 0
        all_failed_sources: set[str] = set()

        # 2. Execution & Verification Loop (capped at max_iterations)
        while iteration < self.max_iterations and current_sub_questions:
            iteration += 1

            # Execute sub-questions concurrently
            tool_results = await router.execute_plan_parallel(current_sub_questions)

            for res in tool_results:
                if res.get("status") == "failed":
                    all_failed_sources.add(res.get("target_source", "unknown"))

            # Run Verifier self-check step
            verification: VerificationResult = await self.verifier.verify(
                original_query=query,
                plan=plan,
                evidence_store=evidence_store,
            )

            verifications_log.append({
                "iteration": iteration,
                "is_sufficient": verification.is_sufficient,
                "reasoning": verification.reasoning,
                "unanswered_count": len(verification.unanswered_sub_questions),
                "follow_up_count": len(verification.follow_up_sub_questions),
            })

            # Check termination
            if verification.is_sufficient or iteration >= self.max_iterations:
                break

            # Prepare follow-up retrieval loop
            if verification.follow_up_sub_questions:
                current_sub_questions = verification.follow_up_sub_questions
            else:
                break

        # 3. Synthesize final answer with numbered citations
        answer, citations = await self.synthesizer.synthesize(
            query=query,
            evidence_store=evidence_store,
            memories=memories,
            failed_sources=list(all_failed_sources),
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return AgentRunResult(
            query=query,
            plan=plan,
            evidence=evidence_store.get_all(),
            answer=answer,
            citations=citations,
            traces=router.traces,
            verifications=verifications_log,
            iterations=iteration,
            duration_ms=duration_ms,
            failed_sources=list(all_failed_sources),
        )
