"""Chat endpoint supporting real-time Server-Sent Events (SSE) streaming and live Agent Traces."""
import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from apps.api.config import settings
from apps.api.core.evidence import EvidenceStore
from apps.api.core.guardrails.canary import default_canary_manager
from apps.api.core.guardrails.citation_validator import CitationValidator
from apps.api.core.guardrails.input_guard import InputGuardrail
from apps.api.core.guardrails.output_guard import OutputGuardrail
from apps.api.core.guardrails.permission import default_permission_layer
from apps.api.core.guardrails.policy import GuardrailPolicy
from apps.api.core.llm import LLMClient
from apps.api.core.memory import MemoryManager
from apps.api.core.planner import Planner
from apps.api.core.router import Router
from apps.api.core.synthesizer import Synthesizer
from apps.api.core.tracer import RunTrace, global_tracer
from apps.api.core.verifier import Verifier

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Chat"])

memory_mgr = MemoryManager(db_path=settings.SQLITE_DB_PATH)
llm_client = LLMClient()


class ChatRequest(BaseModel):
    query: str
    session_id: str = "default-session"
    stream: bool = True
    policy_mode: str | None = None


@router.post("")
async def chat_endpoint(req: ChatRequest):
    """
    Agentic RAG chat endpoint with real-time SSE streaming.
    Emits events: memory_recall, guardrail_verdict, plan, tool_result, verification, evidence, token, done.
    """
    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        start_time = time.perf_counter()
        query = req.query
        session_id = req.session_id
        policy = GuardrailPolicy.from_mode(req.policy_mode)
        canary_mgr = default_canary_manager
        guardrail_verdicts: list[dict[str, Any]] = []

        # 1. INPUT GUARDRAIL
        input_guard = InputGuardrail(policy)
        input_verdict = input_guard.evaluate(query)
        guardrail_verdicts.append(input_verdict.model_dump())

        yield {
            "event": "guardrail_verdict",
            "data": json.dumps(input_verdict.model_dump()),
        }

        if not input_verdict.allowed:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            rejection_text = (
                "I cannot fulfill this request because it contains instructions that violate "
                "security policies or attempt to override system guardrails."
            )
            yield {
                "event": "token",
                "data": json.dumps({"token": rejection_text}),
            }

            trace = RunTrace(
                query=query,
                data_mode=settings.DATA_MODE,
                llm_provider=settings.LLM_PROVIDER,
                policy_mode=policy.mode,
                guardrail_verdicts=guardrail_verdicts,
                security_blocked=True,
                block_reason=input_verdict.reasons[0] if input_verdict.reasons else "Input blocked",
                final_answer=rejection_text,
                duration_ms=duration_ms,
            )
            global_tracer.record(trace)

            yield {
                "event": "done",
                "data": json.dumps({
                    "trace_id": trace.trace_id,
                    "duration_ms": duration_ms,
                    "security_blocked": True,
                    "citations": [],
                    "iterations": 0,
                }),
            }
            return

        # 2. PERMISSION LAYER (Propose-only check for destructive or outbound actions)
        can_proceed, perm_verdict, pending_action = default_permission_layer.classify_and_propose(
            query, policy=policy
        )
        guardrail_verdicts.append(perm_verdict.model_dump())

        yield {
            "event": "guardrail_verdict",
            "data": json.dumps(perm_verdict.model_dump()),
        }

        if not can_proceed and pending_action:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            paused_text = (
                f"⚠️ Proposed action requires human confirmation:\n\n"
                f"• **Action**: {pending_action.summary}\n"
                f"• **Target**: {pending_action.target_system}\n"
                f"• **Token**: `{pending_action.token}`\n"
                f"• **Expires**: {pending_action.expires_at}\n\n"
                f"A simulated notification has been dispatched to `./outbox/proposal_{pending_action.token}.json`.\n"
                f"Use the Pending Actions panel or `POST /api/actions/{pending_action.token}/confirm` to approve."
            )
            yield {
                "event": "token",
                "data": json.dumps({"token": paused_text}),
            }

            trace = RunTrace(
                query=query,
                data_mode=settings.DATA_MODE,
                llm_provider=settings.LLM_PROVIDER,
                policy_mode=policy.mode,
                guardrail_verdicts=guardrail_verdicts,
                action_paused=True,
                pending_action=pending_action.model_dump(),
                final_answer=paused_text,
                duration_ms=duration_ms,
            )
            global_tracer.record(trace)

            yield {
                "event": "done",
                "data": json.dumps({
                    "trace_id": trace.trace_id,
                    "duration_ms": duration_ms,
                    "action_paused": True,
                    "pending_action": pending_action.model_dump(),
                    "citations": [],
                    "iterations": 0,
                }),
            }
            return

        # 3. Read Policy: Memory recall
        recalled_memories = memory_mgr.retrieve_relevant_memories(query)
        conv_context = memory_mgr.short_term.get_formatted_context(session_id)

        yield {
            "event": "memory_recall",
            "data": json.dumps({"memories": recalled_memories}),
        }

        # 3. Planner: Decompose query
        planner = Planner(llm_client)
        plan = await planner.plan(
            query=query,
            memories=recalled_memories,
            conversation_context=conv_context,
        )

        yield {
            "event": "plan",
            "data": json.dumps(plan.model_dump()),
        }

        # 4. Execution & Verification Loop
        evidence_store = EvidenceStore()
        router_exec = Router(evidence_store, policy=policy)
        verifier = Verifier(llm_client)
        verifications_log = []
        all_failed_sources = set()

        current_sub_questions = list(plan.sub_questions)
        iteration = 0
        max_iterations = 2

        while iteration < max_iterations and current_sub_questions:
            iteration += 1

            # Dispatch sub-questions
            tasks = [router_exec.execute_subquestion(sq) for sq in current_sub_questions]
            for coro in asyncio.as_completed(tasks):
                res = await coro
                if res.get("status") == "failed":
                    all_failed_sources.add(res.get("target_source", "unknown"))

                yield {
                    "event": "tool_result",
                    "data": json.dumps(res),
                }

            # Verification step
            verification = await verifier.verify(
                original_query=query,
                plan=plan,
                evidence_store=evidence_store,
            )

            verif_data = {
                "iteration": iteration,
                "is_sufficient": verification.is_sufficient,
                "reasoning": verification.reasoning,
                "unanswered": verification.unanswered_sub_questions,
            }
            verifications_log.append(verif_data)

            yield {
                "event": "verification",
                "data": json.dumps(verif_data),
            }

            if verification.is_sufficient or iteration >= max_iterations:
                break

            current_sub_questions = verification.follow_up_sub_questions

        # Collect router-level verdicts (retrieval & redactions)
        for g_verd in router_exec.guardrail_verdicts:
            guardrail_verdicts.append(g_verd)
            yield {
                "event": "guardrail_verdict",
                "data": json.dumps(g_verd),
            }

        redactions_count = sum(
            v.get("metadata", {}).get("redaction_count", 1)
            for v in guardrail_verdicts
            if v.get("action") == "redact"
        )

        # 5. Stream collected evidence items
        all_evidence = evidence_store.get_all()
        yield {
            "event": "evidence",
            "data": json.dumps([ev.model_dump() for ev in all_evidence]),
        }

        # 6. Stream Synthesized Answer tokens
        synthesizer = Synthesizer(llm_client)
        accumulated_text = []

        async for chunk in synthesizer.stream_synthesize(
            query=query,
            evidence_store=evidence_store,
            memories=recalled_memories,
            failed_sources=list(all_failed_sources),
        ):
            accumulated_text.append(chunk)
            yield {
                "event": "token",
                "data": json.dumps({"token": chunk}),
            }

        full_answer = "".join(accumulated_text)

        # 7. Citation Validation
        cit_validator = CitationValidator(policy)
        cleaned_answer, cit_verdict = cit_validator.validate(
            full_answer, evidence_store, policy=policy
        )
        guardrail_verdicts.append(cit_verdict.model_dump())
        yield {
            "event": "guardrail_verdict",
            "data": json.dumps(cit_verdict.model_dump()),
        }

        # 8. Output Guardrail (Canary Scan + Secondary PII Redaction)
        output_guard = OutputGuardrail(policy, canary_manager=canary_mgr)
        allowed, sanitized_output, out_verdicts = output_guard.evaluate_and_sanitize(
            cleaned_answer, policy=policy
        )
        for ov in out_verdicts:
            guardrail_verdicts.append(ov.model_dump())
            yield {
                "event": "guardrail_verdict",
                "data": json.dumps(ov.model_dump()),
            }

        security_blocked = not allowed
        block_reason = None
        if not allowed:
            security_blocked = True
            block_reason = (
                out_verdicts[0].reasons[0]
                if out_verdicts and out_verdicts[0].reasons
                else "Output blocked by guardrail"
            )
            full_answer = sanitized_output
            citations = []
        else:
            full_answer = sanitized_output
            citations = synthesizer._extract_used_citations(full_answer, evidence_store)

        # Recalculate total redactions
        redactions_count = sum(
            v.get("metadata", {}).get("redaction_count", 1)
            for v in guardrail_verdicts
            if v.get("action") == "redact"
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 8. Record observability trace
        trace = RunTrace(
            query=query,
            data_mode=settings.DATA_MODE,
            llm_provider=settings.LLM_PROVIDER,
            policy_mode=policy.mode,
            plan=plan.model_dump(),
            tool_calls=router_exec.traces,
            verifications=verifications_log,
            guardrail_verdicts=guardrail_verdicts,
            security_blocked=security_blocked,
            block_reason=block_reason,
            redactions_count=redactions_count,
            evidence_count=len(all_evidence),
            citations_count=len(citations),
            final_answer=full_answer,
            duration_ms=duration_ms,
            failed_sources=list(all_failed_sources),
        )
        global_tracer.record(trace)

        # 9. Update Short-Term and Write-Policy Long-Term Memory
        if not security_blocked:
            memory_mgr.short_term.add_message(session_id, "user", query)
            memory_mgr.short_term.add_message(session_id, "assistant", full_answer)
            asyncio.create_task(memory_mgr.extract_and_persist(query, full_answer))

        # 10. Emit final done event
        yield {
            "event": "done",
            "data": json.dumps({
                "trace_id": trace.trace_id,
                "duration_ms": duration_ms,
                "security_blocked": security_blocked,
                "citations": [c.model_dump() for c in citations],
                "iterations": iteration,
            }),
        }

    return EventSourceResponse(event_generator())
