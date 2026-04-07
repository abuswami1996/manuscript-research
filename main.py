"""
Multi-Agent Medical Manuscript Reproduction System

Usage:
    1. Place your reference paper at workspace/paper.md (template; copied into each run)
    2. Fill in your API keys in .env
    3. Run: python main.py
    4. Or with a custom prompt: python main.py "Read paper.md and reproduce the study for 2010-2024"

Each run uses an isolated directory: workspace/runs/<MANUSCRIPT_PROJECT_ID>/<timestamp>/
so you can keep prior outputs. Optional env:
    MANUSCRIPT_PROJECT_ID — folder name under workspace/runs/ (default: default)
    MANUSCRIPT_RUN_WORKSPACE — exact path for this run (skips auto folder; for resuming)
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from utils.log import LOG_FILE, extract_messages, init_logger, log_stream_event
from lib.prompts import (
    DATA_WRANGLER_SYSTEM_PROMPT,
    MANUSCRIPT_WRITER_SYSTEM_PROMPT,
    PRINCIPAL_SYSTEM_PROMPT,
    STATISTICIAN_SYSTEM_PROMPT,
)
from lib.tools import internet_search, run_python

from utils.langsmith_tracing import build_run_config, log_langsmith_status

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE_ROOT = Path(__file__).parent / "workspace"
MODEL = os.environ.get("MANUSCRIPT_MODEL", "anthropic:claude-sonnet-4-6")

log = init_logger()
log_langsmith_status(log)


def _sanitize_project_id(raw: str) -> str:
    s = raw.strip()
    if not s:
        return "default"
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


def resolve_run_workspace() -> Path:
    """Directory for this agent run (virtual FS root + run_python cwd)."""
    explicit = os.environ.get("MANUSCRIPT_RUN_WORKSPACE", "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute():
            p = (Path(__file__).parent / p).resolve()
        else:
            p = p.resolve()
        return p
    project = _sanitize_project_id(os.environ.get("MANUSCRIPT_PROJECT_ID", "default"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return (WORKSPACE_ROOT / "runs" / project / stamp).resolve()


def seed_run_workspace(run_dir: Path) -> None:
    """Create run dir and copy template paper.md from workspace root if missing."""
    run_dir.mkdir(parents=True, exist_ok=True)
    template = WORKSPACE_ROOT / "paper.md"
    dest = run_dir / "paper.md"
    if template.exists() and not dest.exists():
        shutil.copy2(template, dest)

# ---------------------------------------------------------------------------
# Subagent Definitions
# ---------------------------------------------------------------------------

data_wrangler = {
    "name": "data-wrangler",
    "description": (
        "Finds, downloads, cleans, and prepares datasets for medical research. "
        "Delegate all data acquisition, cleaning, and preparation tasks here. "
        "Outputs go to /data/."
    ),
    "system_prompt": DATA_WRANGLER_SYSTEM_PROMPT,
    "tools": [internet_search, run_python],
}

statistician = {
    "name": "statistician",
    "description": (
        "Runs statistical analyses and generates publication-quality tables "
        "and figures. Delegate all quantitative analysis, statistical testing, "
        "and visualization here. Reads /data/, writes to /analysis/."
    ),
    "system_prompt": STATISTICIAN_SYSTEM_PROMPT,
    "tools": [run_python],
}

manuscript_writer = {
    "name": "manuscript-writer",
    "description": (
        "Writes complete, publication-ready manuscripts in Markdown. "
        "Delegate final manuscript writing after data and analysis are done. "
        "Reads paper.md and /analysis/, writes /output/manuscript.md."
    ),
    "system_prompt": MANUSCRIPT_WRITER_SYSTEM_PROMPT,
    "tools": [],
}

# ---------------------------------------------------------------------------
# Agent Creation
# ---------------------------------------------------------------------------


def create_manuscript_agent(*, workspace_dir: Path, model: str = MODEL):
    """Create the Principal Investigator agent with all subagents."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ("data", "analysis", "output", "scratchpad"):
        (workspace_dir / subdir).mkdir(exist_ok=True)

    return create_deep_agent(
        model=model,
        tools=[internet_search],
        system_prompt=PRINCIPAL_SYSTEM_PROMPT,
        subagents=[data_wrangler, statistician, manuscript_writer],
        backend=FilesystemBackend(root_dir=str(workspace_dir), virtual_mode=True),
        name="principal-investigator",
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def stream_run(prompt: str, model: str = MODEL):
    """Run the pipeline with streaming output so progress is visible."""
    run_ws = resolve_run_workspace()
    seed_run_workspace(run_ws)
    os.environ["MANUSCRIPT_RUN_WORKSPACE"] = str(run_ws)
    agent = create_manuscript_agent(workspace_dir=run_ws, model=model)

    log.info("Model   : %s", model, extra={"tag": "INFO"})
    log.info("Workspace: %s", run_ws, extra={"tag": "INFO"})
    log.info("Log file : %s", LOG_FILE, extra={"tag": "INFO"})
    log.info("=" * 60, extra={"tag": "INFO"})

    for event in agent.stream(
        {"messages": [{"role": "user", "content": prompt}]},
        stream_mode="updates",
        config=build_run_config(),
    ):
        for node_name, node_data in event.items():
            for msg in extract_messages(node_data):
                log_stream_event(node_name, msg)

    log.info("=" * 60, extra={"tag": "INFO"})
    log.info("Done. Manuscript at: %s", run_ws / "output" / "manuscript.md", extra={"tag": "INFO"})
    log.info("Full log at: %s", LOG_FILE, extra={"tag": "INFO"})


def run(prompt: str, model: str = MODEL):
    """Run the pipeline (no streaming) and return the final result."""
    run_ws = resolve_run_workspace()
    seed_run_workspace(run_ws)
    os.environ["MANUSCRIPT_RUN_WORKSPACE"] = str(run_ws)
    agent = create_manuscript_agent(workspace_dir=run_ws, model=model)

    log.info("Model   : %s", model, extra={"tag": "INFO"})
    log.info("Workspace: %s", run_ws, extra={"tag": "INFO"})
    log.info("Log file : %s", LOG_FILE, extra={"tag": "INFO"})
    log.info("=" * 60, extra={"tag": "INFO"})

    result = agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config=build_run_config(),
    )

    final_message = result["messages"][-1].content
    log.info("=" * 60, extra={"tag": "INFO"})
    log.info("COMPLETED", extra={"tag": "INFO"})
    log.info("=" * 60, extra={"tag": "INFO"})
    print(final_message)
    return result


if __name__ == "__main__":
    default_prompt = (
        "Replicate the analysis in the paper.md file using currently publically available data. Exclude papers that may have been retracted or withdrawn during that time period. Come back with a finished manuscript."
    )
    user_prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else default_prompt

    use_streaming = os.environ.get("STREAM", "1") == "1"
    if use_streaming:
        stream_run(user_prompt)
    else:
        run(user_prompt)
