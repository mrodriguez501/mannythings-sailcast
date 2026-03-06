"""
LLM service: weather + alerts + tides + club guidance (RAG) → sailing recommendation.
Includes boat type (Scot vs Cruiser), brief weather summary, and safe window.
Rate-limited to stay under ~$5/month in token usage.
"""
import os
from datetime import datetime, timezone
import httpx

# Read at request time so env is definitely loaded (e.g. after load_dotenv in main)
def _get_api_key() -> str:
    return (os.environ.get("OPENAI_API_KEY") or "").strip()


def _get_model() -> str:
    return (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()

# Allow more RAG context (core rules + excerpts)
MAX_GUIDANCE_CHARS = 5000

# Rate limit: max LLM calls per day to keep under ~$5/month (gpt-5-nano / mini pricing)
MAX_LLM_CALLS_PER_DAY = 50
_calls_today: int = 0
_date_today: str = ""


def _check_rate_limit() -> bool:
    """Return True if we can make a call; False if over daily limit."""
    global _calls_today, _date_today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if today != _date_today:
        _date_today = today
        _calls_today = 0
    if _calls_today >= MAX_LLM_CALLS_PER_DAY:
        return False
    _calls_today += 1
    return True


async def generate_report(
    *,
    forecast_3day: list[dict],
    hourly: list[dict],
    alerts: list[dict],
    tides: list[dict],
    guidance: str,
    boat_type: str = "both",
) -> str:
    """
    Call LLM with forecast, alerts, tides, RAG guidance. Optionally scope to boat type (scot | cruiser | both).
    Returns fallback if no key, rate limited, or API error.
    """
    api_key = _get_api_key()
    if not api_key or api_key.lower() == "your-key-here":
        return _fallback_recommendation(forecast_3day, hourly, alerts)

    if not _check_rate_limit():
        return _fallback_recommendation(
            forecast_3day, hourly, alerts, note="Daily recommendation limit reached; try again tomorrow."
        )

    period_lines = "\n".join(
        f"- {p.get('name', '')}: {p.get('shortForecast', '')} "
        f"Temp {p.get('temp')}°F, Wind {p.get('windSpeed')}"
        for p in forecast_3day[:6]
    )
    hourly_lines = "\n".join(
        f"- {p.get('startTime', '')}: Wind {p.get('windSpeed')} Gusts {p.get('windGust')} — {p.get('shortForecast', '')}"
        for p in hourly[:24]
    )
    alerts_text = "None active."
    if alerts:
        alerts_text = "\n".join(
            f"- {a.get('event')} ({a.get('severity')}): {a.get('headline', '')}"
            for a in alerts
        )
    tides_preview = ", ".join(
        f"{t.get('type')} {t.get('v')} ft at {t.get('t')}" for t in tides[:6]
    ) if tides else "No tide data"

    guidance_trimmed = guidance[:MAX_GUIDANCE_CHARS] if guidance else ""

    boat_instruction = (
        "Address both boat types: Flying Scot (stricter wind/weather limits per SIF) and Cruiser (more tolerant). "
        "Say which guidance applies to Scot vs Cruiser when it differs."
        if boat_type == "both"
        else (
            "Address Cruiser skippers only (more tolerant limits)."
            if boat_type == "cruiser"
            else "Address Flying Scot skippers only (stricter wind/weather limits per SIF)."
        )
    )

    prompt = f"""You are a sailing club forecaster for SCOW. Using the weather and club rules below, write a concise recommendation that includes:

1) Brief weather explanation for the period (1–2 sentences).
2) A recommended safe window (e.g. "9 AM–2 PM" or "avoid after 3 PM") based on the hourly wind and conditions.
3) Boat-specific guidance where relevant. {boat_instruction}
4) If there are active alerts, mention them first. Reference club rules (wind limits, PFD, reefing) when conditions warrant. Mention tides if they affect docking or timing.

Use the hourly list to pick a safe window; avoid hours with high wind/gusts or poor visibility. Output only the recommendation (no preamble, no "Recommendation:" label). Keep to 4–6 sentences.

Club rules and relevant excerpts:
{guidance_trimmed}

3-day forecast:
{period_lines}

Hourly (use for safe window):
{hourly_lines}

Active alerts:
{alerts_text}

Tides (next 2 days): {tides_preview}"""

    model = _get_model()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": 400,
            },
        )
        if resp.status_code != 200:
            err_msg = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
            return _fallback_recommendation(
                forecast_3day, hourly, alerts,
                note=f"Recommendation unavailable (API error: {err_msg}). "
            )
        data = resp.json()
        choice = data.get("choices", [{}])[0]
        content = (choice.get("message", {}).get("content") or "").strip()
        if not content:
            return _fallback_recommendation(
                forecast_3day, hourly, alerts,
                note="Recommendation unavailable (model returned no content). ",
            )
        return content


def _fallback_recommendation(
    forecast_3day: list[dict],
    hourly: list[dict],
    alerts: list[dict],
    note: str | None = None,
) -> str:
    """When LLM is unavailable or rate limited."""
    parts = []
    if note:
        parts.append(f"{note} ")
    if alerts:
        parts.append(f"Active alerts: {', '.join(a.get('event', '') for a in alerts)}. ")
    if hourly:
        p = hourly[0]
        parts.append(
            f"Current: Wind {p.get('windSpeed', 'N/A')}, Gusts {p.get('windGust', 'N/A')}. "
        )
    if note and ("limit" in note.lower() or "error" in note.lower() or "unavailable" in note.lower()):
        parts.append("Check club rules and local conditions before sailing.")
    else:
        parts.append("Check club rules and local conditions before sailing. (Set OPENAI_API_KEY in .env to enable AI recommendations.)")
    return "".join(parts).strip()
