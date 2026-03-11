"""
OpenAI Service
Generates AI-powered weather summaries and sailing advisories
using club safety rules and NWS forecast data as context.
Budget-aware: checks limits before every API call.
"""

import json
import logging
import os
from typing import Optional
from datetime import datetime, timezone

from openai import OpenAI

from app.config import settings
from app.services.budget_tracker import budget_tracker

logger = logging.getLogger("sailcast.openai")


class OpenAIService:
    """Handles OpenAI API interactions for sailing advisory generation."""

    def __init__(self):
        self._client: Optional[OpenAI] = None
        self._summary_cache: Optional[dict] = None
        self._club_rules: str = ""
        self._load_club_rules()

    def _load_club_rules(self):
        """Load club sailing rules from the data directory."""
        rules_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "club_rules.md"
        )
        try:
            with open(rules_path, "r") as f:
                self._club_rules = f.read()
            logger.info("Club rules loaded successfully")
        except FileNotFoundError:
            logger.warning(f"Club rules file not found at {rules_path}")
            self._club_rules = "No club rules document available."

    def _get_client(self) -> OpenAI:
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY is not set. Add it to your .env file."
                )
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
            "- Format your response with clear sections"
        )

    def _build_forecast_prompt(
        self, hourly_data: dict, seven_day_data: dict, alerts_data: dict
    ) -> str:
        """Build the user prompt with current forecast data."""
        return (
            "Based on the following NWS forecast data, generate:\n"
            "1. A human-readable 24-HOUR WEATHER SUMMARY (2-3 sentences)\n"
            "2. A SAILING ADVISORY with safety recommendation\n"
            "3. KEY CONCERNS if any\n\n"
            f"HOURLY FORECAST (next 24 hours):\n"
            f"{json.dumps(hourly_data.get('periods', [])[:12], indent=2)}\n\n"
            f"7-DAY OUTLOOK:\n"
            f"{json.dumps(seven_day_data.get('periods', [])[:4], indent=2)}\n\n"
            f"ACTIVE ALERTS ({alerts_data.get('count', 0)}):\n"
            f"{json.dumps(alerts_data.get('alerts', []), indent=2)}\n\n"
            "Provide your response in the following JSON format:\n"
            "{\n"
            '  "summary": "24-hour weather summary text",\n'
            '  "advisory": "Sailing advisory text with safety level",\n'
            '  "safetyLevel": "SAFE | CAUTION | UNSAFE",\n'
            '  "keyConcerns": ["concern1", "concern2"],\n'
            '  "generatedAt": "ISO timestamp"\n'
            "}"
        )

    async def generate_summary(
        self, hourly_data: dict, seven_day_data: dict, alerts_data: dict
    ) -> dict:
        """Generate an AI-powered weather summary and sailing advisory."""

        # --- Budget gate: check before calling OpenAI ---
        allowed, reason = budget_tracker.can_make_request()
        if not allowed:
            logger.warning(f"AI summary SKIPPED: {reason}")
            # Return cached summary if available, or a budget-exceeded notice
            if self._summary_cache:
                self._summary_cache["budgetNotice"] = reason
                return self._summary_cache
            return {
                "summary": "AI summary unavailable — budget limit reached.",
                "advisory": "Please check raw forecast data for current conditions.",
                "safetyLevel": "CAUTION",
                "keyConcerns": [reason],
                "generatedAt": datetime.now(timezone.utc).isoformat(),
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
                        "content": self._build_forecast_prompt(
                            hourly_data, seven_day_data, alerts_data
                        ),
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
            parsed["generatedAt"] = datetime.now(timezone.utc).isoformat()
            parsed["model"] = settings.OPENAI_MODEL

            self._summary_cache = parsed
            logger.info(f"AI summary generated: safety={parsed.get('safetyLevel')}")
            return parsed

        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            raise

    def get_cached_summary(self) -> Optional[dict]:
        return self._summary_cache


# Singleton instance
openai_service = OpenAIService()
