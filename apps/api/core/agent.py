"""Agent Pipeline Orchestrator coordinating Planning, Execution, Verification, and Synthesis."""
import logging
import time
from datetime import UTC, datetime
from typing import Any

from apps.api.core.evidence import Evidence, EvidenceStore
from apps.api.core.guardrails.canary import CanaryManager, default_canary_manager
from apps.api.core.guardrails.citation_validator import CitationValidator
from apps.api.core.guardrails.input_guard import InputGuardrail
from apps.api.core.guardrails.output_guard import OutputGuardrail
from apps.api.core.guardrails.permission import PermissionLayer, default_permission_layer
from apps.api.core.guardrails.policy import GuardrailPolicy, default_policy
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
        guardrail_verdicts: list[dict[str, Any]] | None = None,
        security_blocked: bool = False,
        block_reason: str | None = None,
        redactions_count: int = 0,
        action_paused: bool = False,
        pending_action: dict[str, Any] | None = None,
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
        self.guardrail_verdicts = guardrail_verdicts or []
        self.security_blocked = security_blocked
        self.block_reason = block_reason
        self.redactions_count = redactions_count
        self.action_paused = action_paused
        self.pending_action = pending_action
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
            "guardrail_verdicts": self.guardrail_verdicts,
            "security_blocked": self.security_blocked,
            "block_reason": self.block_reason,
            "redactions_count": self.redactions_count,
            "action_paused": self.action_paused,
            "pending_action": self.pending_action,
            "timestamp": self.timestamp,
        }


class AgenticRAG:
    """Core Agent coordinating Planner, parallel Router, Verifier loop, Synthesizer, and Guardrails."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        max_iterations: int = 2,
        policy: GuardrailPolicy | None = None,
        canary_manager: CanaryManager | None = None,
        permission_layer: PermissionLayer | None = None,
        citation_validator: CitationValidator | None = None,
        output_guard: OutputGuardrail | None = None,
    ):
        self.llm = llm_client or LLMClient()
        self.policy = policy or default_policy
        self.canary_mgr = canary_manager or default_canary_manager
        self.input_guard = InputGuardrail(self.policy)
        self.permission_layer = permission_layer or default_permission_layer
        self.citation_validator = citation_validator or CitationValidator(self.policy)
        self.output_guard = output_guard or OutputGuardrail(
            self.policy, canary_manager=self.canary_mgr
        )
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
        guardrail_verdicts: list[dict[str, Any]] = []

        # 1. INPUT GUARDRAIL
        input_verdict = self.input_guard.evaluate(query)
        guardrail_verdicts.append(input_verdict.model_dump())

        if not input_verdict.allowed:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            rejection_text = (
                "I cannot fulfill this request because it contains instructions that violate "
                "security policies or attempt to override system guardrails."
            )
            empty_plan = Plan(thought_process="Blocked by Input Guardrail", sub_questions=[])
            return AgentRunResult(
                query=query,
                plan=empty_plan,
                evidence=[],
                answer=rejection_text,
                citations=[],
                traces=[],
                verifications=[],
                iterations=0,
                duration_ms=duration_ms,
                guardrail_verdicts=guardrail_verdicts,
                security_blocked=True,
                block_reason=input_verdict.reasons[0] if input_verdict.reasons else "Input blocked",
            )

        # 2. PERMISSION LAYER (Propose-only check for destructive or outbound actions)
        can_proceed, perm_verdict, pending_action = self.permission_layer.classify_and_propose(
            query, policy=self.policy
        )
        guardrail_verdicts.append(perm_verdict.model_dump())

        if not can_proceed and pending_action:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            paused_text = (
                f"Action paused: {pending_action.summary}.\n"
                f"Confirmation token required: {pending_action.token}\n"
                f"Simulated notification dispatched to outbox. "
                f"Please confirm or reject via the Security panel or API."
            )
            empty_plan = Plan(
                thought_process=f"Action paused pending confirmation: {pending_action.summary}",
                sub_questions=[],
            )
            return AgentRunResult(
                query=query,
                plan=empty_plan,
                evidence=[],
                answer=paused_text,
                citations=[],
                traces=[],
                verifications=[],
                iterations=0,
                duration_ms=duration_ms,
                guardrail_verdicts=guardrail_verdicts,
                action_paused=True,
                pending_action=pending_action.model_dump(),
            )

        evidence_store = EvidenceStore()
        router = Router(evidence_store, policy=self.policy)

        # 2. Decompose query into targeted sub-questions
        plan = await self.planner.plan(
            query=query,
            memories=memories,
            conversation_context=conversation_context,
        )

        current_sub_questions = list(plan.sub_questions)
        verifications_log: list[dict[str, Any]] = []
        iteration = 0
        all_failed_sources: set[str] = set()

        # 3. Execution & Verification Loop (capped at max_iterations)
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

        # Collect tool-level guardrail verdicts (retrieval & redaction)
        guardrail_verdicts.extend(router.guardrail_verdicts)
        redactions_count = sum(
            v.get("metadata", {}).get("redaction_count", 1)
            for v in guardrail_verdicts
            if v.get("action") == "redact"
        )

        # 4. Synthesize final answer with numbered citations
        answer, citations = await self.synthesizer.synthesize(
            query=query,
            evidence_store=evidence_store,
            memories=memories,
            failed_sources=list(all_failed_sources),
        )

        # 5. CITATION VALIDATION
        answer, cit_verdict = self.citation_validator.validate(
            answer, evidence_store, policy=self.policy
        )
        guardrail_verdicts.append(cit_verdict.model_dump())
        citations = self.synthesizer._extract_used_citations(answer, evidence_store)

        # 6. OUTPUT GUARDRAIL (Canary Scan + Secondary PII Redaction)
        allowed, answer, out_verdicts = self.output_guard.evaluate_and_sanitize(
            answer, policy=self.policy
        )
        for ov in out_verdicts:
            guardrail_verdicts.append(ov.model_dump())

        security_blocked = not allowed
        block_reason = None
        if not allowed:
            security_blocked = True
            block_reason = (
                out_verdicts[0].reasons[0]
                if out_verdicts and out_verdicts[0].reasons
                else "Output blocked by guardrail"
            )
            citations = []

        # Recalculate total redactions across router and output
        redactions_count = sum(
            v.get("metadata", {}).get("redaction_count", 1)
            for v in guardrail_verdicts
            if v.get("action") == "redact"
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
            guardrail_verdicts=guardrail_verdicts,
            security_blocked=security_blocked,
            block_reason=block_reason,
            redactions_count=redactions_count,
        )
