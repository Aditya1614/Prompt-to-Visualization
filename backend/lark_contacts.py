"""
Lark Contacts API client.

Uses app-level authentication (tenant_access_token) to fetch
all users in the organization via the Contact v3 API.
"""

import os
import time
from typing import Optional

import httpx

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

LARK_CLIENT_ID = os.getenv("LARK_CLIENT_ID", "")
LARK_CLIENT_SECRET = os.getenv("LARK_CLIENT_SECRET", "")

# Lark API endpoints
TENANT_TOKEN_URL = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal/"
DEPARTMENT_USERS_URL = "https://open.larksuite.com/open-apis/contact/v3/users/find_by_department"
DEPARTMENT_CHILDREN_URL = "https://open.larksuite.com/open-apis/contact/v3/departments"

# ──────────────────────────────────────────────
# Tenant token cache
# ──────────────────────────────────────────────

_cached_token: Optional[str] = None
_token_expires_at: float = 0


async def get_tenant_access_token() -> str:
    """
    Get a tenant_access_token for app-level API calls.
    Cached for ~1.5 hours (token lasts 2 hours).
    """
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < _token_expires_at:
        return _cached_token

    payload = {
        "app_id": LARK_CLIENT_ID,
        "app_secret": LARK_CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(TENANT_TOKEN_URL, json=payload)

    data = resp.json()

    if data.get("code", -1) != 0:
        error_msg = data.get("msg", "Unknown error")
        print(f"[LARK_CONTACTS] Failed to get tenant token: {data}")
        raise Exception(f"Failed to get tenant_access_token: {error_msg}")

    _cached_token = data.get("tenant_access_token", "")
    # Cache for 90 minutes (token lasts 2 hours)
    _token_expires_at = time.time() + 5400

    print("[LARK_CONTACTS] Got new tenant_access_token")
    return _cached_token


async def _fetch_department_children(token: str, parent_id: str = "0") -> list[dict]:
    """Fetch child departments of a given parent department."""
    departments = []
    page_token = ""

    while True:
        params = {
            "parent_department_id": parent_id,
            "department_id_type": "open_department_id" if parent_id.startswith("od-") else "department_id",
            "page_size": 50,
        }
        if page_token:
            params["page_token"] = page_token

        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(DEPARTMENT_CHILDREN_URL, params=params, headers=headers)

        data = resp.json()

        if data.get("code", -1) != 0:
            error_msg = f"Lark API Error (Dept): {data.get('msg')} (Code {data.get('code')})"
            print(f"[LARK_CONTACTS] {error_msg}")
            raise Exception(error_msg)

        items = data.get("data", {}).get("items", [])
        if items is None:  # Sometimes API returns null instead of []
            items = []
            
        departments.extend(items)

        if not data.get("data", {}).get("has_more", False):
            break
        page_token = data.get("data", {}).get("page_token", "")

    return departments


async def _fetch_users_in_department(token: str, dept_id: str) -> list[dict]:
    """Fetch all users directly under a department (paginated)."""
    users = []
    page_token = ""

    while True:
        params = {
            "department_id": dept_id,
            "department_id_type": "open_department_id" if dept_id.startswith("od-") else "department_id",
            "page_size": 50,
        }
        if page_token:
            params["page_token"] = page_token

        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(DEPARTMENT_USERS_URL, params=params, headers=headers)

        data = resp.json()

        if data.get("code", -1) != 0:
            error_msg = f"Lark API Error (Users): {data.get('msg')} (Code {data.get('code')})"
            print(f"[LARK_CONTACTS] {error_msg} for dept {dept_id}")
            raise Exception(error_msg)

        items = data.get("data", {}).get("items", [])
        if items is None:
            items = []
            
        users.extend(items)

        if not data.get("data", {}).get("has_more", False):
            break
        page_token = data.get("data", {}).get("page_token", "")

    return users


async def _collect_all_department_ids(token: str, parent_id: str) -> list[str]:
    """Recursively collect all department IDs starting from root."""
    dept_ids = [parent_id]

    try:
        children = await _fetch_department_children(token, parent_id)
        for child in children:
            child_id = child.get("open_department_id", "") or child.get("department_id", "")
            if child_id:
                sub_ids = await _collect_all_department_ids(token, child_id)
                dept_ids.extend(sub_ids)
    except Exception as e:
        print(f"[LARK_CONTACTS] Error collecting children for {parent_id}: {e}")
        # If it's a permission error, we just return what we have (don't crash the whole sync)
        if "40004" in str(e):
            print(f"[LARK_CONTACTS] Bypassing department fetch for {parent_id} due to 40004 permission error...")
        else:
            raise e

    return dept_ids


async def fetch_all_org_users() -> list[dict]:
    """
    Fetch all users across the entire organization.

    Returns:
        List of dicts: { name, email, avatar_url, department, open_id }
        Deduplicated by email.
    """
    token = await get_tenant_access_token()

    # Start recursion from the specific department ID you provided
    root_dept_id = "od-f1f9a48834fac7e5218e727d21ba1788"

    # Collect all department IDs recursively
    print(f"[LARK_CONTACTS] Collecting department tree starting from {root_dept_id}...")
    dept_ids = await _collect_all_department_ids(token, root_dept_id)
    print(f"[LARK_CONTACTS] Found {len(dept_ids)} departments")

    # Fetch users from each department
    seen_emails: set[str] = set()
    all_users: list[dict] = []

    for dept_id in dept_ids:
        raw_users = await _fetch_users_in_department(token, dept_id)

        for u in raw_users:
            email = u.get("email", "") or u.get("enterprise_email", "")
            if not email:
                # Skip users without email
                continue

            email_lower = email.lower()
            if email_lower in seen_emails:
                continue
            seen_emails.add(email_lower)

            # Extract department names
            dept_ids_list = u.get("department_ids", [])
            dept_name = dept_id  # fallback

            all_users.append({
                "name": u.get("name", "Unknown"),
                "email": email,
                "avatar_url": u.get("avatar", {}).get("avatar_240", ""),
                "department": dept_name,
                "open_id": u.get("open_id", ""),
            })

    print(f"[LARK_CONTACTS] Fetched {len(all_users)} unique users")
    return all_users
