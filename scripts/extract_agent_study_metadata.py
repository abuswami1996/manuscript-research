"""Extract structured metadata from a completed manuscript / agent study run.

Reads manuscript-oriented workspace files, sends them to an LLM via LangChain
structured output, walks whitelisted directories for a file manifest, and writes
``output/agent_study_metadata.json``.

Usage::

    python scripts/extract_agent_study_metadata.py workspace/runs/bibliometric-analysis/20260408_113608_844572
    python scripts/extract_agent_study_metadata.py <run_dir> --model claude-haiku-4
    python scripts/extract_agent_study_metadata.py <run_dir> --dry-run
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

# Match extract_metadata controlled vocabularies for consistent filters in the app
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


class Topic(BaseModel):
    id: str = Field(description="Lowercase-hyphenated slug.")
    label: str = Field(description="Human-readable label.")


class AgentStudyMetadata(BaseModel):
    """Structured metadata for a manuscript reproduction / agent study run."""

    title: str = Field(description="Full study title from the manuscript.")
    short_title: str = Field(description="Short label or acronym for cards.")
    abstract: str = Field(description="2–4 sentence plain-text summary for listings.")
    keywords: list[str] = Field(description="5–10 keyword strings.")
    specialty: Specialty = Field(description="Primary medical or methods specialty.")
    subspecialties: list[Specialty] = Field(
        default_factory=list, description="Additional specialties (may be empty)."
    )
    study_type: StudyType = Field(
        description="Usually bibliometric-study for bibliometric reproductions."
    )
    topics: list[Topic] = Field(description="5–10 topic tags with slug ids.")
    replication_summary: str = Field(
        description="One paragraph: what prior work or paper this run reproduces or extends."
    )
    key_findings: str = Field(
        description="Short plain-text summary of main quantitative or narrative findings."
    )
    data_sources: list[str] = Field(
        default_factory=list,
        description="Databases, APIs, or corpora used (e.g. PubMed, OpenAlex).",
    )
    primary_outcome: str = Field(
        description="Primary outcome or research question in one sentence."
    )


WORKSPACE_FILES: dict[str, str] = {
    "manuscript": "output/manuscript.md",
    "study_design": "scratchpad/study_design.md",
    "analysis_summary": "analysis/analysis_summary.md",
    "data_dictionary": "data/data_dictionary.md",
    "paper": "paper.md",
}

# Only these top-level directories are scanned for uploadable assets (relative to run_dir)
MANIFEST_DIRS = ("output", "analysis", "data", "scratchpad")

# Files larger than this are not eligible for in-browser CSV/JSON preview
PREVIEW_BYTE_THRESHOLD = 2 * 1024 * 1024

EXTENSION_MIME: dict[str, str] = {
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".py": "text/x-python",
    ".txt": "text/plain",
}

SKIP_NAMES = {".DS_Store"}


EXTRACTION_SYSTEM_PROMPT = """\
You are a metadata extraction assistant. You will be given the contents of \
files from a manuscript reproduction or bibliometric agent run (final \
manuscript, study design notes, analysis summary, etc.).

Extract accurate structured metadata for browsing and filtering in a web app. \
Do not fabricate statistics or citations that are not implied by the text. \
For topics, use lowercase-hyphenated ids and clear labels (e.g. \
cluster-randomised-trials, bibliometrics, pubmed).

For replication_summary, state what prior publication or benchmark the work \
builds on. For key_findings, summarize headline results from the abstract or \
results sections. For data_sources, list databases or tools used (PubMed, etc.\
). For primary_outcome, phrase the main research question or endpoint in one \
sentence.
"""


def read_workspace(run_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name, rel_path in WORKSPACE_FILES.items():
        full = run_dir / rel_path
        if full.is_file():
            text = full.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                files[name] = text
    return files


def _build_user_message(files: dict[str, str]) -> str:
    parts: list[str] = []
    for name, content in files.items():
        parts.append(f"=== FILE: {name} ===\n{content}\n")
    return "\n".join(parts)


def _detect_created_at(run_dir: Path) -> str:
    manuscript = run_dir / "output" / "manuscript.md"
    if manuscript.is_file():
        mtime = manuscript.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    return datetime.now(tz=timezone.utc).isoformat()


def _mime_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in EXTENSION_MIME:
        return EXTENSION_MIME[ext]
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def build_file_manifest(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Walk whitelisted dirs; return logical_key -> manifest entry."""
    manifest: dict[str, dict[str, Any]] = {}
    for top in MANIFEST_DIRS:
        base = run_dir / top
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file():
                continue
            if f.name in SKIP_NAMES:
                continue
            if f.suffix.lower() not in EXTENSION_MIME:
                continue
            rel = f.relative_to(run_dir)
            key = rel.as_posix()
            size = f.stat().st_size
            mime = _mime_for_path(f)
            preview_eligible = size <= PREVIEW_BYTE_THRESHOLD and mime in (
                "text/markdown",
                "text/csv",
                "application/json",
                "text/plain",
                "text/x-python",
            )
            manifest[key] = {
                "path": key,
                "mime_type": mime,
                "bytes": size,
                "preview_eligible": preview_eligible,
            }
    # Include paper.md at run root if present
    paper = run_dir / "paper.md"
    if paper.is_file() and "paper.md" not in manifest:
        size = paper.stat().st_size
        manifest["paper.md"] = {
            "path": "paper.md",
            "mime_type": "text/markdown",
            "bytes": size,
            "preview_eligible": size <= PREVIEW_BYTE_THRESHOLD,
        }
    return manifest


def extract_metadata(run_dir: Path, *, model: str) -> dict[str, Any]:
    files = read_workspace(run_dir)
    if "manuscript" not in files:
        raise FileNotFoundError(
            f"No manuscript at {run_dir / 'output' / 'manuscript.md'}"
        )

    llm = ChatAnthropic(model_name=model)  # type: ignore[call-arg]
    structured_llm = llm.with_structured_output(AgentStudyMetadata)

    messages = [
        SystemMessage(content=EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=_build_user_message(files)),
    ]

    result = structured_llm.invoke(messages)
    if not isinstance(result, AgentStudyMetadata):
        raise TypeError(f"Expected AgentStudyMetadata, got {type(result)}")

    agent_project = run_dir.parent.name if run_dir.parent else "unknown"
    study_id = str(uuid.uuid4())
    manifest = build_file_manifest(run_dir)

    output: dict[str, Any] = result.model_dump(mode="json")
    output["study_id"] = study_id
    output["created_at"] = _detect_created_at(run_dir)
    output["version"] = "1.0"
    output["status"] = "complete"
    output["run_id"] = run_dir.name
    output["agent_project"] = agent_project
    output["files"] = manifest
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract agent study metadata from a manuscript run directory.",
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Path to the run directory (e.g. workspace/runs/bibliometric-analysis/...)",
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

    print(f"Extracting agent study metadata from: {run_dir}")
    print(f"Model: {args.model}")

    metadata = extract_metadata(run_dir, model=args.model)
    json_str = json.dumps(metadata, indent=2, ensure_ascii=False)

    if args.dry_run:
        print(json_str)
    else:
        out_path = run_dir / "output" / "agent_study_metadata.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json_str + "\n", encoding="utf-8")
        print(f"Written to: {out_path}")


if __name__ == "__main__":
    main()
