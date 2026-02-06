"""
SailCast Configuration
Loads environment variables and provides app-wide settings.
"""

import os
from dotenv import load_dotenv

# Load .env file from the server directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


class Settings:
    """Application settings loaded from environment variables."""

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-nano")

    # NWS API
    NWS_OFFICE: str = os.getenv("NWS_OFFICE", "LWX")
    NWS_GRIDPOINT_X: int = int(os.getenv("NWS_GRIDPOINT_X", "97"))
    NWS_GRIDPOINT_Y: int = int(os.getenv("NWS_GRIDPOINT_Y", "74"))
    NWS_USER_AGENT: str = os.getenv(
        "NWS_USER_AGENT", "SailCast/1.0 (contact@mannythings.us)"
    )
    NWS_BASE_URL: str = "https://api.weather.gov"

    # Server
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

    # CORS
    CLIENT_URL: str = os.getenv("CLIENT_URL", "http://localhost:5173")

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def nws_forecast_url(self) -> str:
        """NWS hourly forecast endpoint for configured gridpoint."""
        return (
            f"{self.NWS_BASE_URL}/gridpoints/"
            f"{self.NWS_OFFICE}/{self.NWS_GRIDPOINT_X},{self.NWS_GRIDPOINT_Y}"
            f"/forecast/hourly"
        )

    @property
    def nws_forecast_7day_url(self) -> str:
        """NWS 7-day forecast endpoint for configured gridpoint."""
        return (
            f"{self.NWS_BASE_URL}/gridpoints/"
            f"{self.NWS_OFFICE}/{self.NWS_GRIDPOINT_X},{self.NWS_GRIDPOINT_Y}"
            f"/forecast"
        )

    @property
    def nws_alerts_url(self) -> str:
        """NWS active alerts for the DC area (Potomac River / KDCA)."""
        return f"{self.NWS_BASE_URL}/alerts/active?point=38.8512,-77.0402"


settings = Settings()
