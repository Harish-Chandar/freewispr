"""Personal dictionary for word corrections applied after transcription."""
import json
import re
from pathlib import Path
from error_log import log_error

_FILE = Path.home() / ".freewispr" / "corrections.json"
_CACHE: dict[str, str] | None = None
_PATTERN: re.Pattern[str] | None = None
_REPLACEMENTS: dict[str, str] = {}


def _normalize(corrections: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for wrong, right in corrections.items():
        key = str(wrong).strip().lower()
        if not key:
            continue
        normalized[key] = str(right)
    return normalized


def _rebuild_matcher(corrections: dict[str, str]):
    global _PATTERN, _REPLACEMENTS

    if not corrections:
        _PATTERN = None
        _REPLACEMENTS = {}
        return

    keys = sorted(corrections.keys(), key=len, reverse=True)
    alternation = "|".join(re.escape(k) for k in keys)
    _PATTERN = re.compile(r"\b(?:" + alternation + r")\b", re.IGNORECASE)
    _REPLACEMENTS = corrections


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
            log_error("corrections.load", e)

    _CACHE = _normalize(data)
    _rebuild_matcher(_CACHE)
    return _CACHE.copy()


def save(corrections: dict[str, str]):
    global _CACHE
    normalized = _normalize(corrections)

    _FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    _CACHE = normalized
    _rebuild_matcher(_CACHE)


def apply(text: str) -> str:
    """Apply case-insensitive word corrections."""
    if not text:
        return text

    if _CACHE is None:
        load()

    if not _PATTERN:
        return text

    return _PATTERN.sub(
        lambda m: _REPLACEMENTS.get(m.group(0).lower(), m.group(0)),
        text,
    )
