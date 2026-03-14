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
            "You are a sailing safety advisor for a sailing club on the Potomac River "
            "near KDCA (Reagan National Airport). Your role is to provide clear, "
            "actionable weather summaries and sailing advisories based on official NWS "
            "forecast data and the club's safety rules.\n\n"
            "CLUB SAFETY RULES:\n"
            f"{self._club_rules}\n\n"
            "GUIDELINES:\n"
            "- Be concise but thorough\n"
            "- Always err on the side of caution for safety\n"
            "- Reference specific wind speeds and gust thresholds from the rules\n"
            "- Clearly state if conditions are SAFE, CAUTION, or UNSAFE for sailing\n"
            "- Mention any active weather alerts prominently\n"
            "- If the NWS Marine Forecast contains a Small Craft Advisory, conditions are UNSAFE — "
            "the club does not allow boats out during a Small Craft Advisory\n"
            "- Format your response with clear sections"
        )

    def _build_forecast_prompt(self, weather_brief: str) -> str:
        """Build the user prompt from the pre-built weather brief."""
        return (
            "Based on the following Weather Brief (daytime periods only, 8 AM – 8 PM), generate:\n"
            "1. A human-readable DAYTIME WEATHER SUMMARY (2-3 sentences)\n"
            "2. A SAILING ADVISORY with safety recommendation\n"
            "3. KEY CONCERNS if any\n"
            "4. SAILING WINDOWS — list the safe hour ranges for each boat type "
            "(cruising boats and daysailers) based on the club wind thresholds\n\n"
            "WEATHER BRIEF:\n"
            f"{weather_brief}\n\n"
            "Provide your response in the following JSON format:\n"
            "{\n"
            '  "summary": "Daytime weather summary text",\n'
            '  "advisory": "Sailing advisory text with safety level",\n'
            '  "safetyLevel": "SAFE | CAUTION | UNSAFE",\n'
            '  "keyConcerns": ["concern1", "concern2"],\n'
            '  "sailingWindows": {\n'
            '    "cruisingBoats": "e.g. 8AM–2PM (winds below 29 mph)",\n'
            '    "daysailers": "e.g. 8AM–12PM (winds below 23 mph)",\n'
            '    "reefRequired": "e.g. 12PM–3PM (winds 17–23 mph, reef + lagoon + PFDs)"\n'
            "  },\n"
            '  "generatedAt": "ISO timestamp"\n'
            "}"
        )

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
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {
                        "role": "user",
                        "content": self._build_forecast_prompt(weather_brief),
                    },
                ],
                temperature=0.3,
                max_completion_tokens=1000,
                response_format={"type": "json_object"},
            )

            # --- Record actual token usage ---
            usage = response.usage
            if usage:
                budget_tracker.record_usage(
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                )

            content = response.choices[0].message.content
            parsed = json.loads(content)
            parsed["generatedAt"] = datetime.now(UTC).isoformat()
            parsed["model"] = settings.OPENAI_MODEL

            self._summary_cache = parsed
            logger.info(f"AI summary generated: safety={parsed.get('safetyLevel')}")
            return parsed

        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            raise

    def get_cached_summary(self) -> dict | None:
        return self._summary_cache


# Singleton instance
openai_service = OpenAIService()
