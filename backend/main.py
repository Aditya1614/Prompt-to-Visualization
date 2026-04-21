"""
FastAPI backend for Prompt-to-Visualization feature.

Exposes /api/visualize endpoint that accepts a prompt + JSON data or BigQuery table name,
runs the Google ADK visualization agent via InMemoryRunner,
and returns chart config + insight.
"""
import json
import os
import re
import secrets
import uuid
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from google.adk.runners import InMemoryRunner

from google import genai
from google.genai import types

from agent import root_agent
from data_manager import data_manager
from bq_client import bq
from firestore_config import get_allowed_datasets
from auth import (
    build_lark_auth_url,
    exchange_code_for_token,
    get_lark_user_info,
    create_session_jwt,
    get_current_user,
    SESSION_COOKIE_NAME,
    FRONTEND_URL,
)
from models import (
    VisualizeRequest,
    VisualizeResponse,
    ChartConfig,
    TokenUsage,
    CountTokensResponse,
    TableListResponse,
    TableInfo,
    QuotaInfo,
    OrgUser,
    QuotaSettingEntry,
    UpdateUserRequest,
    RemoveUserRequest,
    SetAdminRequest,
    DatamartInfoAdmin,
    UpdateDatamartAccessRequest,
)
from token_quota import (
    get_quota_info, consume_tokens, is_registered,
    is_admin, get_all_quota_settings, update_user_quota, remove_user_quota,
    set_admin_role, get_all_datamarts, sync_datamarts, update_datamart_access, 
    has_datamart_access
)
from lark_contacts import fetch_all_org_users, fetch_org_hierarchy

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Load environment variables
load_dotenv()

# ──────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────

