"""
Seed Firestore from existing token_quota.json.

Run this ONE TIME to migrate your local config to Firestore:
    python seed_firestore.py

Safe to re-run — uses Firestore set(merge=True) so it won't overwrite
runtime data that already exists.
"""

import json
import os
import sys
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from firestore_config import (
    update_settings,
    set_admins,
    set_user,
    set_datamart,
    set_allowed_datasets,
)

QUOTA_FILE = Path(__file__).parent / "token_quota.json"


def seed():
    """Read token_quota.json and write each section to Firestore."""

    if not QUOTA_FILE.exists():
        print(f"[SEED] {QUOTA_FILE} not found. Nothing to seed.")
        return

    with open(QUOTA_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    print(f"[SEED] Loaded config from {QUOTA_FILE}")

    # 1. Settings
    default_limit = config.get("default_daily_limit", 100_000)
    update_settings({"default_daily_limit": default_limit})
    print(f"[SEED] ✓ Settings: default_daily_limit = {default_limit:,}")

    # 2. Admins
    admins = config.get("admins", [])
    set_admins(admins)
    print(f"[SEED] ✓ Admins: {admins}")

    # 3. Users
    users = config.get("users", {})
    for email, data in users.items():
        user_data = {
            "name": data.get("name", ""),
            "email": email.lower(),
            "daily_limit": data.get("daily_limit", default_limit),
            "department": data.get("department", "Unassigned"),
            "used_today": data.get("used_today", 0),
            "usage_date": data.get("usage_date", ""),
        }
        set_user(email, user_data)
        print(f"[SEED] ✓ User: {email} (limit: {user_data['daily_limit']:,})")

    # 4. Datamarts
    datamarts = config.get("datamarts", {})
    for key, allowed_users in datamarts.items():
        set_datamart(key, allowed_users)
        print(f"[SEED] ✓ Datamart: {key} ({len(allowed_users)} users)")

    # 5. Allowed datasets (populate from hardcoded defaults)
    default_datasets = ["pis", "igr", "kingpack"]
    set_allowed_datasets(default_datasets)
    print(f"[SEED] ✓ Allowed datasets: {default_datasets}")

    print(f"\n[SEED] ✅ Done! Seeded {1 + 1 + len(users) + len(datamarts) + 1} documents to Firestore.")


if __name__ == "__main__":
    seed()
