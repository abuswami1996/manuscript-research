"""Generic per-run workspace directory resolution."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def _sanitize_project_id(raw: str) -> str:
    s = raw.strip()
    if not s:
        return "default"
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


def resolve_run_workspace(
    repo_root: Path,
    *,
    workspace_root: Path | None = None,
    explicit_env: str = "RUN_WORKSPACE",
    project_id_env: str = "RUN_PROJECT_ID",
    default_project_id: str = "default",
) -> Path:
    """Pick the directory for this agent run (virtual FS root + run_python cwd).

    If ``explicit_env`` is set in the environment, use that path (relative paths
    are resolved under ``repo_root``). Otherwise use
    ``<workspace_root>/runs/<project_id>/<timestamp>/``.
    """
    if workspace_root is None:
        workspace_root = repo_root / "workspace"

    explicit = os.environ.get(explicit_env, "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute():
            p = (repo_root / p).resolve()
        else:
            p = p.resolve()
        return p

    project = _sanitize_project_id(os.environ.get(project_id_env, default_project_id))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return (workspace_root / "runs" / project / stamp).resolve()
