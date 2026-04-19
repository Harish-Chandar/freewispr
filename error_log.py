from __future__ import annotations

from datetime import datetime
from pathlib import Path
import traceback


LOG_FILE = Path.home() / ".freewispr" / "logs" / "error.log"


def log_error(stage: str, error: Exception | None = None, details: str | None = None):
    """Append an error entry to ~/.freewispr/logs/error.log."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"[{ts}] stage={stage}"]
        if details:
            lines.append(f"details={details}")
        if error is not None:
            lines.append(f"error={type(error).__name__}: {error}")
            lines.append("traceback:")
            lines.append("".join(traceback.format_exception(type(error), error, error.__traceback__)).rstrip())
        lines.append("")

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass