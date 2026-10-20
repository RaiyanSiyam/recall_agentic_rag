"""CLI Entrypoint for Agentic RAG over Live Data and Memory."""
import asyncio
import sys

# Configure UTF-8 encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from apps.api.core.agent import AgenticRAG
from apps.api.core.llm import LLMClient


async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "Summarize Project X"

    print("=" * 70)
    print(">> AGENTIC RAG OVER LIVE DATA & MEMORY")
    print(f"?? User Question: \"{query}\"")
    print("=" * 70)

    agent = AgenticRAG(llm_client=LLMClient())

    print("\n[*] STEP 1: DECOMPOSING QUERY...")
    result = await agent.run(query)

    print(f"Thought: {result.plan.thought_process}")
    print(f"Sub-Questions ({len(result.plan.sub_questions)} planned):")
    for sq in result.plan.sub_questions:
        tag = f"[{sq.target_source.upper()}]"
        print(f"  * {tag:<8} {sq.question} (tool: {sq.tool_hint})")

    print("\n[*] STEP 2: PARALLEL MCP TOOL EXECUTION...")
    for trace in result.traces:
        status_tag = "[OK]" if trace.get("status") == "success" else "[ERR]"
        print(
            f"  {status_tag} Source: {trace['target_source'].upper():<7} | "
            f"Tool: {trace['tool_called']:<26} | "
            f"Items: {trace['evidence_collected']} | "
            f"Latency: {trace['latency_ms']}ms"
        )

    print(f"\n[*] STEP 3: EVIDENCE STORE ({len(result.evidence)} items deduplicated)...")
    for ev in result.evidence:
        print(f"  [{ev.evidence_id}] ({ev.source.upper()}) {ev.snippet[:105]}...")

    print("\n[*] STEP 4: FINAL CITED SYNTHESIS:")
    print("-" * 70)
    print(result.answer)
    print("-" * 70)

    print(f"\n[TIME] Total Execution Time: {result.duration_ms} ms")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
