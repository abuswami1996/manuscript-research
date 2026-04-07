#!/usr/bin/env python3
"""Build manuscript.docx from manuscript.md with figures embedded via Pandoc."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_run = os.environ.get("MANUSCRIPT_RUN_WORKSPACE", "").strip()
if _run:
    WORKSPACE = Path(_run).expanduser()
    WORKSPACE = WORKSPACE.resolve() if WORKSPACE.is_absolute() else (ROOT / WORKSPACE).resolve()
else:
    WORKSPACE = ROOT / "workspace"
MD_IN = WORKSPACE / "output" / "manuscript.md"
DOCX_OUT = WORKSPACE / "output" / "manuscript.docx"

# *(See Figure N: /analysis/foo.png)* -> embedded image (paths relative to workspace/)
FIGURE_LINE = re.compile(
    r"^\*\(See Figure (\d+): /analysis/([^)]+)\)\*\s*$",
    re.MULTILINE,
)


def inject_figure_images(markdown: str) -> str:
    def repl(m: re.Match[str]) -> str:
        num, filename = m.group(1), m.group(2)
        return f"\n\n![Figure {num}](analysis/{filename})\n\n"

    return FIGURE_LINE.sub(repl, markdown)


def main() -> int:
    if not MD_IN.is_file():
        print(f"Missing {MD_IN}", file=sys.stderr)
        return 1

    body = inject_figure_images(MD_IN.read_text(encoding="utf-8"))

    cmd = [
        "pandoc",
        "-f",
        "markdown",
        "-t",
        "docx",
        "-o",
        str(DOCX_OUT),
        "--resource-path",
        str(WORKSPACE),
        "-",
    ]
    subprocess.run(cmd, input=body.encode("utf-8"), cwd=str(ROOT), check=True)
    print(f"Wrote {DOCX_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
