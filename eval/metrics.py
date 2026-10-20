"""Evaluation Metrics Calculator for Agentic RAG and Baseline Static RAG."""
import re
from typing import Any


def calculate_source_routing_accuracy(
    planned_sources: list[str], expected_sources: list[str]
) -> float:
    """Calculate Recall of expected sources in the plan."""
    if not expected_sources:
        return 1.0

    planned_set = {s.lower() for s in planned_sources}
    expected_set = {s.lower() for s in expected_sources}

    matched = len(planned_set.intersection(expected_set))
    return round(matched / len(expected_set), 3)


def calculate_answer_faithfulness(
    answer: str, expected_facts: list[str]
) -> float:
    """Calculate percentage of expected benchmark facts present in the answer."""
    if not expected_facts:
        return 1.0

    ans_lower = answer.lower()
    matched = 0
    for fact in expected_facts:
        if fact.lower() in ans_lower:
            matched += 1

    return round(matched / len(expected_facts), 3)


def calculate_citation_precision(
    answer: str, citations: list[Any]
) -> float:
    """Calculate proportion of citation markers in answer with valid evidence backing."""
    markers = re.findall(r"\[(\d+)\]", answer)
    if not markers:
        # If no citations were needed or produced
        return 0.0

    valid_ids = {c.evidence_id if hasattr(c, "evidence_id") else c.get("evidence_id") for c in citations}
    valid_markers = sum(1 for m in markers if int(m) in valid_ids)
    return round(valid_markers / len(markers), 3)
