"""Synthesizer that merges multi-source evidence into a strictly cited answer."""
import re
from collections.abc import AsyncGenerator

from apps.api.core.evidence import Evidence, EvidenceStore
from apps.api.core.llm import LLMClient

SYNTHESIZER_SYSTEM_PROMPT = """You are a rigorous, fact-based AI Synthesizer in an enterprise Agentic RAG system.
Your job is to answer the user's question using ONLY the provided evidence items.

CRITICAL RULES:
1. STRICT CITATIONS: EVERY factual statement, claim, number, or deadline MUST be followed immediately by a citation in square brackets matching the evidence item number, e.g. [1], [2].
2. ZERO SPECULATION: Do NOT make up any details. If an aspect of the question is not answered by the evidence, state: "Information not found in available sources".
3. CONFLICT HANDLING: If sources provide conflicting data, present both perspectives with their respective citations.
4. STRUCTURE: Organize the answer logically with clear headers or bullet points. Follow the prompt flow:
   - Project Goals & Overview (cited)
   - Planned Tasks & Deliverables (cited)
   - Changed Deadlines (cited)
   - Active Blockers & Risks (cited)
5. CITATION FORMAT: Use only [1], [2], [3] format.
"""


class Synthesizer:
    """Produces verified, strictly cited responses mapped to EvidenceStore records."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or LLMClient()

    async def synthesize(
        self,
        query: str,
        evidence_store: EvidenceStore,
        memories: list[str] | None = None,
        failed_sources: list[str] | None = None,
    ) -> tuple[str, list[Evidence]]:
        """Synthesize final cited text and return mapped citations."""
        if evidence_store.is_empty():
            msg = "Information not found in available sources. None of the connected tools (Gmail, Notion, Jira) returned matching evidence."
            if failed_sources:
                msg += f" Note: The following sources encountered connection issues: {', '.join(failed_sources)}."
            return msg, []

        prompt = self._build_prompt(query, evidence_store, memories, failed_sources)
        text = await self.llm.generate_text(prompt, system_prompt=SYNTHESIZER_SYSTEM_PROMPT)
        used_citations = self._extract_used_citations(text, evidence_store)
        return text, used_citations

    async def stream_synthesize(
        self,
        query: str,
        evidence_store: EvidenceStore,
        memories: list[str] | None = None,
        failed_sources: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream synthesized text chunks."""
        if evidence_store.is_empty():
            yield "Information not found in available sources."
            return

        prompt = self._build_prompt(query, evidence_store, memories, failed_sources)
        async for chunk in self.llm.stream_text(prompt, system_prompt=SYNTHESIZER_SYSTEM_PROMPT):
            yield chunk

    def _build_prompt(
        self,
        query: str,
        evidence_store: EvidenceStore,
        memories: list[str] | None,
        failed_sources: list[str] | None,
    ) -> str:
        citation_block = evidence_store.format_citation_block()
        mem_text = ""
        if memories:
            mem_text = "\nUSER PRIORITIES & RECALLED MEMORY:\n" + "\n".join(f"- {m}" for m in memories) + "\n"

        failure_text = ""
        if failed_sources:
            failure_text = f"\nNOTICE: The following sources could not be reached: {', '.join(failed_sources)}. Inform the user if relevant.\n"

        return (
            f"User Question: \"{query}\"\n"
            f"{mem_text}"
            f"{failure_text}\n"
            f"AVAILABLE EVIDENCE ITEMS (Cite these using [n]):\n"
            f"-----------------------------------------\n"
            f"{citation_block}\n"
            f"-----------------------------------------\n"
            f"Synthesize a comprehensive, factual answer citing every claim with [n]."
        )

    def _extract_used_citations(self, text: str, evidence_store: EvidenceStore) -> list[Evidence]:
        """Find all [n] markers in the synthesized text and return the matching Evidence objects."""
        found_ids = set()
        for match in re.finditer(r"\[(\d+)\]", text):
            try:
                found_ids.add(int(match.group(1)))
            except ValueError:
                pass

        all_ev = evidence_store.get_all()
        used = [ev for ev in all_ev if ev.evidence_id in found_ids]
        # If no explicit markers found (e.g. in some mock outputs), include all evidence
        if not used and all_ev:
            used = all_ev
        return used
