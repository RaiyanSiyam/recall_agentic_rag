"""MCP Router & Parallel Tool Executor with timeouts, retries, and partial failure handling."""
import asyncio
import json
import logging
import time
from typing import Any

from apps.api.core.evidence import EvidenceStore
from apps.api.core.planner import SubQuestion
from mcp_servers.gmail.server import server as gmail_server
from mcp_servers.jira.server import server as jira_server
from mcp_servers.notion.server import server as notion_server

logger = logging.getLogger(__name__)


class ToolExecutionTrace(BaseModel := type("BaseModel", (), {})):
    pass


class Router:
    """Dispatches sub-questions to MCP servers in parallel with resilient execution."""

    def __init__(self, evidence_store: EvidenceStore | None = None):
        self.evidence_store = evidence_store or EvidenceStore()
        self.traces: list[dict[str, Any]] = []

    async def execute_subquestion(
        self,
        sub_q: SubQuestion,
        max_retries: int = 2,
        timeout_seconds: float = 6.0,
    ) -> dict[str, Any]:
        """Execute a single sub-question with timeout and exponential backoff retry."""
        start_time = time.perf_counter()
        attempt = 0
        last_error = None

        while attempt <= max_retries:
            attempt += 1
            try:
                raw_result, tool_name = await asyncio.wait_for(
                    self._dispatch_tool(sub_q),
                    timeout=timeout_seconds,
                )
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

                # Parse and ingest evidence
                evidence_count = self._extract_and_store_evidence(
                    raw_result=raw_result,
                    source=sub_q.target_source,
                    sub_q_id=sub_q.id,
                )

                trace_item = {
                    "sub_question_id": sub_q.id,
                    "question": sub_q.question,
                    "target_source": sub_q.target_source,
                    "tool_called": tool_name,
                    "status": "success",
                    "evidence_collected": evidence_count,
                    "latency_ms": duration_ms,
                    "attempts": attempt,
                }
                self.traces.append(trace_item)
                return trace_item

            except TimeoutError:
                last_error = f"Timeout after {timeout_seconds}s"
                logger.warning(f"Sub-question {sub_q.id} timed out (attempt {attempt})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Sub-question {sub_q.id} failed: {e} (attempt {attempt})")

            if attempt <= max_retries:
                await asyncio.sleep(0.2 * (2 ** (attempt - 1)))

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        failed_trace = {
            "sub_question_id": sub_q.id,
            "question": sub_q.question,
            "target_source": sub_q.target_source,
            "tool_called": sub_q.tool_hint,
            "status": "failed",
            "error": last_error,
            "evidence_collected": 0,
            "latency_ms": duration_ms,
            "attempts": attempt,
        }
        self.traces.append(failed_trace)
        return failed_trace

    async def _dispatch_tool(self, sub_q: SubQuestion) -> tuple[str, str]:
        """Route to appropriate MCP server and tool."""
        source = sub_q.target_source.lower()
        tool = sub_q.tool_hint.lower()
        q_lower = sub_q.question.lower()

        if source == "gmail":
            if "get_email" in tool or "msg-" in q_lower:
                msg_id = "msg-101"
                for word in q_lower.split():
                    if word.startswith("msg-"):
                        msg_id = word
                res = await gmail_server.call_tool("get_email", {"message_id": msg_id})
                return res.content[0].text, "get_email"
            else:
                res = await gmail_server.call_tool("search_emails", {"query": sub_q.question})
                return res.content[0].text, "search_emails"

        elif source == "notion":
            if "deliverable" in q_lower or "quarter" in q_lower or "12" in q_lower or "list" in q_lower:
                res = await notion_server.call_tool("list_quarterly_deliverables", {})
                return res.content[0].text, "list_quarterly_deliverables"
            elif "prd" in q_lower or "charter" in q_lower or "doc" in q_lower or "search_pages" in tool:
                res = await notion_server.call_tool("search_pages", {"query": sub_q.question})
                return res.content[0].text, "search_pages"
            else:
                res = await notion_server.call_tool("query_tasks", {"query": sub_q.question})
                return res.content[0].text, "query_tasks"

        elif source == "jira":
            if "blocker" in q_lower or "impediment" in q_lower or "get_blockers" in tool:
                res = await jira_server.call_tool("get_blockers", {})
                return res.content[0].text, "get_blockers"
            elif "deadline" in q_lower or "due" in q_lower or "date" in q_lower or "change" in q_lower:
                res = await jira_server.call_tool("get_changed_deadlines", {})
                return res.content[0].text, "get_changed_deadlines"
            elif "sprint" in q_lower:
                res = await jira_server.call_tool("get_sprint_status", {})
                return res.content[0].text, "get_sprint_status"
            else:
                res = await jira_server.call_tool("search_issues", {"query": sub_q.question})
                return res.content[0].text, "search_issues"

        raise ValueError(f"Unknown data source: {source}")

    def _extract_and_store_evidence(self, raw_result: str, source: str, sub_q_id: str) -> int:
        """Parse MCP tool JSON and add items to EvidenceStore."""
        count = 0
        try:
            data = json.loads(raw_result)
        except Exception:
            # Plain string snippet
            if raw_result and not raw_result.startswith("Error"):
                ev = self.evidence_store.add(
                    source=source,
                    source_url=f"https://{source}.internal",
                    snippet=raw_result[:400],
                    sub_question_id=sub_q_id,
                )
                if ev:
                    count += 1
            return count

        # Gmail messages
        if "messages" in data:
            for msg in data["messages"]:
                snippet = f"{msg['subject']}: {msg['snippet']}"
                ev = self.evidence_store.add(
                    source="gmail",
                    source_url=msg.get("url", f"https://mail.google.com/msg/{msg.get('message_id')}"),
                    snippet=snippet,
                    sub_question_id=sub_q_id,
                    metadata={"from": msg.get("from"), "date": msg.get("date")},
                )
                if ev:
                    count += 1

        # Gmail single email body
        elif "body" in data and data.get("source") == "gmail":
            snippet = f"{data['subject']} (from {data.get('from')}): {data['body'][:400]}"
            ev = self.evidence_store.add(
                source="gmail",
                source_url=data.get("url", "https://mail.google.com"),
                snippet=snippet,
                sub_question_id=sub_q_id,
            )
            if ev:
                count += 1

        # Notion tasks
        elif "tasks" in data:
            tasks = data["tasks"]
            # Add summary evidence for the batch
            task_codes = ", ".join(t["task_code"] for t in tasks[:6])
            summary_snippet = (
                f"Notion Database '{data.get('database', 'Deliverables')}': {len(tasks)} total tasks planned this quarter, "
                f"including key tasks: {task_codes}."
            )
            ev = self.evidence_store.add(
                source="notion",
                source_url="https://notion.so/workspace/deliverables",
                snippet=summary_snippet,
                sub_question_id=sub_q_id,
                metadata={"total_tasks": len(tasks)},
            )
            if ev:
                count += 1

            # Also add specific tasks with changed deadlines or high priority
            for t in tasks:
                if t.get("deadline_changed"):
                    snippet = f"Task {t['task_code']} ({t['title']}): {t.get('change_reason', 'Deadline modified')} (Due: {t['due_date']})."
                    ev = self.evidence_store.add(
                        source="notion",
                        source_url=t.get("url", "https://notion.so"),
                        snippet=snippet,
                        sub_question_id=sub_q_id,
                    )
                    if ev:
                        count += 1

        # Notion pages
        elif "pages" in data:
            for p in data["pages"]:
                snippet = f"Page '{p['title']}': {p.get('snippet', '')}"
                ev = self.evidence_store.add(
                    source="notion",
                    source_url=p.get("url", "https://notion.so"),
                    snippet=snippet,
                    sub_question_id=sub_q_id,
                )
                if ev:
                    count += 1

        # Jira changed deadlines
        elif "changed_deadlines" in data:
            for item in data["changed_deadlines"]:
                snippet = (
                    f"Jira {item['key']} ({item['summary']}): Deadline updated to {item['due_date']}. "
                    f"Details: {item.get('details', '')}"
                )
                ev = self.evidence_store.add(
                    source="jira",
                    source_url=item.get("url", "https://atlassian.net"),
                    snippet=snippet,
                    sub_question_id=sub_q_id,
                )
                if ev:
                    count += 1

        # Jira issues (including blockers)
        elif "issues" in data:
            for issue in data["issues"]:
                blocker_txt = f" [BLOCKER: {issue['blocker_details']}]" if issue.get("is_blocker") else ""
                deadline_txt = f" [Deadline change: {issue.get('deadline_change_details')}]" if issue.get("deadline_changed") else ""
                snippet = f"Jira {issue['key']} ({issue['summary']}) [Status: {issue['status']}, Priority: {issue['priority']}]{blocker_txt}{deadline_txt}: {issue.get('description', '')[:300]}"
                ev = self.evidence_store.add(
                    source="jira",
                    source_url=issue.get("url", f"https://atlassian.net/browse/{issue['key']}"),
                    snippet=snippet,
                    sub_question_id=sub_q_id,
                    metadata={"key": issue["key"], "is_blocker": issue.get("is_blocker", False)},
                )
                if ev:
                    count += 1

        return count

    async def execute_plan_parallel(self, sub_questions: list[SubQuestion]) -> list[dict[str, Any]]:
        """Run all sub-questions concurrently via asyncio.gather."""
        tasks = [self.execute_subquestion(sq) for sq in sub_questions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        clean_results = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                sq = sub_questions[i]
                clean_results.append({
                    "sub_question_id": sq.id,
                    "target_source": sq.target_source,
                    "status": "failed",
                    "error": str(res),
                })
            else:
                clean_results.append(res)

        return clean_results
