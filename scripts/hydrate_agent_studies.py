"""Hydrate Supabase with agent study metadata and workspace files.

Reads ``output/agent_study_metadata.json`` from manuscript runs, upserts tables,
and uploads files to the ``agent-study-files`` storage bucket.

Usage::

    python scripts/hydrate_agent_studies.py workspace/runs/bibliometric-analysis/20260408_113608_844572
    python scripts/hydrate_agent_studies.py --all
    python scripts/hydrate_agent_studies.py --all --force
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent / "workspace" / "runs"

STORAGE_BUCKET = "agent-study-files"
AGENT_PROJECT_DEFAULT = "bibliometric-analysis"


def _folder_sort_key(logical_key: str) -> tuple[int, str]:
    parts = logical_key.split("/", 1)
    folder = parts[0] if parts else ""
    order = {"output": 0, "analysis": 1, "data": 2, "scratchpad": 3}.get(folder, 99)
    return (order, logical_key)


def _display_name(logical_key: str) -> str:
    base = logical_key.rsplit("/", 1)[-1]
    return base.replace("_", " ").replace("-", " ").title()


def _load_metadata(run_dir: Path) -> dict | None:
    meta_path = run_dir / "output" / "agent_study_metadata.json"
    if not meta_path.is_file():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _upsert_study(sb, meta: dict) -> None:
    row = {
        "id": meta["study_id"],
        "run_id": meta["run_id"],
        "agent_project": meta.get("agent_project", AGENT_PROJECT_DEFAULT),
        "title": meta["title"],
        "short_title": meta["short_title"],
        "abstract": meta["abstract"],
        "keywords": meta.get("keywords", []),
        "specialty": meta["specialty"],
        "subspecialties": meta.get("subspecialties", []),
        "study_type": meta["study_type"],
        "replication_summary": meta.get("replication_summary", ""),
        "key_findings": meta.get("key_findings", ""),
        "data_sources": meta.get("data_sources", []),
        "primary_outcome": meta.get("primary_outcome", ""),
        "status": meta.get("status", "complete"),
        "version": meta.get("version", "1.0"),
        "created_at": meta["created_at"],
    }
    sb.table("agent_studies").upsert(row, on_conflict="id").execute()


def _upsert_topics(sb, meta: dict) -> None:
    sid = meta["study_id"]
    topics = meta.get("topics", [])

    if topics:
        topic_rows = [{"id": t["id"], "label": t["label"]} for t in topics]
        sb.table("topics").upsert(topic_rows, on_conflict="id").execute()

    sb.table("agent_study_topics").delete().eq("study_id", sid).execute()
    if topics:
        junction = [{"study_id": sid, "topic_id": t["id"]} for t in topics]
        sb.table("agent_study_topics").insert(junction).execute()


def _upload_files(sb, meta: dict, run_dir: Path) -> None:
    sid = meta["study_id"]
    sb.table("agent_study_files").delete().eq("study_id", sid).execute()

    files_map = meta.get("files", {})
    if not files_map:
        return

    sorted_keys = sorted(files_map.keys(), key=_folder_sort_key)
    rows: list[dict] = []

    for sort_order, logical_key in enumerate(sorted_keys):
        info = files_map[logical_key]
        rel_path = info.get("path", logical_key)
        local_path = run_dir / rel_path
        if not local_path.is_file():
            print(f"    Skip missing file: {rel_path}")
            continue

        mime = info.get("mime_type", "application/octet-stream")
        preview_ok = info.get("preview_eligible", True)
        size = int(info.get("bytes", local_path.stat().st_size))

        storage_path = f"agent-studies/{sid}/{rel_path}"
        content = local_path.read_bytes()

        try:
            sb.storage.from_(STORAGE_BUCKET).upload(
                storage_path,
                content,
                file_options={"content-type": mime, "upsert": "true"},
            )
        except Exception as e:
            if "Duplicate" in str(e) or "already exists" in str(e):
                sb.storage.from_(STORAGE_BUCKET).update(
                    storage_path,
                    content,
                    file_options={"content-type": mime},
                )
            else:
                raise

        rows.append(
            {
                "study_id": sid,
                "logical_name": logical_key,
                "storage_path": storage_path,
                "display_name": _display_name(logical_key),
                "mime_type": mime,
                "bytes": size,
                "sort_order": sort_order,
                "preview_eligible": preview_ok,
            }
        )

    if rows:
        sb.table("agent_study_files").insert(rows).execute()


def hydrate_run(sb, run_dir: Path, *, force: bool = False) -> bool:
    meta = _load_metadata(run_dir)
    if meta is None:
        print(f"  Skipping {run_dir.name}: no agent_study_metadata.json")
        return False

    sid = meta["study_id"]
    run_id = meta["run_id"]

    if not force:
        existing = (
            sb.table("agent_studies").select("id").eq("run_id", run_id).execute()
        )
        if existing.data:
            print(
                f"  Skipping {run_dir.name}: already in database (use --force to re-upload)"
            )
            return False

    print(f"  Hydrating {run_dir.name} (study_id={sid})...")
    _upsert_study(sb, meta)
    _upsert_topics(sb, meta)
    _upload_files(sb, meta, run_dir)
    print(f"  Done: {meta['short_title']}")
    return True


def find_all_runs() -> list[Path]:
    runs: list[Path] = []
    project_dir = WORKSPACE_ROOT / AGENT_PROJECT_DEFAULT
    if not project_dir.is_dir():
        return runs
    for run_dir in sorted(project_dir.iterdir()):
        if run_dir.is_dir() and (run_dir / "output" / "agent_study_metadata.json").is_file():
            runs.append(run_dir)
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hydrate Supabase with agent study data from manuscript runs.",
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
        help=f"Scan runs under workspace/runs/{AGENT_PROJECT_DEFAULT}/.",
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
        print(f"Found {len(run_dirs)} agent study runs with metadata")
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

    print(f"\nHydrated {processed}/{len(run_dirs)} agent study runs.")


if __name__ == "__main__":
    main()
