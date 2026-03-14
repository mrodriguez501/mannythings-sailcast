"""
Report API Route

Serves the cached report payload (built by report_builder) with
LLM advice merged at serve-time from the OpenAI cache.
"""

from fastapi import APIRouter, HTTPException

from app.services.openai_service import openai_service
from app.services.report_builder import report_builder

router = APIRouter()


def _build_advice(summary_data: dict | str | None) -> tuple[str, dict | None]:
    """Extract recommendation string and structured advice from OpenAI cache."""
    if summary_data and isinstance(summary_data, dict):
        summary = summary_data.get("summary", "") or summary_data.get("text", "")
        advisory = summary_data.get("advisory", "")
        recommendation = (
            f"{summary}\n\n{advisory}".strip() if (summary and advisory) else summary or advisory or str(summary_data)
        )
        advice = None
        if summary_data.get("safetyLevel"):
            advice = {
                "safetyLevel": summary_data.get("safetyLevel"),
                "summary": summary,
                "advisory": advisory,
                "keyConcerns": summary_data.get("keyConcerns", []),
                "sailingWindows": summary_data.get("sailingWindows"),
                "generatedAt": summary_data.get("generatedAt"),
                "model": summary_data.get("model"),
            }
        return recommendation, advice

    if isinstance(summary_data, str):
        return summary_data, None

    return "", None


@router.get("/report")
async def api_report():
    """Single report payload for the SailCast static UI."""
    report = report_builder.get_cached_report()
    if report is None:
        raise HTTPException(
            status_code=503,
            detail="Forecast data not yet available (scheduler may still be loading).",
        )

    recommendation, advice = _build_advice(openai_service.get_cached_summary())

    result = {**report, "recommendation": recommendation or "No recommendation available."}
    if advice:
        result["advice"] = advice
    return result
