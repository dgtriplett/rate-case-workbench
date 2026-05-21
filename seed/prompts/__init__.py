"""Prompt library for the synthetic NLPG data generator.

Each module exposes a single ``build_messages(facts, **kwargs)`` function that returns
the OpenAI ``messages`` list for the LLM call. Keeping prompts as Python modules
(not raw text files) lets us interpolate the ``nlpg_facts.json`` dict cleanly and
keep the generator deterministic at the prompt level.
"""
from . import application, testimony, data_requests, prior_responses, orders, policies

__all__ = ["application", "testimony", "data_requests", "prior_responses", "orders", "policies"]
