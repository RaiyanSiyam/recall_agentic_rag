"""Unit tests for Short-Term and Long-Term Memory Manager."""
import os

import pytest

from apps.api.core.memory import LongTermMemory, MemoryManager, ShortTermMemory

TEST_DB_PATH = "./data/test_memory.db"


@pytest.fixture(autouse=True)
def clean_test_db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    yield
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


class TestShortTermMemory:
    def test_session_history(self):
        stm = ShortTermMemory()
        session_id = "test-session-1"
        stm.add_message(session_id, "user", "What is Project X?")
        stm.add_message(session_id, "assistant", "Project X is a healthcare integration.")

        history = stm.get_history(session_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

        fmt = stm.get_formatted_context(session_id)
        assert "USER: What is Project X?" in fmt
        assert "ASSISTANT: Project X is a healthcare integration." in fmt


class TestLongTermMemory:
    def test_crud_operations(self):
        ltm = LongTermMemory(db_path=TEST_DB_PATH)
        # Create
        fact = ltm.add_fact("Project X = high priority", category="priority", source="user")
        assert fact is not None
        assert fact.id is not None
        assert fact.fact_text == "Project X = high priority"

        # Read
        facts = ltm.list_facts()
        assert len(facts) == 1
        assert facts[0]["fact_text"] == "Project X = high priority"

        # Delete
        success = ltm.delete_fact(fact.id)
        assert success is True
        assert len(ltm.list_facts()) == 0


@pytest.mark.asyncio
class TestMemoryPolicies:
    async def test_write_and_read_policy(self):
        mgr = MemoryManager(db_path=TEST_DB_PATH)

        # Write policy: extract and persist user fact
        saved = await mgr.extract_and_persist(
            user_query="Please note that Project X = high priority for executive review",
            synthesized_answer="Acknowledged. Project X is prioritized.",
        )
        assert any("Project X = high priority" in s for s in saved)

        # Read policy: retrieve relevant memory for next query
        memories = mgr.retrieve_relevant_memories("What are the main goals of Project X?")
        assert len(memories) > 0
        assert any("Project X = high priority" in m for m in memories)
