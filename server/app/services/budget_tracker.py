"""
Budget Tracker Service
Tracks OpenAI API token usage and enforces spending limits.
Prevents runaway costs during development and production.

Pricing (gpt-5-nano as of Feb 2026):
  - Input:  $0.050 per 1M tokens
  - Output: $0.400 per 1M tokens
  - Cached: $0.005 per 1M tokens
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger("sailcast.budget")

# Pricing per token (not per million)
PRICING = {
    "gpt-5-nano": {
        "input": 0.050 / 1_000_000,   # $0.00000005 per token
        "output": 0.400 / 1_000_000,  # $0.0000004 per token
        "cached": 0.005 / 1_000_000,  # $0.000000005 per token
    },
    "gpt-4o-mini": {
        "input": 0.150 / 1_000_000,
        "output": 0.600 / 1_000_000,
        "cached": 0.075 / 1_000_000,
    },
    "gpt-4o": {
        "input": 2.50 / 1_000_000,
        "output": 10.00 / 1_000_000,
        "cached": 1.25 / 1_000_000,
    },
}

# Fallback pricing if model not in table (conservative estimate)
DEFAULT_PRICING = {
    "input": 0.50 / 1_000_000,
    "output": 2.00 / 1_000_000,
    "cached": 0.25 / 1_000_000,
}


class BudgetTracker:
    """
    Tracks token usage and estimated cost.
    Enforces monthly and daily budget limits.
    Persists usage data to a JSON file so it survives restarts.
    """

    def __init__(self):
        self._monthly_budget: float = float(
            os.getenv("OPENAI_MONTHLY_BUDGET", "5.00")
        )
        self._daily_budget: float = float(
            os.getenv("OPENAI_DAILY_BUDGET", "0.50")
        )
        self._max_requests_per_hour: int = int(
            os.getenv("OPENAI_MAX_REQUESTS_PER_HOUR", "5")
        )

        self._usage_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "usage.json"
        )
        self._usage = self._load_usage()

    def _empty_usage(self) -> dict:
        """Return a fresh usage tracking structure."""
        now = datetime.now(timezone.utc)
        return {
            "month": now.strftime("%Y-%m"),
            "today": now.strftime("%Y-%m-%d"),
            "monthly_cost": 0.0,
            "daily_cost": 0.0,
            "monthly_input_tokens": 0,
            "monthly_output_tokens": 0,
            "monthly_requests": 0,
            "daily_requests": 0,
            "hourly_requests": 0,
            "current_hour": now.strftime("%Y-%m-%d %H"),
            "last_request": None,
        }

    def _load_usage(self) -> dict:
        """Load usage data from disk, or start fresh."""
        try:
            with open(self._usage_file, "r") as f:
                data = json.load(f)
                # Reset counters if month or day rolled over
                data = self._check_rollovers(data)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return self._empty_usage()

    def _save_usage(self):
        """Persist usage data to disk."""
        try:
            os.makedirs(os.path.dirname(self._usage_file), exist_ok=True)
            with open(self._usage_file, "w") as f:
                json.dump(self._usage, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save usage data: {e}")

    def _check_rollovers(self, data: dict) -> dict:
        """Reset counters if the month, day, or hour has changed."""
        now = datetime.now(timezone.utc)
        current_month = now.strftime("%Y-%m")
        current_day = now.strftime("%Y-%m-%d")
        current_hour = now.strftime("%Y-%m-%d %H")

        if data.get("month") != current_month:
            logger.info(f"New month detected ({current_month}). Resetting monthly usage.")
            data = self._empty_usage()

        if data.get("today") != current_day:
            logger.info(f"New day detected ({current_day}). Resetting daily usage.")
            data["today"] = current_day
            data["daily_cost"] = 0.0
            data["daily_requests"] = 0

        if data.get("current_hour") != current_hour:
            data["current_hour"] = current_hour
            data["hourly_requests"] = 0

        return data

    def _get_pricing(self) -> dict:
        """Get per-token pricing for the configured model."""
        model = settings.OPENAI_MODEL
        return PRICING.get(model, DEFAULT_PRICING)

    def can_make_request(self) -> tuple[bool, str]:
        """
        Check if a request is allowed within budget and rate limits.
        Returns (allowed: bool, reason: str).
        """
        self._usage = self._check_rollovers(self._usage)

        # Check monthly budget
        if self._usage["monthly_cost"] >= self._monthly_budget:
            msg = (
                f"Monthly budget exhausted: ${self._usage['monthly_cost']:.4f} "
                f"/ ${self._monthly_budget:.2f}"
            )
            logger.warning(msg)
            return False, msg

        # Check daily budget
        if self._usage["daily_cost"] >= self._daily_budget:
            msg = (
                f"Daily budget exhausted: ${self._usage['daily_cost']:.4f} "
                f"/ ${self._daily_budget:.2f}"
            )
            logger.warning(msg)
            return False, msg

        # Check hourly rate limit
        if self._usage["hourly_requests"] >= self._max_requests_per_hour:
            msg = (
                f"Hourly rate limit reached: {self._usage['hourly_requests']} "
                f"/ {self._max_requests_per_hour} requests"
            )
            logger.warning(msg)
            return False, msg

        return True, "OK"

    def record_usage(self, input_tokens: int, output_tokens: int):
        """Record token usage from an OpenAI API call."""
        self._usage = self._check_rollovers(self._usage)
        pricing = self._get_pricing()

        input_cost = input_tokens * pricing["input"]
        output_cost = output_tokens * pricing["output"]
        total_cost = input_cost + output_cost

        self._usage["monthly_cost"] += total_cost
        self._usage["daily_cost"] += total_cost
        self._usage["monthly_input_tokens"] += input_tokens
        self._usage["monthly_output_tokens"] += output_tokens
        self._usage["monthly_requests"] += 1
        self._usage["daily_requests"] += 1
        self._usage["hourly_requests"] += 1
        self._usage["last_request"] = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"API call: {input_tokens} in + {output_tokens} out = "
            f"${total_cost:.6f} | "
            f"Daily: ${self._usage['daily_cost']:.4f}/${self._daily_budget:.2f} | "
            f"Monthly: ${self._usage['monthly_cost']:.4f}/${self._monthly_budget:.2f}"
        )

        self._save_usage()

    def get_status(self) -> dict:
        """Return current budget and usage status."""
        self._usage = self._check_rollovers(self._usage)
        pricing = self._get_pricing()
        model = settings.OPENAI_MODEL

        return {
            "model": model,
            "limits": {
                "monthly_budget": self._monthly_budget,
                "daily_budget": self._daily_budget,
                "max_requests_per_hour": self._max_requests_per_hour,
            },
            "usage": {
                "monthly_cost": round(self._usage["monthly_cost"], 6),
                "daily_cost": round(self._usage["daily_cost"], 6),
                "monthly_input_tokens": self._usage["monthly_input_tokens"],
                "monthly_output_tokens": self._usage["monthly_output_tokens"],
                "monthly_requests": self._usage["monthly_requests"],
                "daily_requests": self._usage["daily_requests"],
                "hourly_requests": self._usage["hourly_requests"],
            },
            "remaining": {
                "monthly_budget": round(
                    self._monthly_budget - self._usage["monthly_cost"], 6
                ),
                "daily_budget": round(
                    self._daily_budget - self._usage["daily_cost"], 6
                ),
            },
            "pricing_per_1m_tokens": {
                "input": pricing["input"] * 1_000_000,
                "output": pricing["output"] * 1_000_000,
            },
            "last_request": self._usage.get("last_request"),
        }


# Singleton instance
budget_tracker = BudgetTracker()
