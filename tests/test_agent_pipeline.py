"""Unit tests for the agent pipeline: parallel execution, verifier loop, and partial failure handling."""
import pytest

from apps.api.core.agent import AgenticRAG
from apps.api.core.evidence import EvidenceStore
from apps.api.core.llm import LLMClient
from apps.api.core.planner import Plan, Planner, SubQuestion
from apps.api.core.router import Router
from apps.api.core.verifier import Verifier


@pytest.mark.asyncio
class TestPlannerAndRouter:
    async def test_planner_decomposition(self):
        planner = Planner(llm_client=LLMClient(provider="mock"))
        plan = await planner.plan("Summarize Project X")
        assert len(plan.sub_questions) >= 3
        sources = {sq.target_source for sq in plan.sub_questions}
        assert "gmail" in sources
        assert "notion" in sources
        assert "jira" in sources

    async def test_parallel_router_execution(self):
        store = EvidenceStore()
        router = Router(evidence_store=store)
        sub_questions = [
            SubQuestion(
                id="sq1",
                question="What are the goals of Project X?",
                target_source="gmail",
                tool_hint="search_emails",
                priority=1,
            ),
            SubQuestion(
                id="sq2",
                question="What are the deliverables for this quarter?",
                target_source="notion",
                tool_hint="list_quarterly_deliverables",
                priority=1,
            ),
            SubQuestion(
                id="sq3",
                question="What blockers are active?",
                target_source="jira",
                tool_hint="get_blockers",
                priority=1,
            ),
        ]
        results = await router.execute_plan_parallel(sub_questions)
        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)
        assert len(store.get_all()) >= 3

    async def test_evidence_store_deduplication(self):
        store = EvidenceStore()
        ev1 = store.add(
            source="gmail",
            source_url="https://mail.google.com/1",
            snippet="Project X aims to expand into new markets.",
            sub_question_id="sq1",
        )
        assert ev1 is not None

        # Attempt to add exact duplicate
        ev2 = store.add(
            source="gmail",
            source_url="https://mail.google.com/1",
            snippet="Project X aims to expand into new markets.",
            sub_question_id="sq2",
        )
        assert ev2 is None
        assert len(store.get_all()) == 1


@pytest.mark.asyncio
class TestVerifierAndResilience:
    async def test_verifier_evaluation(self):
        verifier = Verifier(llm_client=LLMClient(provider="mock"))
        store = EvidenceStore()
        store.add(
            source="gmail",
            source_url="https://mail.google.com/1",
            snippet="Project X goals: healthcare market expansion.",
            sub_question_id="sq1",
        )
        plan = Plan(
            thought_process="test",
            sub_questions=[
                SubQuestion(
                    id="sq1",
                    question="What are the goals?",
                    target_source="gmail",
                    tool_hint="search_emails",
                )
            ],
        )
        res = await verifier.verify("What are the goals?", plan, store)
        assert res.is_sufficient is True

    async def test_agent_run_end_to_end(self):
        agent = AgenticRAG(llm_client=LLMClient(provider="mock"))
        res = await agent.run("Summarize Project X")
        assert res.iterations <= 2
        assert len(res.evidence) > 0
        assert len(res.citations) > 0
        assert "[" in res.answer and "]" in res.answer

    async def test_partial_failure_tolerance(self, monkeypatch):
        # Simulate Jira failure
        from mcp_servers.jira.server import server as jira_server

        async def broken_call_tool(name, args):
            raise ConnectionError("Jira API connection timed out")

        monkeypatch.setattr(jira_server, "call_tool", broken_call_tool)

        agent = AgenticRAG(llm_client=LLMClient(provider="mock"))
        res = await agent.run("Summarize Project X")

        # Agent should NOT crash; Gmail & Notion should succeed
        assert res.iterations <= 2
        assert any(ev.source == "gmail" for ev in res.evidence)
        assert any(ev.source == "notion" for ev in res.evidence)
        assert "jira" in res.failed_sources
