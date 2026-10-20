"""Sanitization utilities to protect against indirect prompt injection from live/demo data."""
import re

# Common prompt injection patterns detected in untrusted content
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+override[:\s]", re.IGNORECASE),
    re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<\s*system\s*>.*?<\s*/\s*system\s*>", re.IGNORECASE | re.DOTALL),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
]


def sanitize_text(text: str, max_chars: int = 2500) -> str:
    """
    Sanitize untrusted text from external data sources (emails, documents, issue trackers).
    Neutralizes prompt injection directives and bounds maximum character length.
    """
    if not text:
        return ""

    sanitized = text
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECURITY_RISK]", sanitized)

    # Neutralize control XML/HTML delimiters
    sanitized = sanitized.replace("<|im_start|>", "").replace("<|im_end|>", "")
    sanitized = sanitized.replace("```system", "```raw_data")

    # Limit maximum snippet length
    if len(sanitized) > max_chars:
        sanitized = sanitized[:max_chars] + "... [truncated]"

    return sanitized.strip()
