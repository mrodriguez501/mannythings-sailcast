"""
RAG: load a single curated file of weather, rules, and boat-type guidance for the LLM.
Uses rag/sailing-weather-rules.txt (parsed from club_rules, SIFs, skipper agreement).
"""
from pathlib import Path

RAG_DIR = Path(__file__).resolve().parent.parent.parent / "rag"
SAILING_WEATHER_RULES_PATH = RAG_DIR / "sailing-weather-rules.txt"

_cached_guidance: str | None = None


def _load_guidance() -> str:
    """Load the curated sailing weather/rules text (cached)."""
    global _cached_guidance
    if _cached_guidance is not None:
        return _cached_guidance
    if not SAILING_WEATHER_RULES_PATH.exists():
        _cached_guidance = (
            "Wind: do not sail sustained above 20 knots; gusts above 25 consider reefing or staying in. "
            "PFD required on water. Check weather before leaving dock. When in doubt, stay ashore. Reef early in heavy air."
        )
        return _cached_guidance
    _cached_guidance = SAILING_WEATHER_RULES_PATH.read_text(encoding="utf-8")
    return _cached_guidance


def get_club_guidance() -> str:
    """Return guidance text from rag/sailing-weather-rules.txt for the LLM prompt."""
    return _load_guidance()
