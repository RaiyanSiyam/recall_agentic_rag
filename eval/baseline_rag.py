"""Baseline Static RAG: Standard chunked vector retrieval over a static document export."""
import time
from typing import Any

from apps.api.core.llm import LLMClient

STATIC_KNOWLEDGE_BASE = """
PROJECT X SUMMARY DOCUMENT (STATIC EXPORT - OCT 2026)

Section 1: Overview and Goals
Project X is an enterprise healthcare initiative designed to expand into compliance markets.
Target availability is 99.99%. Approved Q3 budget is $450,000 under Executive Sponsor Sarah Chen.
The initiative incorporates FHIR interoperability and event-driven data streaming.

Section 2: Team Members
The engineering team includes Alex Rivera, Maya Patel, Elena Rostova, and David Kim.

Section 3: Deliverables Overview
Several deliverables are planned this quarter including HIPAA Data Isolation, Audit Trail Logging,
OAuth2 Single Sign-On, and FHIR connectors. Audit trail logging is completed.

Section 4: Infrastructure & Security
Data at rest uses AES-256 with AWS KMS keys. Staging deployment deadline is October 30 for SOC2 audit.

Section 5: Issue Tracker Dump
Several issues are tracked in Jira under project PROJ. PROJ-105 benchmark completed with 4,200 records/sec.
Sprint 24 is ongoing.
"""


class BaselineStaticRAG:
    """Classic naive RAG: passes top-k static chunks to prompt without decomposition or live MCP routing."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or LLMClient()
        self._chunks = self._chunk_text(STATIC_KNOWLEDGE_BASE)

    def _chunk_text(self, text: str, chunk_size: int = 60) -> list[str]:
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - 10):
            chunk = " ".join(words[i : i + chunk_size])
            chunks.append(chunk)
        return chunks

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        """Simple TF-IDF / term overlap retriever simulating vector search."""
        q_tokens = set(query.lower().split())
        scored = []
        for c in self._chunks:
            c_tokens = set(c.lower().split())
            score = len(q_tokens.intersection(c_tokens))
            scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for score, c in scored[:top_k]]

    async def answer(self, query: str) -> dict[str, Any]:
        start = time.perf_counter()
        retrieved_chunks = self.retrieve(query)
        context = "\n---\n".join(retrieved_chunks)

        prompt = (
            f"You are a basic static RAG assistant. Answer using ONLY this static context:\n"
            f"{context}\n\n"
            f"Question: {query}\n"
            f"Answer concisely. If not in the text, say 'Information not found in document'."
        )

        answer_text = await self.llm.generate_text(prompt)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "query": query,
            "answer": answer_text,
            "retrieved_chunks_count": len(retrieved_chunks),
            "duration_ms": duration_ms,
        }
