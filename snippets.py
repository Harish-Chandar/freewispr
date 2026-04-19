"""Snippet library for trigger words that expand into longer phrases."""
import json
from pathlib import Path
from error_log import log_error

_FILE = Path.home() / ".freewispr" / "snippets.json"
_CACHE: dict[str, str] | None = None


def _normalize(snippets: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for trigger, expansion in snippets.items():
        key = str(trigger).strip().lower()
        if not key:
            continue
        normalized[key] = str(expansion)
    return normalized


def load() -> dict[str, str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE.copy()

    data: dict[str, str] = {}
    if _FILE.exists():
        try:
            with open(_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = {str(k): str(v) for k, v in loaded.items()}
        except Exception as e:
            log_error("snippets.load", e)

    _CACHE = _normalize(data)
    return _CACHE.copy()


def save(snippets: dict[str, str]):
    global _CACHE
    normalized = _normalize(snippets)

    _FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    _CACHE = normalized


def expand(text: str) -> str:
    """Expand the text if it exactly matches a snippet trigger."""
    if _CACHE is None:
        load()

    snips = _CACHE or {}
    key = text.strip().lower()
    return snips.get(key, text)
