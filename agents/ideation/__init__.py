"""Research ideation Deep Agent (Principal + 4 subagents)."""

from __future__ import annotations

from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from agents.ideation.prompts import (
    CRITIC_SYSTEM_PROMPT,
    IDEATOR_SYSTEM_PROMPT,
    PRINCIPAL_SYSTEM_PROMPT,
    PROTOCOL_WRITER_SYSTEM_PROMPT,
    SURVEYOR_SYSTEM_PROMPT,
)
from runtime.workspace import resolve_run_workspace
from tools import internet_search, run_python

_WORKSPACE_SUBDIRS = (
    "survey",
    "ideas",
    "critiques",
    "output",
    "scratchpad",
)

surveyor = {
    "name": "surveyor",
    "description": (
        "Scans recent literature to map the research landscape and identify "
        "gaps, underexplored areas, and methodological opportunities. "
        "Delegate landscape scanning and gap identification here. "
        "Writes to /survey/."
    ),
    "system_prompt": SURVEYOR_SYSTEM_PROMPT,
    "tools": [internet_search, run_python],
}

ideator = {
    "name": "ideator",
    "description": (
        "Reads the landscape report and generates 5-10 candidate study "
        "concepts with hypotheses, methods, and novelty claims. "
        "Delegate creative idea generation here. Writes to /ideas/."
    ),
    "system_prompt": IDEATOR_SYSTEM_PROMPT,
    "tools": [],
}

critic = {
    "name": "critic",
    "description": (
        "Evaluates candidate ideas for novelty, feasibility, and impact. "
        "Runs targeted searches against bibliographic databases to check "
        "for prior work and scores each idea. "
        "Delegate idea evaluation here. Writes to /critiques/."
    ),
    "system_prompt": CRITIC_SYSTEM_PROMPT,
    "tools": [internet_search, run_python],
}

protocol_writer = {
    "name": "protocol-writer",
    "description": (
        "Takes a vetted idea and produces a complete, structured study "
        "protocol with all required sections. "
        "Delegate final protocol writing here. Writes to /output/."
    ),
    "system_prompt": PROTOCOL_WRITER_SYSTEM_PROMPT,
    "tools": [],
}


def seed_ideation_workspace(run_dir: Path) -> None:
    """Create the run directory with the expected subdirectory layout."""
    run_dir.mkdir(parents=True, exist_ok=True)
    for subdir in _WORKSPACE_SUBDIRS:
        (run_dir / subdir).mkdir(exist_ok=True)


def resolve_ideation_workspace(repo_root: Path) -> Path:
    """Directory for this run (honors IDEATION_* env vars)."""
    return resolve_run_workspace(
        repo_root,
        explicit_env="IDEATION_RUN_WORKSPACE",
        project_id_env="IDEATION_PROJECT_ID",
    )


def ideation_success_message(run_ws: Path) -> str:
    return f"Done. Study protocol at: {run_ws / 'output' / 'study_protocol.md'}"


def create_ideation_agent(*, workspace_dir: Path, model: str) -> object:
    """Create the Principal agent with surveyor, ideator, critic, and protocol writer."""
    seed_ideation_workspace(workspace_dir)

    return create_deep_agent(
        model=model,
        tools=[internet_search],
        system_prompt=PRINCIPAL_SYSTEM_PROMPT,
        subagents=[surveyor, ideator, critic, protocol_writer],
        backend=FilesystemBackend(root_dir=str(workspace_dir), virtual_mode=True),
        name="research-ideation-principal",
    )
