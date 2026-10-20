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


@router.post("")
async def chat_endpoint(req: ChatRequest):
    """
    Agentic RAG chat endpoint with real-time SSE streaming.
    Emits events: memory_recall, plan, tool_result, verification, evidence, token, done.
    """
    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        start_time = time.perf_counter()
        query = req.query
        session_id = req.session_id

        # 0. Read Policy: Memory recall
        recalled_memories = memory_mgr.retrieve_relevant_memories(query)
        conv_context = memory_mgr.short_term.get_formatted_context(session_id)

        yield {
            "event": "memory_recall",
            "data": json.dumps({"memories": recalled_memories}),
        }

        # 1. Planner: Decompose query
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

        # 2. Execution & Verification Loop
        evidence_store = EvidenceStore()
        router_exec = Router(evidence_store)
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

        # 3. Stream collected evidence items
        all_evidence = evidence_store.get_all()
        yield {
            "event": "evidence",
            "data": json.dumps([ev.model_dump() for ev in all_evidence]),
        }

        # 4. Stream Synthesized Answer tokens
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
        citations = synthesizer._extract_used_citations(full_answer, evidence_store)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 5. Record observability trace
        trace = RunTrace(
            query=query,
            data_mode=settings.DATA_MODE,
            llm_provider=settings.LLM_PROVIDER,
            plan=plan.model_dump(),
            tool_calls=router_exec.traces,
            verifications=verifications_log,
            evidence_count=len(all_evidence),
            citations_count=len(citations),
            final_answer=full_answer,
            duration_ms=duration_ms,
            failed_sources=list(all_failed_sources),
        )
        global_tracer.record(trace)

        # 6. Update Short-Term and Write-Policy Long-Term Memory
        memory_mgr.short_term.add_message(session_id, "user", query)
        memory_mgr.short_term.add_message(session_id, "assistant", full_answer)
        asyncio.create_task(memory_mgr.extract_and_persist(query, full_answer))

        # 7. Emit final done event
        yield {
            "event": "done",
            "data": json.dumps({
                "trace_id": trace.trace_id,
                "duration_ms": duration_ms,
                "citations": [c.model_dump() for c in citations],
                "iterations": iteration,
            }),
        }

    return EventSourceResponse(event_generator())