app = FastAPI(
    title="Prompt to Visualization API",
    description="AI-powered data visualization generator",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# ADK Runner (singleton)
# ──────────────────────────────────────────────

APP_NAME = "prompt_to_viz"
runner = InMemoryRunner(
    agent=root_agent,
    app_name=APP_NAME
)


# Initialize GenAI client for token counting
client = genai.Client()


QUERY_GEN_PROMPT = """\
You are a senior data analyst. Given a table schema and a user question, produce a single-line pandas expression that answers the question.

Today's date: {today}

Rules:
- The DataFrame is available as `df`.
- Your output must be ONLY the pandas expression string — no explanation, no markdown, no quotes around it.
- The expression must return a DataFrame limited to at most 30 rows.
- Sort order: for time-series / trend data (grouped by date/day/month), sort ASCENDING by date so the chart reads left-to-right chronologically. For rankings (top N categories), sort DESCENDING by the metric.
- Use .reset_index() when needed so the result has plain columns (not index labels).
- For date filters, ALWAYS use string-based pd.Timestamp like `pd.Timestamp("{today}")`. NEVER use `date.today()`, `datetime.date`, or bare Python date objects — they will cause a TypeError.
- Always cast date columns to datetime before comparing: `pd.to_datetime(df['col']) >= pd.Timestamp("{today}")`.

Schema:
{schema}

User question: {question}

Output (single-line pandas expression only):
"""

CHART_FORMAT_PROMPT = """\
You are a data visualization assistant. Given a user question and query results, produce a chart configuration.

User question: {question}

Query results (as JSON records):
{results}

Return ONLY a valid JSON object (no markdown fences, no extra text):
{{
    "rejected": false,
    "chart_type": "<chosen type>",
    "chart_config": {{
        "x_field": "<the x-axis column name>",
        "y_field": "<the y-axis column name>",
        "data": <paste the exact query results list here>,
        "title": "<descriptive title>",
        "x_label": "<x axis label>",
        "y_label": "<y axis label>"
    }},
    "insight": "<one sentence observation about the data>"
}}

Chart type selection rules (IMPORTANT):
- Use "line" when the x-axis is dates/time (trends, time series, daily/monthly data)
- Use "bar" when comparing categories or rankings (top N cities, products, etc.)
- Use "pie" when showing proportions with 7 or fewer slices
- Use "scatter" for correlations between two numeric variables
- Use "area" for cumulative volume over time

Other rules:
- x_field and y_field must be actual column names from the query results
- data must be the EXACT query results provided above — do NOT change any values
"""


async def run_agent_pipeline(prompt: str, data_id: str, history: list[dict] = None) -> tuple[str, TokenUsage]:
    """
    Stateful pipeline using Google ADK Agent.
    """
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

    # Reconstruct history transcript to embed in the prompt for stateless context awareness
    history_context = ""
    if history:
        for msg in history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_context += f"{role}: {msg.get('content')}\n\n"

    # Compound input for the agent
    user_input = f"""data_id: {data_id}

### NOTE ON DATA TYPES
- All date/time columns have ALREADY been converted to pandas datetime objects.
- Use them directly: `df[df['posting_date'] > ...]` is valid. 
- Do NOT use `df['col'] = pd.to_datetime(...)`.

### CONVERSATION HISTORY
{history_context if history_context else "No previous history."}

### CURRENT DATE
{datetime.now().strftime('%Y-%m-%d')}

### CURRENT USER REQUEST
{prompt}
"""
    
    try:
        # Create a unique session for this request
        # We use the runner's internal session_service to avoid extra imports
        sid = f"session_{uuid.uuid4().hex[:8]}"
        uid = "user_default"
        
        # Await session creation (InMemoryRunner's service is async)
        await runner.session_service.create_session(user_id=uid, session_id=sid, app_name=APP_NAME)

        
        # Run the agent using keyword-only arguments as per signature
        from google.genai import types
        
        events = runner.run(
            user_id=uid,
            session_id=sid,
            new_message=types.Content(role="user", parts=[types.Part(text=user_input)])
        )


        
        raw_json = ""
        last_text = ""
        prompt_tokens = 0
        completion_tokens = 0
        
        for event in events:
            # Capture token usage if present
            if hasattr(event, "usage_metadata") and event.usage_metadata:
                usage = event.usage_metadata
                prompt_tokens = usage.prompt_token_count or prompt_tokens
                completion_tokens = usage.candidates_token_count or completion_tokens
                logger.info(f"[ADK USAGE] Prompt: {prompt_tokens}, Completion: {completion_tokens}")

            # Improved debugging log
            author = getattr(event, "author", "Unknown")
            is_final = event.is_final_response()
            logger.info(f"[ADK EVENT] Author: {author}, Type: {type(event)}, Final: {is_final}")

            # Log parts if available to see what the agent is thinking/doing
            if hasattr(event, 'content') and event.content and event.content.parts:
                for i, part in enumerate(event.content.parts):
                    if part.text:
                        logger.info(f"  [PART {i} TEXT] {part.text[:200]}...")
                    if part.function_call:
                        logger.info(f"  [PART {i} TOOL CALL] {part.function_call.name}({part.function_call.args})")
            
            # Check for errors
            if hasattr(event, 'errors') and event.errors:
                logger.error(f"[ADK ERROR EVENT] {event.errors}")
                raise ValueError(f"Agent error event: {event.errors}")

            # Collect content from final response
            if getattr(event, 'content', None) and getattr(event.content, 'parts', None): # Safely access content and parts
                 for part in event.content.parts:
                    if getattr(part, 'text', None): # Safely access text
                         last_text = part.text # Fallback tracker
                         if getattr(event, 'is_final_response', lambda: False)(): # Safely call is_final_response
                            raw_json = part.text
        
        if not raw_json:
            if last_text:
                logger.warning("[ADK WARNING] No final response detected in event stream, using last generated text as fallback.")
                raw_json = last_text
            else:
                logger.error("[ADK ERROR] No final response detected in event stream, and no fallback text available.")
                raise ValueError("No text response from agent. Check backend logs for event stream.")


        
        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            agent_turns=1
        )
        
        return raw_json, token_usage
        
    except Exception as e:
        logger.error(f"[AGENT ERROR] {e}")
        return json.dumps({
            "rejected": True,
            "reject_reason": f"Agent error: {str(e)}"
        }), TokenUsage()




