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
        return {"admins": [], "users": {}, "default_daily_limit": 100_000}


def _save_config(config: dict) -> None:
    """Write updated config back to token_quota.json."""
    with open(QUOTA_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print("[QUOTA] Config saved to disk.")


def is_admin(email: str) -> bool:
    """Check if an email is in the admins list."""
    config = _load_config()
    admins = config.get("admins", [])
    return email.lower() in {a.lower() for a in admins}


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
            "date": str,
            "is_admin": bool,
        }
    """
    registered = is_registered(email)
    admin = is_admin(email)

    if not registered:
        return {
            "registered": False,
            "email": email,
            "daily_limit": 0,
            "used_today": 0,
            "remaining": 0,
            "date": _get_today(),
            "is_admin": admin,
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
        "is_admin": admin,
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


# ── Admin Functions ──────────────────────────────────────────────────


def get_all_quota_settings() -> list[dict]:
    """
    Return all registered users with their limits and today's usage.
    Used by the admin dashboard.
    """
    config = _load_config()
    users = config.get("users", {})
    admins = {a.lower() for a in config.get("admins", [])}
    result = []

    for email, info in users.items():
        used = get_usage(email)
        limit = info.get("daily_limit", config.get("default_daily_limit", 100_000))
        result.append({
            "email": email,
            "name": info.get("name", ""),
            "daily_limit": limit,
            "used_today": used,
            "remaining": max(0, limit - used),
            "is_admin": email.lower() in admins,
        })

    return result


def update_user_quota(email: str, name: str, daily_limit: int) -> dict:
    """
    Add or update a user in the quota config.

    Args:
        email: User's email (key)
        name: Display name
        daily_limit: Daily token limit

    Returns:
        Updated user entry
    """
    config = _load_config()
    users = config.setdefault("users", {})

    # Case-insensitive: find existing key or use provided email
    existing_key = None
    for key in users:
        if key.lower() == email.lower():
            existing_key = key
            break

    target_key = existing_key or email
    users[target_key] = {
        "name": name,
        "daily_limit": daily_limit,
    }

    _save_config(config)
    return {"email": target_key, "name": name, "daily_limit": daily_limit}


def remove_user_quota(email: str) -> bool:
    """
    Remove a user from the quota config.

    Args:
        email: User's email to remove

    Returns:
        True if removed, False if not found
    """
    config = _load_config()
    users = config.get("users", {})

    # Case-insensitive lookup
    key_to_remove = None
    for key in users:
        if key.lower() == email.lower():
            key_to_remove = key
            break

    if key_to_remove is None:
        return False

    del users[key_to_remove]

    # Also remove from admins if present
    admins = config.get("admins", [])
    config["admins"] = [a for a in admins if a.lower() != email.lower()]

    _save_config(config)
    return True


def set_admin_role(email: str, is_admin_role: bool) -> bool:
    """
    Update the admin status of a registered user.
    """
    config = _load_config()
    admins = config.get("admins", [])

    if is_admin_role:
        # Add if not present
        if not any(a.lower() == email.lower() for a in admins):
            admins.append(email)
    else:
        # Remove if present
        admins = [a for a in admins if a.lower() != email.lower()]

    config["admins"] = admins
    _save_config(config)
    return True
