"""
Firestore configuration client.

Provides CRUD helpers for all application config previously stored
in token_quota.json. Uses Application Default Credentials (ADC) — no service
account key file is required when running on Cloud Run in the same project.

Collections:
  - prompt_to_viz_config: global settings (default_daily_limit, admins, allowed_datasets)
  - prompt_to_viz_users: per-user docs (name, email, daily_limit, department, used_today, usage_date)
  - prompt_to_viz_datamarts: per-table access lists (allowed_users)
"""

import os
from dotenv import load_dotenv
from google.cloud import firestore
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

load_dotenv()

# ──────────────────────────────────────────────
# Firestore client (singleton)
# ──────────────────────────────────────────────

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "database-replica-bigquery")

# On Cloud Run, remove GOOGLE_APPLICATION_CREDENTIALS if it points to a
# local key file — Cloud Run uses its built-in service identity (ADC) instead.
if os.getenv("K_SERVICE"):
    # K_SERVICE is set automatically on Cloud Run
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if creds_path and not os.path.isfile(creds_path):
        logger.info(f"[FIRESTORE] Clearing GOOGLE_APPLICATION_CREDENTIALS='{creds_path}' (file not found on Cloud Run, using ADC instead)")
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

_db = firestore.Client(project=PROJECT_ID)
logger.info(f"[FIRESTORE] Initialized client for project: {PROJECT_ID}")

# Collection names
CONFIG_COLLECTION = "prompt_to_viz_config"
USERS_COLLECTION = "prompt_to_viz_users"
DATAMARTS_COLLECTION = "prompt_to_viz_datamarts"

# ──────────────────────────────────────────────
# Settings helpers
# ──────────────────────────────────────────────


def get_settings() -> dict:
    """Get global settings (default_daily_limit, etc.)."""
    doc = _db.collection(CONFIG_COLLECTION).document("settings").get()
    if doc.exists:
        return doc.to_dict()
    return {"default_daily_limit": 100_000}


def update_settings(data: dict) -> None:
    """Update global settings (merge)."""
    _db.collection(CONFIG_COLLECTION).document("settings").set(data, merge=True)


# ──────────────────────────────────────────────
# Admin helpers
# ──────────────────────────────────────────────


def get_admins() -> list[str]:
    """Get list of admin emails."""
    doc = _db.collection(CONFIG_COLLECTION).document("admins").get()
    if doc.exists:
        return doc.to_dict().get("emails", [])
    return []


def set_admins(emails: list[str]) -> None:
    """Overwrite the admin list."""
    _db.collection(CONFIG_COLLECTION).document("admins").set({"emails": emails})


# ──────────────────────────────────────────────
# User helpers
# ──────────────────────────────────────────────


def get_user(email: str) -> dict | None:
    """Get a single user doc by email (case-insensitive key)."""
    doc = _db.collection(USERS_COLLECTION).document(email.lower()).get()
    if doc.exists:
        return doc.to_dict()
    return None


def get_all_users() -> dict[str, dict]:
    """Get all registered users. Returns {email: user_data}."""
    docs = _db.collection(USERS_COLLECTION).stream()
    return {doc.id: doc.to_dict() for doc in docs}


def set_user(email: str, data: dict) -> None:
    """Create or update a user doc (merge to preserve usage data)."""
    _db.collection(USERS_COLLECTION).document(email.lower()).set(data, merge=True)


def delete_user(email: str) -> bool:
    """Delete a user doc. Returns True if it existed."""
    ref = _db.collection(USERS_COLLECTION).document(email.lower())
    doc = ref.get()
    if doc.exists:
        ref.delete()
        return True
    return False


# ──────────────────────────────────────────────
# Datamart helpers
# ──────────────────────────────────────────────


def get_all_datamarts() -> dict[str, list[str]]:
    """Get all datamarts. Returns {dataset.table: [allowed_emails]}."""
    docs = _db.collection(DATAMARTS_COLLECTION).stream()
    return {doc.id: doc.to_dict().get("allowed_users", []) for doc in docs}


def get_datamart(key: str) -> list[str] | None:
    """Get allowed users for a specific datamart key (dataset.table)."""
    doc = _db.collection(DATAMARTS_COLLECTION).document(key).get()
    if doc.exists:
        return doc.to_dict().get("allowed_users", [])
    return None


def set_datamart(key: str, allowed_users: list[str]) -> None:
    """Create or update a datamart access list."""
    _db.collection(DATAMARTS_COLLECTION).document(key).set(
        {"allowed_users": allowed_users}
    )


def delete_datamart(key: str) -> bool:
    """Delete a datamart access doc. Returns True if it existed."""
    ref = _db.collection(DATAMARTS_COLLECTION).document(key)
    doc = ref.get()
    if doc.exists:
        ref.delete()
        return True
    return False


# ──────────────────────────────────────────────
# Allowed Datasets helpers
# ──────────────────────────────────────────────


def get_allowed_datasets() -> list[str]:
    """Get the list of allowed BigQuery dataset names."""
    try:
        doc = _db.collection(CONFIG_COLLECTION).document("allowed_datasets").get()
        if doc.exists:
            data = doc.to_dict()
            datasets = data.get("datasets", [])
            logger.info(f"[FIRESTORE] get_allowed_datasets: doc exists, raw data={data}, datasets={datasets}")
            return datasets
        else:
            logger.info("[FIRESTORE] get_allowed_datasets: doc does NOT exist, using fallback")
            return ["pis", "igr", "kingpack"]
    except Exception as e:
        logger.info(f"[FIRESTORE] get_allowed_datasets ERROR: {e}")
        # Fallback so the app doesn't crash
        return ["pis", "igr", "kingpack"]


def set_allowed_datasets(datasets: list[str]) -> None:
    """Set the list of allowed BigQuery dataset names."""
    _db.collection(CONFIG_COLLECTION).document("allowed_datasets").set(
        {"datasets": datasets}
    )


# ──────────────────────────────────────────────
# Transactional token consumption
# ──────────────────────────────────────────────


def consume_tokens_transactional(email: str, amount: int) -> dict:
    """
    Atomically consume tokens for a user using a Firestore transaction.

    Returns the updated user data dict.
    Raises ValueError if user not found or quota exceeded.
    """
    from datetime import date

    ref = _db.collection(USERS_COLLECTION).document(email.lower())
    transaction = _db.transaction()

    @firestore.transactional
    def _consume(txn, doc_ref):
        doc = doc_ref.get(transaction=txn)
        if not doc.exists:
            raise ValueError(f"User {email} is not registered for token quota.")

        data = doc.to_dict()
        today = date.today().isoformat()

        # Reset if new day
        if data.get("usage_date") != today:
            data["usage_date"] = today
            data["used_today"] = 0

        settings = get_settings()
        limit = data.get("daily_limit", settings.get("default_daily_limit", 100_000))
        current_used = data.get("used_today", 0)

        if current_used >= limit:
            raise ValueError(
                f"Daily token quota exceeded. Used: {current_used:,} / Limit: {limit:,}. "
                f"Quota resets tomorrow."
            )

        data["used_today"] = current_used + amount
        txn.set(doc_ref, data)
        return data

    return _consume(transaction, ref)
