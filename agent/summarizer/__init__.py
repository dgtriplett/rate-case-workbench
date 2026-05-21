"""Summarizer — used by the ingest pipeline to summarize uploaded documents."""
from .agent import summarize_document, SummarizerAgent

__all__ = ["summarize_document", "SummarizerAgent"]
