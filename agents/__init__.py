"""Registered top-level Deep Agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agents.ideation import (
    create_ideation_agent,
    ideation_success_message,
    resolve_ideation_workspace,
    seed_ideation_workspace,
)
from agents.literature_search import (
    create_literature_search_agent,
    literature_search_success_message,
    resolve_literature_search_workspace,
    seed_literature_search_workspace,
)
from agents.manuscript import (
    create_manuscript_agent,
    manuscript_success_message,
    resolve_manuscript_run_workspace,
    seed_manuscript_run_workspace,
)

DEFAULT_MANUSCRIPT_PROMPT = (
    "Replicate the analysis in the paper.md file using currently publically available data. "
    "Exclude papers that may have been retracted or withdrawn during that time period. "
    "Come back with a finished manuscript."
)

DEFAULT_IDEATION_PROMPT = (
    "Generate a novel, feasible research study protocol in health sciences or "
    "biomedical informatics. Choose the domain, identify a gap in the literature, "
    "and produce a complete study protocol."
)

DEFAULT_LITERATURE_SEARCH_PROMPT = (
    "Identify 40-50 bibliometric or scientometric studies in health sciences, biomedical "
    "research, or medical informatics that were published between January 1, 1995 and "
    "December 31, 2005 and that use open medical research data sources such as PubMed or "
    "OpenAlex as their primary data source. "
    "Query public bibliographic databases, identify candidate studies based on title, "
    "abstract, keywords, and methods text, apply inclusion and exclusion criteria, resolve "
    "ambiguities, and output a finalized study list with citations and justifications. "
    "Deliver: a structured table of selected studies, inclusion rationale for each study, "
    "exclusion rationale for rejected candidates, and confidence scores for eligibility "
    "determination."
)


@dataclass(frozen=True)
class AgentSpec:
    """Metadata and factory for one Deep Agent app."""

    id: str
    create_agent: Callable[..., Any]
    seed_workspace: Callable[[Path], None]
    resolve_run_workspace: Callable[[Path], Path]
    default_prompt: str
    model_env: str = "MANUSCRIPT_MODEL"
    default_model: str = "anthropic:claude-sonnet-4-6"
    success_message: Callable[[Path], str] | None = None


AGENTS: dict[str, AgentSpec] = {
    "manuscript": AgentSpec(
        id="manuscript",
        create_agent=create_manuscript_agent,
        seed_workspace=seed_manuscript_run_workspace,
        resolve_run_workspace=resolve_manuscript_run_workspace,
        default_prompt=DEFAULT_MANUSCRIPT_PROMPT,
        model_env="MANUSCRIPT_MODEL",
        success_message=manuscript_success_message,
    ),
    "ideation": AgentSpec(
        id="ideation",
        create_agent=create_ideation_agent,
        seed_workspace=seed_ideation_workspace,
        resolve_run_workspace=resolve_ideation_workspace,
        default_prompt=DEFAULT_IDEATION_PROMPT,
        model_env="IDEATION_MODEL",
        success_message=ideation_success_message,
    ),
    "literature_search": AgentSpec(
        id="literature_search",
        create_agent=create_literature_search_agent,
        seed_workspace=seed_literature_search_workspace,
        resolve_run_workspace=resolve_literature_search_workspace,
        default_prompt=DEFAULT_LITERATURE_SEARCH_PROMPT,
        model_env="LITSEARCH_MODEL",
        success_message=literature_search_success_message,
    ),
}

__all__ = [
    "AGENTS",
    "AgentSpec",
    "DEFAULT_IDEATION_PROMPT",
    "DEFAULT_LITERATURE_SEARCH_PROMPT",
    "DEFAULT_MANUSCRIPT_PROMPT",
]
