"""
Lark SSO authentication module.

Handles OAuth 2.0 authorization code flow with Lark and
JWT-based session management for the application.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import Request, HTTPException


# ──────────────────────────────────────────────
# Configuration (from environment)
# ──────────────────────────────────────────────

LARK_CLIENT_ID = os.getenv("LARK_CLIENT_ID", "")
LARK_CLIENT_SECRET = os.getenv("LARK_CLIENT_SECRET", "")
LARK_REDIRECT_URI = os.getenv("LARK_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", secrets.token_hex(32))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Lark API endpoints
LARK_AUTH_URL = "https://accounts.larksuite.com/open-apis/authen/v1/authorize"
LARK_TOKEN_URL = "https://open.larksuite.com/open-apis/authen/v2/oauth/token"
LARK_USER_INFO_URL = "https://open.larksuite.com/open-apis/authen/v1/user_info"

# Session JWT config
SESSION_COOKIE_NAME = "lark_session"
SESSION_EXPIRY_HOURS = 24

# Lark permission scopes
LARK_SCOPES = "contact:user.base:readonly contact:user.email:readonly"


def build_lark_auth_url(state: str) -> str:
    """
    Construct the Lark OAuth authorization URL.

    Args:
        state: Anti-CSRF state parameter

    Returns:
        The full Lark authorization URL to redirect the user to.
    """
    from urllib.parse import quote

    # Use quote() (not quote_plus) to match Lark's expected encoding
    redirect_uri_encoded = quote(LARK_REDIRECT_URI, safe="")
    scope_encoded = quote(LARK_SCOPES, safe="")

    return (
        f"{LARK_AUTH_URL}"
        f"?client_id={LARK_CLIENT_ID}"
        f"&redirect_uri={redirect_uri_encoded}"
        f"&state={state}"
        f"&scope={scope_encoded}"
    )


async def exchange_code_for_token(code: str) -> dict:
    """
    Exchange an authorization code for a user_access_token.

    POST to Lark's token endpoint with the auth code.

    Args:
        code: The authorization code from Lark redirect

    Returns:
        Dict with access_token, refresh_token, etc.

    Raises:
        HTTPException: If the token exchange fails
    """
    payload = {
        "grant_type": "authorization_code",
        "client_id": LARK_CLIENT_ID,
        "client_secret": LARK_CLIENT_SECRET,
        "code": code,
        "redirect_uri": LARK_REDIRECT_URI,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(LARK_TOKEN_URL, json=payload)

    data = resp.json()

    if resp.status_code != 200 or data.get("code", -1) != 0:
        error_msg = data.get("msg", data.get("error_description", "Unknown error"))
        print(f"[AUTH] Token exchange failed: {data}")
        raise HTTPException(status_code=401, detail=f"Lark token exchange failed: {error_msg}")

    return data


async def get_lark_user_info(access_token: str) -> dict:
    """
    Fetch the authenticated user's profile from Lark.

    Args:
        access_token: The user_access_token from Lark

    Returns:
        Dict with user info: name, email, avatar_url, open_id, etc.

    Raises:
        HTTPException: If the user info request fails
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(LARK_USER_INFO_URL, headers=headers)

    data = resp.json()

    if resp.status_code != 200 or data.get("code", -1) != 0:
        print(f"[AUTH] User info fetch failed: {data}")
        raise HTTPException(status_code=401, detail="Failed to fetch user info from Lark")

    user_data = data.get("data", {})
    return {
        "open_id": user_data.get("open_id", ""),
        "name": user_data.get("name", "Unknown"),
        "email": user_data.get("email", ""),
        "avatar_url": user_data.get("avatar_url", ""),
        "tenant_key": user_data.get("tenant_key", ""),
    }


def create_session_jwt(user_info: dict) -> str:
    """
    Create a signed JWT containing user identity.

    Args:
        user_info: Dict with open_id, name, email, avatar_url

    Returns:
        Signed JWT string
    """
    now = datetime.now(timezone.utc)
    payload = {
        **user_info,
        "iat": now,
        "exp": now + timedelta(hours=SESSION_EXPIRY_HOURS),
    }
    return jwt.encode(payload, SESSION_SECRET_KEY, algorithm="HS256")


def verify_session_jwt(token: str) -> dict:
    """
    Validate and decode a session JWT.

    Args:
        token: The JWT string

    Returns:
        Decoded payload dict

    Raises:
        HTTPException: If the token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SESSION_SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please login again.")


def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency that extracts and validates the session token.

    Checks (in order):
    1. Authorization: Bearer <token> header (for cross-domain frontend)
    2. Session cookie (for same-domain setups)

    Raises:
        HTTPException 401: If no valid session exists
    """
    token = None

    # Check Authorization header first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # Fall back to cookie
    if not token:
        token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated. Please login with Lark SSO.",
        )
    return verify_session_jwt(token)
