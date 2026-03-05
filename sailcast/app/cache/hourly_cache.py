"""
In-memory cache keyed by UTC hour so we only call the LLM once per hour.

Switch: cache can be disabled manually or automatically in dev/local:
  - Set DISABLE_REPORT_CACHE=1 (or true/yes) to disable.
  - Set ENV=dev (or development/local) to disable in local/dev.
  - Call set_cache_enabled(False) in code to disable; set_cache_enabled(None) to use env again.
"""
import os
from datetime import datetime, timezone

_cached_key: str | None = None  # "YYYY-MM-DDTHH" for current UTC hour
_cached_payload: dict | None = None
# Manual override: None = use env, True/False = force on/off
_cache_enabled_override: bool | None = None


def _env_cache_enabled() -> bool:
    """True if cache should be on based on env (off for dev/local or when explicitly disabled)."""
    if os.environ.get("DISABLE_REPORT_CACHE", "").lower() in ("1", "true", "yes"):
        return False
    env = os.environ.get("ENV", "").lower()
    if env in ("dev", "development", "local"):
        return False
    return True


def is_cache_enabled() -> bool:
    """Whether the cache is currently enabled (manual override or env)."""
    if _cache_enabled_override is not None:
        return _cache_enabled_override
    return _env_cache_enabled()


def set_cache_enabled(enabled: bool | None) -> None:
    """
    Manually enable or disable the cache.
    - True: cache on regardless of env
    - False: cache off regardless of env
    - None: use env (DISABLE_REPORT_CACHE, ENV) again
    """
    global _cache_enabled_override
    _cache_enabled_override = enabled


def _current_utc_hour_key() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H")


def get_cached_report() -> dict | None:
    """Return cached report if it was stored for the current UTC hour (and cache is enabled)."""
    if not is_cache_enabled():
        return None
    global _cached_key, _cached_payload
    if _cached_payload is None or _cached_key is None:
        return None
    if _cached_key != _current_utc_hour_key():
        _cached_key = None
        _cached_payload = None
        return None
    return _cached_payload


def set_cached_report(payload: dict) -> None:
    """Store report for the current UTC hour (no-op if cache is disabled)."""
    if not is_cache_enabled():
        return
    global _cached_key, _cached_payload
    _cached_key = _current_utc_hour_key()
    _cached_payload = payload
