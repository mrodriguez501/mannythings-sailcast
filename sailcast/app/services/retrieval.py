"""
Minimal RAG-style retrieval: load club rules markdown and return relevant guidance
based on wind speed, gusts, and conditions.
"""
from pathlib import Path

# Path to club rules relative to project root (sailcast/)
RAG_DIR = Path(__file__).resolve().parent.parent.parent / "rag"
CLUB_RULES_PATH = RAG_DIR / "club_rules.md"

_cached_rules_text: str | None = None


def _load_rules() -> str:
    global _cached_rules_text
    if _cached_rules_text is not None:
        return _cached_rules_text
    if not CLUB_RULES_PATH.exists():
        _cached_rules_text = "# Club rules\nNo club rules file found. Use safe sailing practices."
        return _cached_rules_text
    _cached_rules_text = CLUB_RULES_PATH.read_text(encoding="utf-8")
    return _cached_rules_text


def get_club_guidance(forecast_data: list[dict]) -> str:
    """
    Return relevant club guidance based on forecast (wind, gusts, conditions).
    Uses simple heuristics: if any period has high wind/gusts, include full rules.
    """
    rules = _load_rules()
    if not forecast_data:
        return rules

    # Heuristic: if any hour has strong wind/gusts, return full rules for context
    for p in forecast_data[:12]:  # next 12 hours
        ws = p.get("windSpeed") or ""
        gust = p.get("windGust") or ""
        # Simple check: "20 mph" or "25 mph" etc.
        try:
            w = "".join(c for c in str(ws) if c.isdigit() or c == ".")
            g = "".join(c for c in str(gust) if c.isdigit() or c == ".")
            if (w and float(w) >= 18) or (g and float(g) >= 22):
                return rules
        except (ValueError, TypeError):
            pass
    return rules
