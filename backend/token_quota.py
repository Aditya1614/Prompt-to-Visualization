"""
Token quota manager.

Tracks per-user daily token usage against limits stored in Firestore.
Users not registered in Firestore are denied access.
Usage counters reset automatically at the start of each new day.

All state is persisted in Firestore — survives container redeployments.
"""

from datetime import date

from firestore_config import (
    get_admins,
    set_admins,
    get_settings,
    get_user,
    get_all_users,
    set_user,
    delete_user,
    get_all_datamarts as _fs_get_all_datamarts,
    get_datamart,
    set_datamart,
    delete_datamart,
    consume_tokens_transactional,
)


def _get_today() -> str:
    """Get today's date as ISO string."""
    return date.today().isoformat()


# ── User Checks ──────────────────────────────────────────────────────


def is_admin(email: str) -> bool:
    """Check if an email is in the admins list."""
    admins = get_admins()
    return email.lower() in {a.lower() for a in admins}


def is_registered(email: str) -> bool:
    """Check if an email is registered in the quota config."""
    return get_user(email) is not None


def get_daily_limit(email: str) -> int:
    """Get the daily token limit for a user."""
    user = get_user(email)
    if user:
        settings = get_settings()
        return user.get("daily_limit", settings.get("default_daily_limit", 100_000))
    settings = get_settings()
    return settings.get("default_daily_limit", 100_000)


def get_usage(email: str) -> int:
    """Get today's token usage for a user. Resets if date has changed."""
    user = get_user(email)
    if not user:
        return 0
    today = _get_today()
    if user.get("usage_date") != today:
        return 0
    return user.get("used_today", 0)


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
    Deduct tokens from a user's daily quota using a Firestore transaction.

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

    consume_tokens_transactional(email, amount)
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
    users = get_all_users()
    admins = {a.lower() for a in get_admins()}
    settings = get_settings()
    result = []

    for email, info in users.items():
        used = get_usage(email)
        limit = info.get("daily_limit", settings.get("default_daily_limit", 100_000))
        result.append({
            "email": email,
            "name": info.get("name", ""),
            "daily_limit": limit,
            "used_today": used,
            "remaining": max(0, limit - used),
            "is_admin": email.lower() in admins,
            "department": info.get("department", "Unassigned")
        })

    return result


def update_user_quota(email: str, name: str, daily_limit: int, department: str = "") -> dict:
    """
    Add or update a user in the quota config.

    Args:
        email: User's email (key)
        name: Display name
        daily_limit: Daily token limit
        department: User's department name

    Returns:
        Updated user entry
    """
    existing = get_user(email)

    if existing:
        # Merge update so we do not overwrite usage data
        existing["name"] = name
        existing["daily_limit"] = daily_limit
        if department:
            existing["department"] = department
        set_user(email, existing)
    else:
        # Create new entry
        set_user(email, {
            "name": name,
            "email": email.lower(),
            "daily_limit": daily_limit,
            "department": department or "Unassigned",
            "used_today": 0,
            "usage_date": _get_today()
        })

    return {"email": email, "name": name, "daily_limit": daily_limit, "department": department}


def remove_user_quota(email: str) -> bool:
    """
    Remove a user from the quota config.

    Args:
        email: User's email to remove

    Returns:
        True if removed, False if not found
    """
    removed = delete_user(email)

    if removed:
        # Also remove from admins if present
        admins = get_admins()
        new_admins = [a for a in admins if a.lower() != email.lower()]
        if len(new_admins) != len(admins):
            set_admins(new_admins)

    return removed


def set_admin_role(email: str, is_admin_role: bool) -> bool:
    """Update the admin status of a registered user."""
    admins = get_admins()

    if is_admin_role:
        # Add if not present
        if not any(a.lower() == email.lower() for a in admins):
            admins.append(email)
    else:
        # Remove if present
        admins = [a for a in admins if a.lower() != email.lower()]

    set_admins(admins)
    return True


# ── Datamart Access Control ──────────────────────────────────────────


def get_all_datamarts() -> dict:
    """Return all datamarts and their access list."""
    return _fs_get_all_datamarts()


def sync_datamarts(available_tables: list[dict]) -> dict:
    """
    Sync available tables from BQ to config.
    Reconciles Firestore with the list of tables found in BQ:
    - If a table exists in BQ but not in Firestore: Add it (0 access).
    - If a table exists in both: Skip it (preserves existing permissions).
    - If a table exists in Firestore but not in BQ: Delete it.
    
    available_tables: [{"dataset": "...", "table": "..."}]
    """
    existing_in_fs = _fs_get_all_datamarts()  # { "dataset.table": [users] }
    
    # Identify "live" keys from BigQuery
    live_keys = set()
    for t in available_tables:
        dataset = t.get("dataset")
        table = t.get("table")
        if dataset and table:
            live_keys.add(f"{dataset}.{table}")

    # 1. Identify and DELETE stale entries from Firestore
    stale_keys = set(existing_in_fs.keys()) - live_keys
    for key in stale_keys:
        print(f"[SYNC] Deleting stale datamart from Firestore: {key}")
        delete_datamart(key)

    # 2. Identify and ADD new entries to Firestore
    new_keys = live_keys - set(existing_in_fs.keys())
    for key in new_keys:
        print(f"[SYNC] Adding new datamart to Firestore: {key}")
        set_datamart(key, [])  # Default: empty (admins only)

    # Return the clean, updated state from Firestore
    return _fs_get_all_datamarts()


def update_datamart_access(dataset: str, table: str, emails: list[str]) -> dict:
    """Update user access list for a specific datamart."""
    key = f"{dataset}.{table}"
    # Deduplicate and lowercase
    deduped = list({e.lower() for e in emails})
    set_datamart(key, deduped)
    return _fs_get_all_datamarts()


def has_datamart_access(email: str, dataset: str, table: str) -> bool:
    """Check if a user has access to a specific datamart."""
    # Admins always have access
    if is_admin(email):
        return True

    key = f"{dataset}.{table}"
    allowed_users = get_datamart(key)

    if allowed_users is None:
        return False

    return email.lower() in {u.lower() for u in allowed_users}
