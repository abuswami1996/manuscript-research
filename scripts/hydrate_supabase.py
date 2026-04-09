"""Hydrate Supabase with protocol metadata and workspace files.

Reads ``protocol_metadata.json`` from completed ideation runs, upserts all
tables, and uploads markdown files to Supabase Storage.

Usage::

    python scripts/hydrate_supabase.py workspace/runs/default/20260408_175434_093820
    python scripts/hydrate_supabase.py --all
    python scripts/hydrate_supabase.py --all --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent / "workspace" / "runs"

FILE_DISPLAY_NAMES: dict[str, str] = {
    "protocol": "Study Protocol",
    "landscape_report": "Landscape Report",
    "candidate_ideas": "Candidate Ideas",
    "critique_report": "Critique Report",
    "novelty_checks": "Novelty Checks",
    "principal_notes": "Principal Notes",
    "critic_notes": "Critic Notes",
    "raw_sources": "Raw Sources",
}

TAB_ORDER = list(FILE_DISPLAY_NAMES.keys())

STORAGE_BUCKET = "protocol-files"


def _load_metadata(run_dir: Path) -> dict | None:
    meta_path = run_dir / "output" / "protocol_metadata.json"
    if not meta_path.is_file():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _upsert_protocol(sb, meta: dict) -> None:
    """Upsert the main protocols row."""
    ideation = meta.get("ideation", {})
    scores = ideation.get("scores", {})
    row = {
        "id": meta["protocol_id"],
        "run_id": meta["run_id"],
        "title": meta["title"],
        "short_title": meta["short_title"],
        "abstract": meta["abstract"],
        "keywords": meta.get("keywords", []),
        "specialty": meta["specialty"],
        "subspecialties": meta.get("subspecialties", []),
        "study_type": meta["study_type"],
        "primary_outcome": meta.get("primary_outcome", ""),
        "secondary_outcomes": meta.get("secondary_outcomes", []),
        "data_sources": meta.get("data_sources", []),
        "estimated_budget_usd": meta.get("estimated_budget_usd"),
        "status": meta.get("status", "complete"),
        "version": meta.get("version", "1.0"),
        "created_at": meta["created_at"],
        "domain_chosen": ideation.get("domain_chosen"),
        "ideas_considered": ideation.get("ideas_considered"),
        "critique_cycles": ideation.get("critique_cycles"),
        "selected_idea": ideation.get("selected_idea"),
        "selection_rationale": ideation.get("selection_rationale"),
        "score_novelty": scores.get("novelty"),
        "score_feasibility": scores.get("feasibility"),
        "score_impact": scores.get("impact"),
    }
    sb.table("protocols").upsert(row, on_conflict="id").execute()


def _upsert_topics(sb, meta: dict) -> None:
    pid = meta["protocol_id"]
    topics = meta.get("topics", [])

    if topics:
        topic_rows = [{"id": t["id"], "label": t["label"]} for t in topics]
        sb.table("topics").upsert(topic_rows, on_conflict="id").execute()

    sb.table("protocol_topics").delete().eq("protocol_id", pid).execute()
    if topics:
        junction = [{"protocol_id": pid, "topic_id": t["id"]} for t in topics]
        sb.table("protocol_topics").insert(junction).execute()


def _upsert_references(sb, meta: dict) -> None:
    pid = meta["protocol_id"]
    sb.table("protocol_references").delete().eq("protocol_id", pid).execute()
    refs = meta.get("references", [])
    if refs:
        rows = [
            {
                "protocol_id": pid,
                "title": r["title"],
                "authors": r["authors"],
                "year": r["year"],
                "journal": r["journal"],
                "doi": r.get("doi"),
                "pmid": r.get("pmid"),
                "role": r["role"],
                "sort_order": i,
            }
            for i, r in enumerate(refs)
        ]
        sb.table("protocol_references").insert(rows).execute()


def _upsert_study_design(sb, meta: dict) -> None:
    pid = meta["protocol_id"]
    sd = meta.get("study_design", {})
    if not sd:
        return
    row = {
        "protocol_id": pid,
        "description": sd.get("description", ""),
        "is_multicenter": sd.get("is_multicenter", False),
        "has_control_arm": sd.get("has_control_arm", False),
        "has_randomization": sd.get("has_randomization", False),
        "estimated_duration_months": sd.get("estimated_duration_months"),
        "target_sample_size": sd.get("target_sample_size"),
    }
    sb.table("study_designs").upsert(row, on_conflict="protocol_id").execute()


def _upsert_rejected_ideas(sb, meta: dict) -> None:
    pid = meta["protocol_id"]
    sb.table("rejected_ideas").delete().eq("protocol_id", pid).execute()
    ideas = meta.get("rejected_ideas", [])
    if ideas:
        rows = [
            {
                "protocol_id": pid,
                "title": idea["title"],
                "verdict": idea.get("verdict", "REJECT"),
                "reason": idea.get("reason", ""),
                "score_novelty": idea.get("scores", {}).get("novelty", 0),
                "score_feasibility": idea.get("scores", {}).get("feasibility", 0),
                "score_impact": idea.get("scores", {}).get("impact", 0),
                "sort_order": i,
            }
            for i, idea in enumerate(ideas)
        ]
        sb.table("rejected_ideas").insert(rows).execute()


def _upload_files(sb, meta: dict, run_dir: Path) -> None:
    pid = meta["protocol_id"]
    sb.table("protocol_files").delete().eq("protocol_id", pid).execute()

    files_map = meta.get("files", {})
    rows = []
    for logical_name, rel_path in files_map.items():
        local_path = run_dir / rel_path
        if not local_path.is_file():
            continue

        storage_path = f"protocols/{pid}/{logical_name}.md"
        content = local_path.read_bytes()

        try:
            sb.storage.from_(STORAGE_BUCKET).upload(
                storage_path,
                content,
                file_options={"content-type": "text/markdown", "upsert": "true"},
            )
        except Exception as e:
            if "Duplicate" in str(e) or "already exists" in str(e):
                sb.storage.from_(STORAGE_BUCKET).update(
                    storage_path,
                    content,
                    file_options={"content-type": "text/markdown"},
                )
            else:
                raise

        display = FILE_DISPLAY_NAMES.get(logical_name, logical_name.replace("_", " ").title())
        rows.append({
            "protocol_id": pid,
            "logical_name": logical_name,
            "storage_path": storage_path,
            "display_name": display,
        })

    if rows:
        sb.table("protocol_files").insert(rows).execute()


def hydrate_run(sb, run_dir: Path, *, force: bool = False) -> bool:
    """Hydrate a single run directory. Returns True if processed."""
    meta = _load_metadata(run_dir)
    if meta is None:
        print(f"  Skipping {run_dir.name}: no protocol_metadata.json")
        return False

    pid = meta["protocol_id"]

    if not force:
        existing = (
            sb.table("protocols").select("id").eq("run_id", meta["run_id"]).execute()
        )
        if existing.data:
            print(f"  Skipping {run_dir.name}: already in database (use --force to re-upload)")
            return False

    print(f"  Hydrating {run_dir.name} (protocol_id={pid})...")
    _upsert_protocol(sb, meta)
    _upsert_topics(sb, meta)
    _upsert_references(sb, meta)
    _upsert_study_design(sb, meta)
    _upsert_rejected_ideas(sb, meta)
    _upload_files(sb, meta, run_dir)
    print(f"  Done: {meta['short_title']}")
    return True


def find_all_runs() -> list[Path]:
    """Find all run directories under workspace/runs/."""
    runs = []
    if not WORKSPACE_ROOT.is_dir():
        return runs
    for project_dir in sorted(WORKSPACE_ROOT.iterdir()):
        if not project_dir.is_dir():
            continue
        for run_dir in sorted(project_dir.iterdir()):
            if run_dir.is_dir() and (run_dir / "output" / "protocol_metadata.json").is_file():
                runs.append(run_dir)
    return runs


def main() -> None:
    import os

    parser = argparse.ArgumentParser(
        description="Hydrate Supabase with protocol data from ideation runs.",
    )
    parser.add_argument(
        "run_dirs",
        nargs="*",
        type=Path,
        help="Path(s) to run directories. Omit if using --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all runs under workspace/runs/.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-upload even if the run is already in the database.",
    )
    args = parser.parse_args()

    load_dotenv()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print(
            "Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    sb = create_client(url, key)

    if args.all:
        run_dirs = find_all_runs()
        print(f"Found {len(run_dirs)} runs with metadata")
    elif args.run_dirs:
        run_dirs = [p.resolve() for p in args.run_dirs]
    else:
        print("Error: provide run directories or use --all", file=sys.stderr)
        sys.exit(1)

    processed = 0
    for run_dir in run_dirs:
        if not run_dir.is_dir():
            print(f"  Skipping {run_dir}: not a directory")
            continue
        if hydrate_run(sb, run_dir, force=args.force):
            processed += 1

    print(f"\nHydrated {processed}/{len(run_dirs)} runs.")


if __name__ == "__main__":
    main()
