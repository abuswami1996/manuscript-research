"""Logging setup and stream event helpers."""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Default log path when init_logger is called without log_file (legacy).
LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "run.log"


class _Formatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[90m",
        "INFO": "\033[36m",
        "WARNING": "\033[33m",
        "TOOL": "\033[35m",
        "AGENT": "\033[32m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        color = self.COLORS.get(record.levelname, "")
        tag = getattr(record, "tag", record.levelname)
        msg = record.getMessage()
        return f"{color}[{ts}] [{tag}]{self.RESET} {msg}"


def init_logger(
    name: str = "autonomous_research",
    *,
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure and return a logger. Each ``name`` is configured at most once."""
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.DEBUG)
    console.setFormatter(_Formatter())
    log.addHandler(console)

    path = log_file if log_file is not None else LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(path, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    log.addHandler(fh)

    return log


# ---------------------------------------------------------------------------
# Stream event helpers
# ---------------------------------------------------------------------------


def extract_messages(node_data):
    """Safely extract a list of messages from a LangGraph stream node update."""
    if not isinstance(node_data, dict) or "messages" not in node_data:
        return []
    raw = node_data["messages"]
    if hasattr(raw, "value"):
        raw = raw.value
    if not isinstance(raw, list):
        raw = [raw]
    return raw


def log_stream_event(log: logging.Logger, node_name: str, msg):
    """Log a single message from the stream with full detail."""
    if not hasattr(msg, "content") and not hasattr(msg, "tool_calls"):
        return

    agent_name = getattr(msg, "additional_kwargs", {}).get(
        "lc_agent_name", node_name
    )
    msg_type = type(msg).__name__

    if hasattr(msg, "tool_calls") and msg.tool_calls:
        for tc in msg.tool_calls:
            tool_name = tc.get("name", "?")
            args = tc.get("args", {})
            if tool_name == "task":
                subagent = args.get("subagent_type", args.get("name", "?"))
                desc = args.get("description", args.get("task", ""))
                preview = desc[:150] + "..." if len(desc) > 150 else desc
                log.info("Delegating to '%s': %s", subagent, preview,
                         extra={"tag": "AGENT"})
            elif tool_name == "write_todos":
                log.info("Planning: write_todos", extra={"tag": "AGENT"})
            elif tool_name in ("read_file", "write_file", "edit_file"):
                path = args.get("file_path", "?")
                log.info("%s %s", tool_name, path, extra={"tag": "AGENT"})
            else:
                arg_preview = str(args)
                if len(arg_preview) > 120:
                    arg_preview = arg_preview[:120] + "..."
                log.info("Tool call: %s(%s)", tool_name, arg_preview,
                         extra={"tag": "AGENT"})

    if hasattr(msg, "content") and msg.content:
        text = str(msg.content)
        if msg_type == "ToolMessage":
            preview = text[:200] + "..." if len(text) > 200 else text
            log.debug("[%s] tool result: %s", agent_name, preview,
                      extra={"tag": "TOOL"})
        else:
            preview = text[:300] + "..." if len(text) > 300 else text
            log.info("[%s] %s", agent_name, preview, extra={"tag": "AGENT"})
