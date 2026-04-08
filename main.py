"""
Multi-Agent Deep Agent runner (LangChain Deep Agents).

Usage:
    1. For manuscript: place your reference paper at workspace/paper.md
    2. Fill in API keys in .env
    3. Run: python main.py
    4. Or: python main.py "custom prompt"
    5. Or: python main.py manuscript "custom prompt"
    6. Or: AGENT=manuscript python main.py "prompt"

Each run uses an isolated directory under workspace/runs/ (see per-agent env vars;
manuscript uses MANUSCRIPT_PROJECT_ID and MANUSCRIPT_RUN_WORKSPACE).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from agents import AGENTS
from runtime import run as invoke_run
from runtime import stream_run
from utils.langsmith_tracing import log_langsmith_status
from utils.log import init_logger

REPO_ROOT = Path(__file__).resolve().parent
load_dotenv(REPO_ROOT / ".env")


def parse_argv(argv: list[str]) -> tuple[str, str]:
    """Resolve agent id and prompt. If the first arg is a registered id, it selects the agent."""
    if len(argv) <= 1:
        return "manuscript", AGENTS["manuscript"].default_prompt
    rest = argv[1:]
    if rest[0] in AGENTS:
        agent_id = rest[0]
        if len(rest) > 1:
            prompt = " ".join(rest[1:])
        else:
            prompt = AGENTS[agent_id].default_prompt
        return agent_id, prompt
    agent_id = os.environ.get("AGENT", "manuscript").strip() or "manuscript"
    if agent_id not in AGENTS:
        agent_id = "manuscript"
    prompt = " ".join(rest)
    return agent_id, prompt


def main() -> None:
    agent_id, user_prompt = parse_argv(sys.argv)
    spec = AGENTS[agent_id]
    log_path = REPO_ROOT / "logs" / f"{agent_id}.log"
    log = init_logger(f"autonomous_research.{agent_id}", log_file=log_path)
    log_langsmith_status(log)
    model = os.environ.get(spec.model_env, spec.default_model)
    run_ws = spec.resolve_run_workspace(REPO_ROOT)
    use_streaming = os.environ.get("STREAM", "1") == "1"
    if use_streaming:
        stream_run(
            agent_id=agent_id,
            prompt=user_prompt,
            model=model,
            log=log,
            log_file=log_path,
            create_agent=spec.create_agent,
            run_workspace=run_ws,
            seed_workspace=spec.seed_workspace,
            success_message=spec.success_message,
        )
    else:
        invoke_run(
            agent_id=agent_id,
            prompt=user_prompt,
            model=model,
            log=log,
            log_file=log_path,
            create_agent=spec.create_agent,
            run_workspace=run_ws,
            seed_workspace=spec.seed_workspace,
        )


if __name__ == "__main__":
    main()
