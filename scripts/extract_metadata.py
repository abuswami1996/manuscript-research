"""Extract structured metadata from a completed ideation agent run.

Reads the workspace files (protocol, critique report, principal notes, etc.),
sends them to an LLM via LangChain structured output, and writes
``output/protocol_metadata.json`` with canonical, filterable fields suitable
for a frontend.

Usage::

    python scripts/extract_metadata.py workspace/runs/default/20260408_175434_093820
    python scripts/extract_metadata.py <run_dir> --model claude-haiku-4
    python scripts/extract_metadata.py <run_dir> --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Controlled vocabularies (Literal unions enforce valid values)
# ---------------------------------------------------------------------------

Specialty = Literal[
    "anesthesiology",
    "biomedical-informatics",
    "cardiac-surgery",
    "cardiology",
    "critical-care",
    "emergency-medicine",
    "endocrinology",
    "epidemiology",
    "gastroenterology",
    "health-informatics",
    "internal-medicine",
    "nephrology",
    "neurology",
    "oncology",
    "ophthalmology",
    "orthopedics",
    "pathology",
    "pediatrics",
    "pharmacology",
    "psychiatry",
    "public-health",
    "pulmonology",
    "radiology",
    "surgery-general",
    "urology",
]

StudyType = Literal[
    "bibliometric-study",
    "case-control",
    "cross-sectional",
    "decision-analytic-model",
    "feasibility-pilot",
    "meta-analysis",
    "mixed-methods",
    "observational-cohort-prospective",
    "observational-cohort-retrospective",
    "observational-registry",
    "randomized-controlled-trial",
    "systematic-review",
]

ReferenceRole = Literal["background", "gap-evidence", "prior-art", "methodology"]

# ---------------------------------------------------------------------------
# Pydantic models — the schema IS the type system
# ---------------------------------------------------------------------------


class Topic(BaseModel):
    id: str = Field(
        description="Lowercase-hyphenated slug, e.g. 'glp1-receptor-agonists', "
        "'point-of-care-ultrasound', 'machine-learning', 'cardiac-surgery'."
    )
    label: str = Field(
        description="Human-readable label, e.g. 'GLP-1 Receptor Agonists'."
    )


class StudyDesign(BaseModel):
    description: str = Field(description="One-sentence plain-text description of the study design.")
    is_multicenter: bool
    has_control_arm: bool
    has_randomization: bool
    estimated_duration_months: int | None = Field(
        default=None, description="Estimated total study duration in months, or null if not stated."
    )
    target_sample_size: int | None = Field(
        default=None, description="Total target enrollment across all arms, or null if not stated."
    )


class IdeationScores(BaseModel):
    novelty: int = Field(ge=1, le=5)
    feasibility: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)


class IdeationProcess(BaseModel):
    domain_chosen: str = Field(description="The broad domain or topic area the surveyor explored.")
    ideas_considered: int = Field(description="Total number of candidate ideas generated.")
    critique_cycles: int = Field(description="Number of ideate/critique loops (usually 1 or 2).")
    selected_idea: str = Field(description="Title of the idea that was selected for the protocol.")
    selection_rationale: str = Field(
        description="2-3 sentence summary of why this idea was chosen."
    )
    scores: IdeationScores


class Reference(BaseModel):
    title: str
    authors: str = Field(description="Short author string, e.g. 'Lincoff AM et al.'")
    year: int
    journal: str
    doi: str | None = None
    pmid: str | None = None
    role: ReferenceRole = Field(
        description="background = establishes state of the field; "
        "gap-evidence = documents the gap this study addresses; "
        "prior-art = related work identified by the critic; "
        "methodology = validates the methods being proposed."
    )


class ProtocolMetadata(BaseModel):
    """Structured metadata extracted from a research study protocol and its
    supporting ideation workspace files."""

    title: str = Field(description="Full protocol title.")
    short_title: str = Field(description="Acronym or short form, e.g. 'CARDIAC-POCUS Registry'.")
    abstract: str = Field(description="2-3 sentence plain-text summary for card displays.")
    keywords: list[str] = Field(description="5-10 keyword strings.")
    specialty: Specialty = Field(description="Primary medical specialty.")
    subspecialties: list[Specialty] = Field(
        description="Additional specialties involved (may be empty)."
    )
    study_type: StudyType
    topics: list[Topic] = Field(
        description="5-10 topic tags. Use lowercase-hyphenated slugs for id."
    )
    study_design: StudyDesign
    primary_outcome: str = Field(description="One-sentence primary outcome description.")
    secondary_outcomes: list[str] = Field(description="Short descriptions of secondary outcomes.")
    data_sources: list[str] = Field(
        description="Databases, registries, or APIs the study uses."
    )
    estimated_budget_usd: int | None = Field(
        default=None, description="Total budget in USD if the protocol includes one."
    )
    ideation: IdeationProcess
    references: list[Reference] = Field(
        description="Top 10-15 most important references from the protocol."
    )


# ---------------------------------------------------------------------------
# Workspace file map
# ---------------------------------------------------------------------------

WORKSPACE_FILES: dict[str, str] = {
    "protocol": "output/study_protocol.md",
    "landscape_report": "survey/landscape_report.md",
    "candidate_ideas": "ideas/candidate_ideas.md",
    "critique_report": "critiques/critique_report.md",
    "novelty_checks": "critiques/novelty_checks.md",
    "principal_notes": "scratchpad/principal_notes.md",
    "critic_notes": "scratchpad/critic_notes.md",
    "raw_sources": "survey/raw_sources.md",
}

EXTRACTION_SYSTEM_PROMPT = """\
You are a metadata extraction assistant. You will be given the contents of \
workspace files from a research ideation agent run. Your job is to extract \
structured metadata about the study protocol that was produced.

