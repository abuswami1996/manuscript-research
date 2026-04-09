"""Literature search Deep Agent — single flat agent, no subagents."""

from __future__ import annotations

from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from agents.literature_search.prompts import LITERATURE_SEARCH_SYSTEM_PROMPT
from runtime.workspace import resolve_run_workspace
from tools import internet_search, run_python

_WORKSPACE_SUBDIRS = (
    "searches",
    "candidates",
    "screening",
    "output",
    "scratchpad",
    "scripts",
)


def seed_literature_search_workspace(run_dir: Path) -> None:
    """Create the run directory with the expected subdirectory layout."""
    run_dir.mkdir(parents=True, exist_ok=True)
    for subdir in _WORKSPACE_SUBDIRS:
        (run_dir / subdir).mkdir(exist_ok=True)


def resolve_literature_search_workspace(repo_root: Path) -> Path:
    """Directory for this run (honors LITSEARCH_* env vars)."""
    return resolve_run_workspace(
        repo_root,
        explicit_env="LITSEARCH_RUN_WORKSPACE",
        project_id_env="LITSEARCH_PROJECT_ID",
    )


def literature_search_success_message(run_ws: Path) -> str:
    return f"Done. Report at: {run_ws / 'output' / 'selection_report.md'}"


def create_literature_search_agent(*, workspace_dir: Path, model: str) -> object:
    """Create a single-agent literature search Deep Agent (no subagents)."""
    seed_literature_search_workspace(workspace_dir)

    return create_deep_agent(
        model=model,
        tools=[internet_search, run_python],
        system_prompt=LITERATURE_SEARCH_SYSTEM_PROMPT,
        subagents=[],
        backend=FilesystemBackend(root_dir=str(workspace_dir), virtual_mode=True),
        name="literature-search",
    )
