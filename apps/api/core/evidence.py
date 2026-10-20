"""Evidence Store and citation tracking model."""
import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Pydantic model representing a verified factual claim from an MCP data source."""
    evidence_id: int = Field(description="1-based integer citation number, e.g. 1 for [1]")
    source: str = Field(description="Source name: 'gmail', 'notion', 'jira'")
    source_url: str = Field(description="Direct link to email, Notion page, or Jira issue")
    snippet: str = Field(description="Relevant factual quote or excerpt extracted from the source")
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    sub_question_id: str = Field(description="Sub-question ID that prompted this retrieval")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceStore:
    """Manages collected evidence with deduplication and numbered citation registry."""

    def __init__(self):
        self._evidence_list: list[Evidence] = []
        self._seen_fingerprints: set[str] = set()

    def add(
        self,
        source: str,
        source_url: str,
        snippet: str,
        sub_question_id: str,
        confidence: float = 0.95,
        metadata: dict[str, Any] | None = None,
    ) -> Evidence | None:
        """Add new evidence item, automatically deduplicating overlapping snippets."""
        if not snippet or len(snippet.strip()) < 5:
            return None

        # Compute content fingerprint
        norm_text = " ".join(snippet.lower().split())[:200]
        fingerprint = hashlib.sha256(f"{source}:{norm_text}".encode()).hexdigest()

        if fingerprint in self._seen_fingerprints:
            return None

        self._seen_fingerprints.add(fingerprint)
        citation_number = len(self._evidence_list) + 1

        evidence = Evidence(
            evidence_id=citation_number,
            source=source,
            source_url=source_url,
            snippet=snippet.strip(),
            sub_question_id=sub_question_id,
            confidence=confidence,
            metadata=metadata or {},
        )
        self._evidence_list.append(evidence)
        return evidence

    def get_all(self) -> list[Evidence]:
        return list(self._evidence_list)

    def is_empty(self) -> bool:
        return len(self._evidence_list) == 0

    def format_citation_block(self) -> str:
        """Format all evidence for synthesis prompt."""
        if not self._evidence_list:
            return "No evidence collected."

        lines = []
        for ev in self._evidence_list:
            lines.append(
                f"[{ev.evidence_id}] Source: {ev.source.upper()} ({ev.source_url})\n"
                f"    Excerpt: \"{ev.snippet}\""
            )
        return "\n\n".join(lines)
