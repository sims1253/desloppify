"""Backward-compatible re-export for scan LLM reporting helpers."""

from __future__ import annotations

from .reporting.agent_context import (
    is_agent_environment,
    is_agent_environment as _is_agent_environment,  # backward compat
    print_llm_summary,
    print_llm_summary as _print_llm_summary,  # backward compat
    auto_update_skill,
)

__all__ = ["print_llm_summary", "_print_llm_summary", "auto_update_skill", "is_agent_environment", "_is_agent_environment"]
