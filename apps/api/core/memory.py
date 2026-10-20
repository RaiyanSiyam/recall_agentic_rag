"""Short-Term and Long-Term Memory Manager with Read/Write Policies."""
import logging
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from apps.api.core.llm import LLMClient

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.getenv("SQLITE_DB_PATH", "./data/memory.db")


class MemoryFact(BaseModel):
    id: int | None = None
    fact_text: str
    category: str = "project_fact"
    source: str = "extracted"
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class ExtractedMemories(BaseModel):
    facts: list[str] = Field(
        default_factory=list,
        description="List of durable, reusable facts or user priorities extracted from the interaction",
    )


MEMORY_EXTRACTOR_PROMPT = """You are a Memory Extractor for an intelligent agent.
Analyze the user's question and the agent's answer to identify any durable, persistent facts, user preferences, or stated project priorities worth remembering.

EXAMPLES OF MEMORY-WORTHY FACTS:
- "Project X = high priority"
- "User is focusing on SOC2 compliance"
- "Sarah Chen is the executive sponsor for Project X"

Do NOT remember ephemeral questions or temporary chit-chat.
Return an ExtractedMemories object containing only durable facts. If none, return empty list.
"""


class ShortTermMemory:
    """Manages session-level conversation turns and current run scratchpad."""

    def __init__(self):
        # session_id -> list of {"role": str, "content": str, "timestamp": str}
        self._sessions: dict[str, list[dict[str, Any]]] = {}

    def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
        })

    def get_history(self, session_id: str, limit: int = 6) -> list[dict[str, Any]]:
        return self._sessions.get(session_id, [])[-limit:]

    def get_formatted_context(self, session_id: str, limit: int = 4) -> str:
        history = self.get_history(session_id, limit=limit)
        if not history:
            return ""
        return "\n".join(f"{h['role'].upper()}: {h['content']}" for h in history)

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]


class LongTermMemory:
    """SQLite-backed persistent memory for user-stated facts, priorities, and past Q&A."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS persistent_facts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fact_text TEXT NOT NULL UNIQUE,
                        category TEXT NOT NULL,
                        source TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS past_qa (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT NOT NULL,
                        answer_snippet TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
        finally:
            conn.close()

    def add_fact(
        self,
        fact_text: str,
        category: str = "project_fact",
        source: str = "manual",
    ) -> MemoryFact | None:
        clean_text = fact_text.strip()
        if not clean_text:
            return None

        now = datetime.now(UTC).isoformat()
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO persistent_facts (fact_text, category, source, created_at) VALUES (?, ?, ?, ?)",
                    (clean_text, category, source, now),
                )
                row_id = cursor.lastrowid
                return MemoryFact(
                    id=row_id,
                    fact_text=clean_text,
                    category=category,
                    source=source,
                    created_at=now,
                )
        except Exception as e:
            logger.error(f"Failed to add fact: {e}")
            return None
        finally:
            conn.close()

    def list_facts(self) -> list[dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, fact_text, category, source, created_at FROM persistent_facts ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def delete_fact(self, fact_id: int) -> bool:
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM persistent_facts WHERE id = ?", (fact_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def clear_all(self):
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM persistent_facts")
                cursor.execute("DELETE FROM past_qa")
        finally:
            conn.close()

    def save_qa(self, question: str, answer_snippet: str):
        now = datetime.now(UTC).isoformat()
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO past_qa (question, answer_snippet, created_at) VALUES (?, ?, ?)",
                    (question.strip(), answer_snippet[:300].strip(), now),
                )
        finally:
            conn.close()


class MemoryManager:
    """Coordinates read policy (pre-planning retrieval) and write policy (post-synthesis extraction)."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, llm_client: LLMClient | None = None):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(db_path=db_path)
        self.llm = llm_client or LLMClient()

    # --- READ POLICY ---
    def retrieve_relevant_memories(self, query: str, limit: int = 5) -> list[str]:
        """
        Read Policy: Retrieve user facts and priorities relevant to the incoming query.
        Matches keywords and prioritizes explicit user constraints.
        """
        all_facts = self.long_term.list_facts()
        if not all_facts:
            return []

        q_tokens = set(query.lower().split())
        scored_facts = []

        for fact in all_facts:
            f_text = fact["fact_text"]
            f_tokens = set(f_text.lower().split())
            overlap = len(q_tokens.intersection(f_tokens))

            # Bonus for explicit priority facts
            if fact.get("category") == "priority" or "priority" in f_text.lower():
                overlap += 3

            scored_facts.append((overlap, f_text))

        # Sort descending by relevance
        scored_facts.sort(key=lambda x: x[0], reverse=True)
        return [f[1] for f in scored_facts[:limit]]

    # --- WRITE POLICY ---
    async def extract_and_persist(self, user_query: str, synthesized_answer: str) -> list[str]:
        """
        Write Policy: Extracts durable facts from user statements or synthesis and saves to long-term memory.
        """
        q_lower = user_query.lower()

        # Deterministic extraction for explicit user statements (e.g. "Project X = high priority")
        saved_facts = []
        if "=" in user_query or "remember that" in q_lower or "priority" in q_lower:
            if "=" in user_query:
                parts = user_query.split("=", 1)
                fact_str = f"{parts[0].strip()} = {parts[1].strip()}"
                self.long_term.add_fact(fact_str, category="priority", source="user_statement")
                saved_facts.append(fact_str)
            elif "remember that" in q_lower:
                idx = q_lower.find("remember that") + len("remember that")
                fact_str = user_query[idx:].strip().rstrip(".")
                self.long_term.add_fact(fact_str, category="user_preference", source="user_statement")
                saved_facts.append(fact_str)

        # Record QA summary
        self.long_term.save_qa(user_query, synthesized_answer)

        # Use LLM to extract additional durable facts if query provided new insights
        try:
            prompt = f"User Input: \"{user_query}\"\nAgent Answer: \"{synthesized_answer[:400]}\""
            extracted: ExtractedMemories = await self.llm.generate_structured(
                prompt=prompt,
                response_model=ExtractedMemories,
                system_prompt=MEMORY_EXTRACTOR_PROMPT,
            )
            for f in extracted.facts:
                if f not in saved_facts:
                    self.long_term.add_fact(f, category="project_fact", source="extracted")
                    saved_facts.append(f)
        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")

        return saved_facts
