"""LangSmith observability helpers for the LangGraph deep agent."""

from __future__ import annotations

import logging
import os
from typing import Any


def _truthy(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in ("1", "true", "yes", "on")


def tracing_enabled() -> bool:
    return _truthy(os.environ.get("LANGSMITH_TRACING")) or _truthy(
        os.environ.get("LANGCHAIN_TRACING_V2")
    )


def api_key_configured() -> bool:
    return bool(os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY"))


def project_name() -> str:
    return (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or "default"
    )


def build_run_config() -> dict[str, Any]:
    """RunnableConfig fragment merged into invoke/stream for LangSmith."""
    return {
        "tags": ["medical-manuscript", "deepagents"],
        "metadata": {"app": "autonomous-research-manuscript"},
    }


def log_langsmith_status(log: logging.Logger) -> None:
    """Log whether traces will be sent (no secrets)."""
    if not tracing_enabled():
        log.info(
            "LangSmith: tracing off (set LANGSMITH_TRACING=true to enable)",
            extra={"tag": "INFO"},
        )
        return
    if not api_key_configured():
        log.warning(
            "LangSmith: tracing requested but no LANGSMITH_API_KEY or LANGCHAIN_API_KEY set",
            extra={"tag": "INFO"},
        )
        return
    log.info(
        "LangSmith: tracing on (project=%s)",
        project_name(),
        extra={"tag": "INFO"},
    )
