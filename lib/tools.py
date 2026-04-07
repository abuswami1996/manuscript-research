"""Custom tools available to agents: web search and Python execution."""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal

from tavily import TavilyClient

log = logging.getLogger("manuscript")

_ROOT = Path(__file__).parent.resolve()


def get_workspace_dir() -> Path:
    """Active run directory set by main.py via MANUSCRIPT_RUN_WORKSPACE."""
    p = os.environ.get("MANUSCRIPT_RUN_WORKSPACE", "").strip()
    if p:
        return Path(p).expanduser().resolve()
    return _ROOT / "workspace"

_tavily_client: TavilyClient | None = None


def _get_tavily() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        import os
        _tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))
    return _tavily_client


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> dict:
    """Search the internet for information. Use this to find data sources,
    research background literature, methodology references, or any other
    information needed to support the research."""
    log.info("Searching: %s", query, extra={"tag": "TOOL"})
    t0 = time.time()
    result = _get_tavily().search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )
    n = len(result.get("results", []))
    log.info("Search returned %d results (%.1fs)", n, time.time() - t0, extra={"tag": "TOOL"})
    return result


def run_python(code: str, timeout_seconds: int = 300) -> str:
    """Execute a Python script and return its output (stdout + stderr).

    The script runs with its working directory set to the workspace, so it
    can read and write files using relative paths such as 'data/dataset.csv'
    or 'analysis/figure1.png'.

    Available libraries: pandas, numpy, scipy, statsmodels, matplotlib,
    seaborn, requests, openpyxl.

    For plots, always save figures to files
    (e.g. plt.savefig('analysis/figure1.png', dpi=300, bbox_inches='tight'))
    instead of calling plt.show().

    Args:
        code: The Python source code to execute.
        timeout_seconds: Maximum wall-clock time for the script (default 300).

    Returns:
        Combined stdout and stderr, or an error message.
    """
    workspace = get_workspace_dir()
    workspace.mkdir(parents=True, exist_ok=True)

    first_lines = "\n".join(code.strip().splitlines()[:5])
    log.info("Running Python script (%d chars):\n    %s",
             len(code), first_lines.replace("\n", "\n    "), extra={"tag": "TOOL"})

    script_file = workspace / "_tmp_script.py"
    t0 = time.time()
    try:
        script_file.write_text(code, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script_file)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed = time.time() - t0
        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append("--- STDERR ---\n" + result.stderr)
        if result.returncode != 0:
            output_parts.append(f"--- Process exited with code {result.returncode} ---")
            log.warning("Script failed (exit %d, %.1fs)", result.returncode, elapsed,
                        extra={"tag": "TOOL"})
        else:
            log.info("Script finished OK (%.1fs)", elapsed, extra={"tag": "TOOL"})
        output = "\n".join(output_parts).strip() or "(no output)"
        preview = output[:300] + "..." if len(output) > 300 else output
        log.debug("Script output:\n    %s", preview.replace("\n", "\n    "), extra={"tag": "TOOL"})
        return output
    except subprocess.TimeoutExpired:
        log.warning("Script timed out after %ds", timeout_seconds, extra={"tag": "TOOL"})
        return f"Error: Script exceeded the {timeout_seconds}s timeout."
    except Exception as exc:
        log.warning("Script error: %s", exc, extra={"tag": "TOOL"})
        return f"Error executing Python code: {exc}"
    finally:
        script_file.unlink(missing_ok=True)
