"""
Manual script to grant access to all Supply Chain Management (SCM) users
for all configured data marts in Firestore.

Usage:
    python grant_scm_access.py
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend is importable and environment is loaded
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Explicitly load .env from the backend directory
load_dotenv(backend_dir / ".env")

# Fallback for local execution if credentials aren't set in env
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    json_path = backend_dir / "prompt-to-viz.json"
    if json_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(json_path)
        print(f"[AUTO_GRANT] Using local credentials: {json_path}")

if not os.getenv("GOOGLE_CLOUD_PROJECT"):
    os.environ["GOOGLE_CLOUD_PROJECT"] = "database-replica-bigquery"

from firestore_config import (
    get_all_users,
    get_all_datamarts,
    set_datamart,
)

def grant_scm_access():
    print("[AUTO_GRANT] Starting manual access synchronization...")

    # 1. Fetch all users and filter for SCM department
    all_users = get_all_users()
    scm_emails = [
        email.lower() 
        for email, data in all_users.items() 
        if data.get("department") == "IT Data Analyst"
    ]

    if not scm_emails:
        print("[AUTO_GRANT] No users found for department 'Supply Chain Management'.")
        return


    print(f"[AUTO_GRANT] Found {len(scm_emails)} SCM users: {', '.join(scm_emails)}")

    # 2. Fetch all datamarts
    datamarts = get_all_datamarts()
    if not datamarts:
        print("[AUTO_GRANT] No datamarts found in Firestore.")
        return

    print(f"[AUTO_GRANT] Synchronizing access for {len(datamarts)} datamarts...")

    # 3. Update each datamart
    updated_count = 0
    for key, allowed_users in datamarts.items():
        # Use set for easy deduplication
        current_set = {u.lower() for u in allowed_users}
        new_emails = [email for email in scm_emails if email not in current_set]

        if new_emails:
            # Append new SCM users to the list
            updated_list = allowed_users + new_emails
            set_datamart(key, updated_list)
            print(f"[AUTO_GRANT] ✓ Updated {key}: Added {len(new_emails)} users.")
            updated_count += 1
        else:
            print(f"[AUTO_GRANT] - Skipped {key}: Already has all SCM users.")

    print(f"\n[AUTO_GRANT] ✅ Done! Updated access for {updated_count} datamarts.")

if __name__ == "__main__":
    grant_scm_access()