Extract information from the provided files accurately. For references, \
include only the 10-15 most important ones cited in the protocol — prioritize \
those that document the gap, establish background, or are cited as prior art \
by the critic. Use DOIs and PMIDs when they appear in the text.

For the ideation section, extract the critic's scores for the selected idea \
from the critique report or principal notes.

For topics, generate 5-10 tags using lowercase-hyphenated slugs as the id. \
Reuse common slugs where applicable: machine-learning, natural-language-processing, \
point-of-care-ultrasound, glp1-receptor-agonists, cardiac-surgery, \
perioperative-safety, clinical-decision-support, staffing-optimization, \
electronic-health-records, bibliometrics, aspiration-risk, atrial-fibrillation, \
acute-kidney-injury, glycemic-management.

Be precise. Do not fabricate information that is not present in the files.\
"""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def read_workspace(run_dir: Path) -> dict[str, str]:
    """Read all existing workspace files and return ``{name: content}``."""
    files: dict[str, str] = {}
    for name, rel_path in WORKSPACE_FILES.items():
        full = run_dir / rel_path
        if full.is_file():
            text = full.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                files[name] = text
    return files


def _build_user_message(files: dict[str, str]) -> str:
    """Assemble file contents into the user message for the LLM."""
    parts: list[str] = []
    for name, content in files.items():
        parts.append(f"=== FILE: {name} ===\n{content}\n")
    return "\n".join(parts)


def _detect_created_at(run_dir: Path) -> str:
    """ISO 8601 timestamp from the protocol file's mtime, or now()."""
    protocol = run_dir / "output" / "study_protocol.md"
    if protocol.is_file():
        mtime = protocol.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def _detect_files(run_dir: Path) -> dict[str, str]:
    """Return the subset of WORKSPACE_FILES that exist on disk."""
    found: dict[str, str] = {}
    for name, rel_path in WORKSPACE_FILES.items():
        if (run_dir / rel_path).is_file():
            found[name] = rel_path
    return found


def extract_metadata(run_dir: Path, *, model: str) -> dict:
    """Read workspace, call LLM with structured output, return final dict."""
    files = read_workspace(run_dir)
    if "protocol" not in files:
        raise FileNotFoundError(
            f"No protocol found at {run_dir / 'output' / 'study_protocol.md'}"
        )

    llm = ChatAnthropic(model_name=model)  # type: ignore[call-arg]
    structured_llm = llm.with_structured_output(ProtocolMetadata)

    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=_build_user_message(files)),
    ]

    result = structured_llm.invoke(messages)
    if not isinstance(result, ProtocolMetadata):
        raise TypeError(f"Expected ProtocolMetadata, got {type(result)}")

    output = result.model_dump(mode="json")
    output["protocol_id"] = str(uuid.uuid4())
    output["created_at"] = _detect_created_at(run_dir)
    output["version"] = "1.0"
    output["status"] = "complete"
    output["run_id"] = run_dir.name
    output["files"] = _detect_files(run_dir)

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract structured metadata from a completed ideation run.",
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Path to the ideation run directory (e.g. workspace/runs/default/20260408_...)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Anthropic model name (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON to stdout instead of writing to file.",
    )
    args = parser.parse_args()

    load_dotenv()

    run_dir: Path = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"Error: {run_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    print(f"Extracting metadata from: {run_dir}")
    print(f"Model: {args.model}")

    metadata = extract_metadata(run_dir, model=args.model)
    json_str = json.dumps(metadata, indent=2, ensure_ascii=False)

    if args.dry_run:
        print(json_str)
    else:
        out_path = run_dir / "output" / "protocol_metadata.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_str + "\n", encoding="utf-8")
        print(f"Written to: {out_path}")


if __name__ == "__main__":
    main()
