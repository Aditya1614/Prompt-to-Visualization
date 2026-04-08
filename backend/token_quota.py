"""
Token quota manager.

Tracks per-user daily token usage against limits defined in token_quota.json.
Users not registered in the JSON file are denied access.
Usage counters reset automatically at the start of each new day.
"""

import json
import os
from datetime import date
from pathlib import Path
from threading import Lock

# Path to the quota config file (same directory as this module)
QUOTA_FILE = Path(__file__).parent / "token_quota.json"

# In-memory usage tracker: { "email": { "date": "2026-04-08", "used": 12345 } }
_usage: dict[str, dict] = {}
_lock = Lock()


def _load_config() -> dict:
    """Load the quota config from JSON file (re-read each time for hot editing)."""
    try:
        with open(QUOTA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[QUOTA] Failed to load config: {e}")
        return {"users": {}, "default_daily_limit": 100_000}


def is_registered(email: str) -> bool:
    """Check if an email is registered in the quota config."""
    config = _load_config()
    return email.lower() in {k.lower() for k in config.get("users", {}).keys()}


def get_daily_limit(email: str) -> int:
    """Get the daily token limit for a user."""
    config = _load_config()
    users = config.get("users", {})
    # Case-insensitive lookup
    for key, val in users.items():
        if key.lower() == email.lower():
            return val.get("daily_limit", config.get("default_daily_limit", 100_000))
    return config.get("default_daily_limit", 100_000)


def _get_today() -> str:
    """Get today's date as ISO string."""
    return date.today().isoformat()


def get_usage(email: str) -> int:
    """Get today's token usage for a user. Resets if date has changed."""
    with _lock:
        key = email.lower()
        today = _get_today()
        entry = _usage.get(key, {})
        if entry.get("date") != today:
            return 0
        return entry.get("used", 0)


def get_quota_info(email: str) -> dict:
    """
    Get full quota information for a user.

    Returns:
        {
            "registered": bool,
            "email": str,
            "daily_limit": int,
            "used_today": int,
            "remaining": int,
            "date": str
        }
    """
    registered = is_registered(email)
    if not registered:
        return {
            "registered": False,
            "email": email,
            "daily_limit": 0,
            "used_today": 0,
            "remaining": 0,
            "date": _get_today(),
        }

    limit = get_daily_limit(email)
    used = get_usage(email)
    remaining = max(0, limit - used)

    return {
        "registered": registered,
        "email": email,
        "daily_limit": limit,
        "used_today": used,
        "remaining": remaining,
        "date": _get_today(),
    }


def consume_tokens(email: str, amount: int) -> dict:
    """
    Deduct tokens from a user's daily quota.

    Args:
        email: User's email
        amount: Number of tokens to consume

    Returns:
        Updated quota info dict

    Raises:
        ValueError: If user is not registered or has exceeded quota
    """
    if not is_registered(email):
        raise ValueError(f"User {email} is not registered for token quota.")

    with _lock:
        key = email.lower()
        today = _get_today()
        entry = _usage.get(key, {})

        # Reset if new day
        if entry.get("date") != today:
            entry = {"date": today, "used": 0}

        limit = get_daily_limit(email)
        current_used = entry.get("used", 0)

        if current_used >= limit:
            raise ValueError(
                f"Daily token quota exceeded. Used: {current_used:,} / Limit: {limit:,}. "
                f"Quota resets tomorrow."
            )

        # Deduct tokens (allow going slightly over limit on the last request)
        entry["used"] = current_used + amount
        _usage[key] = entry

    return get_quota_info(email)


def check_quota(email: str) -> bool:
    """Quick check if user has tokens remaining today."""
    if not is_registered(email):
        return False
    info = get_quota_info(email)
    return info["remaining"] > 0
