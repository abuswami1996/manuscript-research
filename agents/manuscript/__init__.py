"""Medical manuscript reproduction Deep Agent (Principal Investigator + subagents)."""

from __future__ import annotations

import shutil
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from agents.manuscript.prompts import (
    DATA_WRANGLER_SYSTEM_PROMPT,
    MANUSCRIPT_WRITER_SYSTEM_PROMPT,
    PRINCIPAL_SYSTEM_PROMPT,
    STATISTICIAN_SYSTEM_PROMPT,
)
from runtime.workspace import resolve_run_workspace
from tools import internet_search, run_python

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

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


def seed_manuscript_run_workspace(run_dir: Path) -> None:
    """Create run dir and copy template paper.md from workspace root if missing."""
    run_dir.mkdir(parents=True, exist_ok=True)
    template = _REPO_ROOT / "workspace" / "paper.md"
    dest = run_dir / "paper.md"
    if template.exists() and not dest.exists():
        shutil.copy2(template, dest)


def resolve_manuscript_run_workspace(repo_root: Path) -> Path:
    """Directory for this run (honors MANUSCRIPT_* env vars)."""
    return resolve_run_workspace(
        repo_root,
        explicit_env="MANUSCRIPT_RUN_WORKSPACE",
        project_id_env="MANUSCRIPT_PROJECT_ID",
    )


def manuscript_success_message(run_ws: Path) -> str:
    return f"Done. Manuscript at: {run_ws / 'output' / 'manuscript.md'}"


def create_manuscript_agent(*, workspace_dir: Path, model: str) -> object:
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
