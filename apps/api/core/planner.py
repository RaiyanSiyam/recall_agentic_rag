"""Query Planner & Decomposer."""
from typing import Literal

from pydantic import BaseModel, Field

from apps.api.core.llm import LLMClient


class SubQuestion(BaseModel):
    """Decomposed sub-query routed to a specific live MCP data source."""
    id: str = Field(description="Unique identifier for the sub-question, e.g. subq_1")
    question: str = Field(description="Targeted natural language sub-question")
    target_source: Literal["gmail", "notion", "jira"] = Field(
        description="Target live system: 'gmail' for emails/goals, 'notion' for tasks/PRDs, 'jira' for issues/blockers/sprints"
    )
    tool_hint: str = Field(
        description="Specific tool recommended, e.g., 'search_emails', 'query_tasks', 'get_blockers', 'get_changed_deadlines'"
    )
    priority: int = Field(default=1, description="Execution priority (1 = highest)")


class Plan(BaseModel):
    """Execution plan containing decomposed sub-questions."""
    thought_process: str = Field(description="Reasoning behind decomposition and tool assignments")
    sub_questions: list[SubQuestion] = Field(
        description="List of independent sub-questions to be executed in parallel"
    )


PLANNER_SYSTEM_PROMPT = """You are an expert Query Planner in an Agentic RAG system with access to live enterprise data sources via MCP tools:
1. GMAIL (Tool hint: search_emails, get_email):
   - Best for: high-level project goals, executive decisions, steering updates, budget approvals, and team communication.
2. NOTION (Tool hint: query_tasks, list_quarterly_deliverables, search_pages, get_page):
   - Best for: planned tasks, quarterly deliverables, PRD specifications, documentation, and roadmaps.
3. JIRA (Tool hint: search_issues, get_blockers, get_changed_deadlines, get_sprint_status):
   - Best for: live operational status, active blockers/impediments, bug tickets, sprint progress, and changed deadlines.

YOUR INSTRUCTIONS:
- Break down the user question into distinct, focused sub-questions.
- Route each sub-question to the most appropriate data source and suggest a tool hint.
- For broad questions like "Summarize Project X":
  * Split into: Project goals (Gmail), planned tasks (Notion), changed deadlines (Notion/Jira), and blockers (Jira).
- Incorporate any retrieved memories or user priorities provided.
- Independent sub-questions will be executed in parallel.
"""


class Planner:
    """Decomposes user questions into structured sub-questions with target MCP sources."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client or LLMClient()

    async def plan(
        self,
        query: str,
        memories: list[str] | None = None,
        conversation_context: str | None = None,
    ) -> Plan:
        memory_section = ""
        if memories:
            memory_section = "\nRELEVANT PERSISTENT USER MEMORIES & PRIORITIES:\n" + "\n".join(
                f"- {m}" for m in memories
            )

        context_section = ""
        if conversation_context:
            context_section = f"\nRECENT CONVERSATION CONTEXT:\n{conversation_context}\n"

        prompt = (
            f"User Question: \"{query}\"\n"
            f"{memory_section}"
            f"{context_section}\n"
            f"Decompose this question into targeted sub-questions for Gmail, Notion, and Jira."
        )

        plan = await self.llm.generate_structured(
            prompt=prompt,
            response_model=Plan,
            system_prompt=PLANNER_SYSTEM_PROMPT,
        )
        return plan