def parse_agent_response(raw: str) -> VisualizeResponse:
    """Parse the agent's raw JSON response into a structured VisualizeResponse."""
    import re

    cleaned = raw.strip()

    # Strategy 1: Strip markdown code fences
    # Handle ```json ... ```, ``` ... ```, or just raw JSON
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    else:
        # Strategy 2: Find the outermost { ... } in the response
        # This handles cases where the agent adds commentary before/after JSON
        brace_start = cleaned.find("{")
        brace_end = cleaned.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            cleaned = cleaned[brace_start:brace_end + 1]

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"[PARSE ERROR] {e}")
        logger.error(f"[RAW RESPONSE] {raw[:500]}")
        return VisualizeResponse(
            rejected=True,
            reject_reason="The AI agent returned an invalid response. Please try rephrasing your question.",
        )

    if data.get("rejected", False):
        return VisualizeResponse(
            rejected=True,
            reject_reason=data.get("reject_reason", "Your question is not related to data visualization."),
        )

    # Validate that the agent actually queried data (not just a stub response)
    chart_config_data = data.get("chart_config", {})
    chart_data = chart_config_data.get("data", [])
    
    if not chart_config_data or not chart_data:
        logger.warning(f"[VALIDATION] Agent returned response without chart data. Keys present: {list(data.keys())}")
        return VisualizeResponse(
            rejected=True,
            reject_reason="The AI agent failed to query the data. Please try again with a more specific question.",
        )

    # Build chart config
    chart_config = ChartConfig(
        x_field=chart_config_data.get("x_field", ""),
        y_field=chart_config_data.get("y_field", ""),
        data=chart_data,
        title=chart_config_data.get("title", ""),
        x_label=chart_config_data.get("x_label", ""),
        y_label=chart_config_data.get("y_label", ""),
        colors=chart_config_data.get("colors", []),
    )

    return VisualizeResponse(
        rejected=False,
        chart_type=data.get("chart_type", "bar"),
        chart_config=chart_config,
        insight=data.get("insight", ""),
    )


# ──────────────────────────────────────────────
# Auth Endpoints (public)
# ──────────────────────────────────────────────

@app.get("/api/auth/login")
async def auth_login():
    """Redirect the user to Lark's OAuth authorization page."""
    state = secrets.token_urlsafe(16)
    auth_url = build_lark_auth_url(state)
    return RedirectResponse(url=auth_url)


