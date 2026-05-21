"""Redactor — scans text for PII / privileged language and returns spans."""
from .agent import redact_text, RedactorAgent

__all__ = ["redact_text", "RedactorAgent"]
