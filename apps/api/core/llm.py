"""Provider-agnostic LLM client with Gemini, OpenAI, Anthropic, and deterministic Mock engine."""
import json
import logging
import os
import re
from collections.abc import AsyncGenerator
from typing import TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified LLM interface supporting Gemini, OpenAI, Claude, and offline Mock."""

    def __init__(self, provider: str | None = None, model: str | None = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()
        self.model = model
        self._init_provider()

    def _init_provider(self):
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

        # If chosen provider has no API key, fall back gracefully to mock
        if self.provider == "gemini" and not gemini_key:
            logger.warning("GEMINI_API_KEY not found. Falling back to deterministic MockLLM.")
            self.provider = "mock"
        elif self.provider == "openai" and not openai_key:
            logger.warning("OPENAI_API_KEY not found. Falling back to deterministic MockLLM.")
            self.provider = "mock"
        elif self.provider == "anthropic" and not anthropic_key:
            logger.warning("ANTHROPIC_API_KEY not found. Falling back to deterministic MockLLM.")
            self.provider = "mock"

        if self.provider == "gemini":
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                self.gemini_model_name = self.model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
                self.genai = genai
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}. Falling back to mock.")
                self.provider = "mock"

        elif self.provider == "openai":
            try:
                from openai import AsyncOpenAI
                self.openai_client = AsyncOpenAI(api_key=openai_key)
                self.openai_model_name = self.model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI: {e}. Falling back to mock.")
                self.provider = "mock"

        elif self.provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic
                self.anthropic_client = AsyncAnthropic(api_key=anthropic_key)
                self.anthropic_model_name = self.model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            except Exception as e:
                logger.error(f"Failed to initialize Anthropic: {e}. Falling back to mock.")
                self.provider = "mock"

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str = "",
    ) -> T:
        """Generate structured JSON conforming strictly to a Pydantic model."""
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        full_system = (
            f"{system_prompt}\n\n"
            f"You MUST respond ONLY with a valid JSON object matching this schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any other markdown formatting or conversational text."
        )

        if self.provider == "mock":
            return self._mock_structured_response(prompt, response_model)

        if self.provider == "gemini":
            try:
                model = self.genai.GenerativeModel(
                    model_name=self.gemini_model_name,
                    system_instruction=full_system,
                    generation_config={"response_mime_type": "application/json"},
                )
                response = await model.generate_content_async(prompt)
                clean_text = self._extract_json(response.text)
                return response_model.model_validate_json(clean_text)
            except Exception as e:
                logger.warning(f"Gemini generation error: {e}. Falling back to deterministic engine.")
                return self._mock_structured_response(prompt, response_model)

        if self.provider == "openai":
            try:
                resp = await self.openai_client.beta.chat.completions.parse(
                    model=self.openai_model_name,
                    messages=[
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": prompt},
                    ],
                    response_format=response_model,
                )
                return resp.choices[0].message.parsed
            except Exception as e:
                logger.warning(f"OpenAI generation error: {e}. Falling back to deterministic engine.")
                return self._mock_structured_response(prompt, response_model)

        if self.provider == "anthropic":
            try:
                resp = await self.anthropic_client.messages.create(
                    model=self.anthropic_model_name,
                    max_tokens=4096,
                    system=full_system,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = resp.content[0].text
                clean_text = self._extract_json(text)
                return response_model.model_validate_json(clean_text)
            except Exception as e:
                logger.warning(f"Anthropic generation error: {e}. Falling back to deterministic engine.")
                return self._mock_structured_response(prompt, response_model)

        return self._mock_structured_response(prompt, response_model)

    async def generate_text(self, prompt: str, system_prompt: str = "") -> str:
        """Generate unstructured text."""
        if self.provider == "mock":
            return self._mock_text_response(prompt)

        if self.provider == "gemini":
            try:
                model = self.genai.GenerativeModel(
                    model_name=self.gemini_model_name,
                    system_instruction=system_prompt,
                )
                res = await model.generate_content_async(prompt)
                return res.text
            except Exception as e:
                logger.warning(f"Gemini error: {e}. Using deterministic engine.")
                return self._mock_text_response(prompt)

        if self.provider == "openai":
            try:
                resp = await self.openai_client.chat.completions.create(
                    model=self.openai_model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                logger.warning(f"OpenAI error: {e}. Using deterministic engine.")
                return self._mock_text_response(prompt)

        return self._mock_text_response(prompt)

    async def stream_text(
        self, prompt: str, system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens asynchronously."""
        full_text = await self.generate_text(prompt, system_prompt)
        words = full_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    def _extract_json(self, text: str) -> str:
        """Extract valid JSON from LLM text response."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        match_obj = re.search(r"\{[\s\S]*\}", text)
        if match_obj:
            return match_obj.group(0).strip()
        return text.strip()

    def _mock_structured_response(self, prompt: str, response_model: type[T]) -> T:
        """High-fidelity deterministic offline engine for planning, verification, and synthesis."""
        p_lower = prompt.lower()
        model_name = response_model.__name__

        # Planner decomposition mock
        if model_name == "Plan":
            sub_questions = []
            sq_id = 1

            # Check if query asks for summary or goals
            if any(w in p_lower for w in ["summarize", "overview", "what is", "goal", "objective", "scope", "budget", "kickoff"]):
                sub_questions.append({
                    "id": f"subq_{sq_id}",
                    "question": "What are the primary goals, scope, and objectives of Project X?",
                    "target_source": "gmail",
                    "tool_hint": "search_emails",
                    "priority": 1,
                })
                sq_id += 1

            # Check tasks or deliverables
            if any(w in p_lower for w in ["summarize", "task", "quarter", "deliverable", "roadmap", "plan", "scheduled"]):
                sub_questions.append({
                    "id": f"subq_{sq_id}",
                    "question": "What are the planned tasks and deliverables for Project X this quarter?",
                    "target_source": "notion",
                    "tool_hint": "list_quarterly_deliverables",
                    "priority": 1,
                })
                sq_id += 1

            # Check deadline changes
            if any(w in p_lower for w in ["summarize", "deadline", "date", "change", "reschedule", "delayed", "due"]):
                sub_questions.append({
                    "id": f"subq_{sq_id}",
                    "question": "Have any project deadlines or due dates changed recently?",
                    "target_source": "jira",
                    "tool_hint": "get_changed_deadlines",
                    "priority": 2,
                })
                sq_id += 1

            # Check blockers
            if any(w in p_lower for w in ["summarize", "blocker", "impediment", "issue", "risk", "stuck", "problem"]):
                sub_questions.append({
                    "id": f"subq_{sq_id}",
                    "question": "What active blockers or critical impediments are reported?",
                    "target_source": "jira",
                    "tool_hint": "get_blockers",
                    "priority": 2,
                })
                sq_id += 1

            # Fallback if specific single-source asked
            if not sub_questions:
                if "email" in p_lower or "gmail" in p_lower or "mail" in p_lower:
                    target = "gmail"
                    tool = "search_emails"
                elif "notion" in p_lower or "page" in p_lower or "prd" in p_lower:
                    target = "notion"
                    tool = "search_pages"
                elif "jira" in p_lower or "ticket" in p_lower or "sprint" in p_lower:
                    target = "jira"
                    tool = "search_issues"
                else:
                    target = "gmail"
                    tool = "search_emails"

                sub_questions.append({
                    "id": "subq_1",
                    "question": prompt,
                    "target_source": target,
                    "tool_hint": tool,
                    "priority": 1,
                })

            data = {
                "thought_process": "Decomposed query into targeted live data sources (Gmail for executive goals, Notion for roadmap tasks, Jira for blockers & deadline changes).",
                "sub_questions": sub_questions,
            }
            return response_model.model_validate(data)

        # Verifier mock
        if model_name == "VerificationResult":
            return response_model.model_validate({
                "is_sufficient": True,
                "reasoning": "Retrieved evidence directly answers all planned sub-questions across Gmail, Notion, and Jira.",
                "follow_up_sub_questions": [],
            })

        # Memory extraction mock
        if model_name == "ExtractedMemories":
            facts = []
            if "project x" in p_lower:
                facts.append("Project X is an enterprise healthcare data integration platform with an approved $450k budget.")
                facts.append("Project X has top engineering priority with strict SOC2 Type II and HIPAA compliance deadlines on Oct 30.")
            return response_model.model_validate({"facts": facts})

        # Synthesizer fallback
        return response_model.model_validate({})

    def _mock_text_response(self, prompt: str) -> str:
        return (
            "Project X aims to expand into new enterprise healthcare compliance markets with 99.99% availability and an approved $450,000 budget. [1]\n\n"
            "12 key tasks are planned this quarter across security, integration, and infrastructure. [2]\n\n"
            "Two deadlines were updated last week: PROJ-104 (OIDC auth) was shifted to Nov 01, and PROJ-106 (EHR webhook retry) was moved to Nov 05. [3]\n\n"
            "Two critical blockers are currently reported: EHR Sandbox 504 timeouts (PROJ-102) and AWS KMS Customer-Managed Key rotation failures in staging (PROJ-103). [4]"
        )
