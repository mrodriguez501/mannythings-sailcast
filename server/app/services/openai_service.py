"""
OpenAI Service
Generates AI-powered weather summaries and sailing advisories
using club safety rules and NWS forecast data as context.
Budget-aware: checks limits before every API call.
"""

import json
import logging
import os
from datetime import UTC, datetime

from openai import OpenAI

from app.config import settings
from app.services.budget_tracker import budget_tracker

logger = logging.getLogger("sailcast.openai")


class OpenAIService:
    """Handles OpenAI API interactions for sailing advisory generation."""

    def __init__(self):
        self._client: OpenAI | None = None
        self._summary_cache: dict | None = None
        self._club_rules: str = ""
        self._load_club_rules()

    def _load_club_rules(self):
        """Load club sailing rules from the RAG data directory."""
        rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rag", "club_rules.md")
        try:
            with open(rules_path) as f:
                self._club_rules = f.read()
            logger.info("Club rules loaded successfully")
        except FileNotFoundError:
            logger.warning(f"Club rules file not found at {rules_path}")
            self._club_rules = "No club rules document available."

    def _get_client(self) -> OpenAI:
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    def _build_system_prompt(self) -> str:
        """Build the system prompt with club rules context."""
        return (
            "You are SailCast, a conservative sailing conditions recommendation assistant.\n\n"
            "Your job is to evaluate the next 12 hours of sailing conditions using:\n"
            "1. structured weather data,\n"
            "2. retrieved club-guideline excerpts,\n"
            "3. deterministic risk flags provided by the application.\n\n"
            "Primary objective:\n"
            "Produce a brief, practical recommendation for club sailors.\n\n"
            "Decision principles:\n"
            "- Follow club guidelines over general sailing knowledge whenever a conflict exists.\n"
            "- Be conservative when conditions are ambiguous or borderline.\n"
            "- Do not invent thresholds, rules, or club policies not present in the provided context.\n"
            "- If context is insufficient, say that the recommendation is uncertain.\n"
            "- Respect hard risk flags from the application.\n"
            '- Distinguish between "good to go", "marginal/caution", and "no-go".\n'
            "- If novice and experienced guidance would differ, state that clearly.\n\n"
            "CLUB GUIDELINES:\n"
            f"{self._club_rules}"
        )

    def _build_forecast_prompt(self, weather_brief: str) -> str:
        """Build the user prompt from the pre-built weather brief."""
        return (
            "WEATHER DATA:\n"
            f"{weather_brief}\n\n"
            "Respond with JSON only. Schema:\n"
            "{\n"
            '  "safetyLevel": "GOOD_TO_GO | CAUTION | NO_GO",\n'
            '  "recommendation": "Max 3 short sentences. '
            "Sentence 1: overall recommendation. "
            "Sentence 2: main reasons based on weather and club rules. "
            'Sentence 3: optional caution or timing nuance only if useful.",\n'
            '  "keyConcerns": ["concern1", "concern2"],\n'
            '  "sailingWindows": {\n'
            '    "cruisingBoats": "safe hour range or NO_GO",\n'
            '    "daysailers": "safe hour range or NO_GO",\n'
            '    "reefRequired": "hour range requiring reef + lagoon + PFDs, or N/A"\n'
            "  }\n"
            "}\n\n"
            "Do not mention token limits, prompting, or internal reasoning.\n"
            "Do not quote large passages from the guidelines."
        )

    # Models that do NOT support the temperature parameter (reasoning models)
    _NO_TEMPERATURE_MODELS = {"o1", "o1-mini", "o1-preview", "o3-mini", "gpt-5-nano"}

    def _model_supports_temperature(self) -> bool:
        model = settings.OPENAI_MODEL.lower()
        return model not in self._NO_TEMPERATURE_MODELS

    async def generate_summary(self, weather_brief: str) -> dict:
        """Generate an AI-powered weather summary and sailing advisory.

        Args:
            weather_brief: Pre-built markdown weather brief (daytime-only,
                           written by weather_brief.write_weather_brief()).
        """

        # --- Budget gate: check before calling OpenAI ---
        allowed, reason = budget_tracker.can_make_request()
        if not allowed:
            logger.warning(f"AI summary SKIPPED: {reason}")
            if self._summary_cache:
                self._summary_cache["budgetNotice"] = reason
                return self._summary_cache
            return {
                "summary": "AI summary unavailable — budget limit reached.",
                "advisory": "Please check raw forecast data for current conditions.",
                "safetyLevel": "CAUTION",
                "keyConcerns": [reason],
                "generatedAt": datetime.now(UTC).isoformat(),
                "model": settings.OPENAI_MODEL,
                "budgetNotice": reason,
            }

        logger.info("Generating AI summary...")
        logger.info(f"Model: {settings.OPENAI_MODEL}")
        logger.debug("Weather brief length: %d chars", len(weather_brief))
        try:
            client = self._get_client()

            kwargs: dict = {
                "model": settings.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": self._build_system_prompt()},
                    {
                        "role": "user",
                        "content": self._build_forecast_prompt(weather_brief),
                    },
                ],
                "max_completion_tokens": 8000,
                "response_format": {"type": "json_object"},
            }
            if self._model_supports_temperature():
                kwargs["temperature"] = 0.3

            response = client.chat.completions.create(**kwargs)

            # --- Record actual token usage ---
            usage = response.usage
            if usage:
                budget_tracker.record_usage(
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                )
                logger.info(
                    "Token usage: prompt=%d, completion=%d, total=%d",
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                )

            choice = response.choices[0]
            content = choice.message.content
            finish_reason = choice.finish_reason

            logger.info("Finish reason: %s", finish_reason)
            if choice.message.refusal:
                logger.warning("Model refusal: %s", choice.message.refusal)

            if not content:
                logger.error("OpenAI returned empty content (finish_reason=%s)", finish_reason)
                raise ValueError(f"OpenAI returned empty content (finish_reason={finish_reason})")

            logger.info("Raw response (first 300 chars): %s", content[:300])

            if finish_reason == "length":
                logger.warning("Response truncated — max_completion_tokens may be too low")

            parsed = json.loads(content)
            parsed["generatedAt"] = datetime.now(UTC).isoformat()
            parsed["model"] = settings.OPENAI_MODEL

            self._summary_cache = parsed
            logger.info("AI summary generated: safety=%s", parsed.get("safetyLevel"))
            return parsed

        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            raise

    def get_cached_summary(self) -> dict | None:
        return self._summary_cache


# Singleton instance
openai_service = OpenAIService()