@app.get("/api/auth/callback")
async def auth_callback(code: str = "", error: str = "", state: str = ""):
    """
    Handle the OAuth callback from Lark.
    Exchanges auth code for token, fetches user info, creates session.
    """
    if error == "access_denied":
        return RedirectResponse(url=f"{FRONTEND_URL}?auth_error=access_denied")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Exchange code for user_access_token
    token_data = await exchange_code_for_token(code)
    access_token = token_data.get("access_token", "")

    if not access_token:
        raise HTTPException(status_code=401, detail="No access token received from Lark")

    # Fetch user info from Lark
    user_info = await get_lark_user_info(access_token)

    # Create a session JWT
    session_token = create_session_jwt(user_info)

    # Redirect to frontend with token in URL hash
    # (hash fragments are not sent to the server, keeping the token client-side only)
    redirect_url = f"{FRONTEND_URL}#token={session_token}"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.get("/api/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    """Return the current authenticated user's info."""
    return {
        "authenticated": True,
        "user": {
            "open_id": user.get("open_id", ""),
            "name": user.get("name", "Unknown"),
            "email": user.get("email", ""),
            "avatar_url": user.get("avatar_url", ""),
        },
    }


@app.post("/api/auth/logout")
async def auth_logout():
    """Logout endpoint. Token is cleared client-side from localStorage."""
    return {"status": "ok", "message": "Logged out"}


# ──────────────────────────────────────────────
# Public Endpoints
# ──────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "agent": "visualization_agent", "framework": "google-adk"}


# ──────────────────────────────────────────────
# Protected Endpoints (require Lark SSO)
# ──────────────────────────────────────────────

@app.get("/api/quota")
async def get_user_quota(user: dict = Depends(get_current_user)):
    """Get the current user's token quota info."""
    email = user.get("email", "")
    info = get_quota_info(email)
    return QuotaInfo(**info)

@app.get("/api/tables", response_model=TableListResponse)
async def list_tables(dataset: str = "", user: dict = Depends(get_current_user)):
    """List available BigQuery tables for the given dataset (company)."""
    # Force reload
    allowed = get_allowed_datasets()
    if not dataset or dataset not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid dataset. Allowed: {allowed}")
    try:
        tables_data = bq.list_tables(dataset)
        email = user.get("email", "")
        # Filter tables by ACL
        tables = [
            TableInfo(name=t["name"]) 
            for t in tables_data 
            if has_datamart_access(email, dataset, t["name"])
        ]
        return TableListResponse(dataset=dataset, tables=tables)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {str(e)}")


@app.post("/api/count-tokens", response_model=CountTokensResponse)
async def count_tokens(request: VisualizeRequest, user: dict = Depends(get_current_user)):
    """Estimate the token count for the prompt and data."""
    if not request.data:
        text_to_count = request.prompt
    else:
        text_to_count = f"{request.prompt}\n{json.dumps(request.data)}"

    try:
        response = client.models.count_tokens(
            model="gemini-2.0-flash",
            contents=text_to_count
        )
        return CountTokensResponse(total_tokens=response.total_tokens)
    except Exception as e:
        logger.error(f"Token counting error: {e}")
        raise HTTPException(status_code=500, detail=f"Token counting failed: {str(e)}")


@app.post("/api/visualize", response_model=VisualizeResponse)
async def visualize(request: VisualizeRequest, user: dict = Depends(get_current_user)):
    """
    Generate a visualization from a user prompt and data.

    Supports two modes:
    1. JSON mode: request.data contains the JSON array
    2. BigQuery mode: request.table_name specifies the BQ table
    """
    email = user.get("email", "")

    # Check if user is registered for quota
    if not is_registered(email):
        raise HTTPException(
            status_code=403,
            detail="You are not registered to use this service. Please contact the Data Team for access.",
        )

    # Check if user has tokens remaining
    quota_info = get_quota_info(email)
    if quota_info["remaining"] <= 0:
        raise HTTPException(
            status_code=429,
            detail=f"Daily token quota exceeded ({quota_info['daily_limit']:,} tokens). Quota resets tomorrow.",
        )

    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    table_name = ""
    data_id = ""

    if request.table_name:
        # BigQuery mode — pre-fetch ALL columns into a DataFrame
        # This way the agent treats it identically to JSON paste mode
        table_name = request.table_name
        allowed = get_allowed_datasets()
        dataset = request.dataset or (allowed[0] if allowed else "pis")
        
        # Enforce ACL
        if not has_datamart_access(email, dataset, table_name):
            raise HTTPException(status_code=403, detail=f"You do not have access to datamart {dataset}.{table_name}")

        # Use a UUID so concurrent users requesting the same table don't share/overwrite data
        data_id = f"bq_{dataset}_{table_name}_{uuid.uuid4().hex[:8]}"

        try:
            rows = bq.fetch_all_rows(table_name, dataset)
            data_manager.store_data_with_id(data_id, rows)
            logger.info(f"[BQ] Loaded {len(rows)} rows from {dataset}.{table_name}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load table data: {str(e)}")

    elif request.data:
        # JSON paste mode
        if not isinstance(request.data, list) or len(request.data) == 0:
            raise HTTPException(status_code=400, detail="Data must be a non-empty JSON array")
        data_id = data_manager.store_data(request.data)

    else:
        raise HTTPException(status_code=400, detail="Either 'data' or 'table_name' must be provided")

    try:
        raw_response, token_usage = await run_agent_pipeline(request.prompt, data_id, request.history)

        if not raw_response:
            return VisualizeResponse(
                rejected=True,
                reject_reason="The AI agent did not return a response. Please try again.",
                token_usage=token_usage,
            )

        response = parse_agent_response(raw_response)
        response.token_usage = token_usage

        # Deduct tokens from quota
        try:
            updated_quota = consume_tokens(email, token_usage.total_tokens)
            response.quota = QuotaInfo(**updated_quota)
        except ValueError as qe:
            logger.error(f"[QUOTA] Warning: {qe}")

        return response


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    finally:
        data_manager.clear(data_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


# ──────────────────────────────────────────────
# Admin Endpoints (require admin role)
# ──────────────────────────────────────────────

def require_admin(user: dict) -> None:
    """Raise 403 if user is not an admin."""
    email = user.get("email", "")
    if not is_admin(email):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required.",
        )


@app.get("/api/admin/org-users")
async def admin_get_org_users(user: dict = Depends(get_current_user)):
    """Fetch all users from the Lark organization."""
    require_admin(user)
    try:
        users = await fetch_all_org_users()
        return {"users": [OrgUser(**u) for u in users]}
    except Exception as e:
        logger.error(f"[ADMIN] Org user fetch error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch org users: {str(e)}")


@app.get("/api/admin/org-hierarchy")
async def admin_get_org_hierarchy(user: dict = Depends(get_current_user)):
    """Fetch structured departments and users from Lark."""
    require_admin(user)
    try:
        hierarchy = await fetch_org_hierarchy()
        return {"departments": hierarchy}
    except Exception as e:
        logger.error(f"[ADMIN] Org hierarchy fetch error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch org hierarchy: {str(e)}")


@app.get("/api/admin/quota-settings")
async def admin_get_quota_settings(user: dict = Depends(get_current_user)):
    """Get all registered users with their quota settings and usage."""
    require_admin(user)
    entries = get_all_quota_settings()
    return {"users": [QuotaSettingEntry(**e) for e in entries]}


@app.post("/api/admin/update-user")
async def admin_update_user(
    request: UpdateUserRequest, user: dict = Depends(get_current_user)
):
    """Add or update a user's quota settings."""
    require_admin(user)
    result = update_user_quota(request.email, request.name, request.daily_limit, request.department)
    return {"status": "ok", "user": result}


@app.post("/api/admin/remove-user")
async def admin_remove_user(
    request: RemoveUserRequest, user: dict = Depends(get_current_user)
):
    """Remove a user's access."""
    require_admin(user)
    removed = remove_user_quota(request.email)
    if not removed:
        raise HTTPException(status_code=404, detail=f"User {request.email} not found.")
    return {"status": "ok", "removed": request.email}

@app.post("/api/admin/set-admin")
async def admin_set_admin(
    request: SetAdminRequest, user: dict = Depends(get_current_user)
):
    """Update a user's admin role."""
    require_admin(user)
    
    # Prevent self-demotion
    if not request.is_admin and request.email.lower() == user.get("email", "").lower():
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role.")
        
    set_admin_role(request.email, request.is_admin)
    return {"status": "ok", "email": request.email, "is_admin": request.is_admin}


# ── Datamart ACL Endpoints ──────────────────────────────────────────

@app.get("/api/admin/datamarts")
async def admin_get_datamarts(user: dict = Depends(get_current_user)):
    """Fetch all configured datamarts and their access list."""
    require_admin(user)
    datamarts = get_all_datamarts()
    
    # Format into a list of DatamartInfoAdmin
    results = []
    for key, emails in datamarts.items():
        if "." in key:
            ds, tbl = key.split(".", 1)
            results.append(DatamartInfoAdmin(dataset=ds, table=tbl, allowed_users=emails))
            
    return {"datamarts": results}


@app.post("/api/admin/sync-datamarts")
async def admin_sync_datamarts(user: dict = Depends(get_current_user)):
    """Sync list of tables from BigQuery datasets and append to config."""
    require_admin(user)
    available = []
    allowed = get_allowed_datasets()
    if not allowed:
        logger.warning("[SYNC] No allowed datasets configured in Firestore. Skipping sync to prevent accidental deletion.")
        return {"status": "error", "message": "No allowed datasets configured. Please check prompt_to_viz_config/allowed_datasets in Firestore."}

    for dataset in allowed:
        try:
            tables = bq.list_tables(dataset)
            for t in tables:
                available.append({"dataset": dataset, "table": t["name"]})
        except Exception as e:
            logger.error(f"[BQ SYNC ERROR] Dataset {dataset}: {e}")
            
    if not available:
        logger.warning("[SYNC] BigQuery returned 0 tables for all allowed datasets. Skipping sync to prevent accidental deletion.")
        return {"status": "error", "message": "No tables found in BigQuery datasets. Check your BQ permissions or dataset names."}

    updated = sync_datamarts(available)
    return {"status": "ok", "synced_count": len(available), "total_configured": len(updated)}


@app.post("/api/admin/update-datamart-access")
async def admin_update_datamart_access(
    request: UpdateDatamartAccessRequest, user: dict = Depends(get_current_user)
):
    """Update user access list for a specific datamart."""
    require_admin(user)
    updated = update_datamart_access(request.dataset, request.table, request.allowed_users)
    return {"status": "ok", "dataset": request.dataset, "table": request.table, "allowed_users": request.allowed_users}
