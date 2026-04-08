"""Invoke/stream Deep Agents with shared logging and LangSmith config."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from utils.langsmith_tracing import build_run_config
from utils.log import extract_messages, log_stream_event


def _set_run_workspace_env(run_ws: Path) -> None:
    """Expose active run dir to tools (and legacy MANUSCRIPT_* alias)."""
    s = str(run_ws)
    os.environ["RUN_WORKSPACE"] = s
    os.environ["MANUSCRIPT_RUN_WORKSPACE"] = s


def stream_run(
    *,
    agent_id: str,
    prompt: str,
    model: str,
    log: logging.Logger,
    log_file: Path,
    create_agent: Callable[..., Any],
    run_workspace: Path,
    seed_workspace: Callable[[Path], None] | None = None,
    success_message: Callable[[Path], str] | None = None,
) -> None:
    """Run the agent with streaming output."""
    run_ws = run_workspace
    if seed_workspace:
        seed_workspace(run_ws)
    _set_run_workspace_env(run_ws)
    agent = create_agent(workspace_dir=run_ws, model=model)

    log.info("Model   : %s", model, extra={"tag": "INFO"})
    log.info("Workspace: %s", run_ws, extra={"tag": "INFO"})
    log.info("Log file : %s", log_file, extra={"tag": "INFO"})
    log.info("=" * 60, extra={"tag": "INFO"})

    for event in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        stream_mode="updates",
        config=build_run_config(agent_id),
    ):
        for node_name, node_data in event.items():
            for msg in extract_messages(node_data):
                log_stream_event(log, node_name, msg)

    log.info("=" * 60, extra={"tag": "INFO"})
    if success_message:
        log.info("%s", success_message(run_ws), extra={"tag": "INFO"})
    log.info("Full log at: %s", log_file, extra={"tag": "INFO"})


def run(
    *,
    agent_id: str,
    prompt: str,
    model: str,
    log: logging.Logger,
    log_file: Path,
    create_agent: Callable[..., Any],
    run_workspace: Path,
    seed_workspace: Callable[[Path], None] | None = None,
) -> Any:
    """Run the agent without streaming; return the invoke result."""
    run_ws = run_workspace
    if seed_workspace:
        seed_workspace(run_ws)
    _set_run_workspace_env(run_ws)
    agent = create_agent(workspace_dir=run_ws, model=model)

    log.info("Model   : %s", model, extra={"tag": "INFO"})
    log.info("Workspace: %s", run_ws, extra={"tag": "INFO"})
    log.info("Log file : %s", log_file, extra={"tag": "INFO"})
    log.info("=" * 60, extra={"tag": "INFO"})

    result = agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config=build_run_config(agent_id),
    )

    final_message = result["messages"][-1].content
    log.info("=" * 60, extra={"tag": "INFO"})
    log.info("COMPLETED", extra={"tag": "INFO"})
    log.info("=" * 60, extra={"tag": "INFO"})
    print(final_message)
    return result
