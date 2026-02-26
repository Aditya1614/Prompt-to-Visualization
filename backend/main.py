"""
FastAPI backend for Prompt-to-Visualization feature.

Exposes /api/visualize endpoint that accepts a prompt + JSON data or BigQuery table name,
runs the Google ADK visualization agent via InMemoryRunner,
and returns chart config + insight.
"""
import json
import os
import re
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from google.adk.runners import InMemoryRunner
from google import genai
from google.genai import types

from agent import root_agent
from data_manager import data_manager
from bq_client import bq, ALLOWED_DATASETS
from models import (
    VisualizeRequest,
    VisualizeResponse,
    ChartConfig,
    TokenUsage,
    CountTokensResponse,
    TableListResponse,
    TableInfo,
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
    app_name=APP_NAME,
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


async def run_pipeline(prompt: str, data_id: str) -> tuple[str, TokenUsage]:
    """
    Deterministic 2-pass pipeline:
      Pass 1 — LLM generates a pandas query string
      Pass 2 — Python executes it; LLM formats the results as chart JSON
    """
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

    total_prompt_tokens = 0
    total_completion_tokens = 0

    schema_info = data_manager.get_schema(data_id)
    schema_str = json.dumps(schema_info, indent=2, default=str)

    from datetime import date
    today_str = date.today().isoformat()  # e.g. "2026-02-26"

    # ── Pass 1: generate pandas query ──────────────────────────────────────
    pass1_prompt = QUERY_GEN_PROMPT.format(schema=schema_str, question=prompt, today=today_str)
    pass1_resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=pass1_prompt,
    )
    if pass1_resp.usage_metadata:
        total_prompt_tokens += pass1_resp.usage_metadata.prompt_token_count or 0
        total_completion_tokens += pass1_resp.usage_metadata.candidates_token_count or 0

    pandas_query = pass1_resp.text.strip().strip("`").strip()
    # Strip leading "python" if model wrapped it in a code fence
    pandas_query = re.sub(r'^python\s+', '', pandas_query, flags=re.IGNORECASE).strip()

    print(f"[PIPELINE] Pass 1 — generated pandas query:\n  {pandas_query}")

    # ── Execute query deterministically ──────────────────────────────────
    query_result = data_manager.query_data(data_id, pandas_query)
    if "error" in query_result:
        print(f"[PIPELINE] Query error: {query_result['error']}")
        return json.dumps({
            "rejected": True,
            "reject_reason": f"Could not execute the data query: {query_result['error']}"
        }), TokenUsage(prompt_tokens=total_prompt_tokens,
                       completion_tokens=total_completion_tokens,
                       total_tokens=total_prompt_tokens + total_completion_tokens,
                       agent_turns=1)

    result_records = query_result.get("data", [])
    print(f"[PIPELINE] Query returned {len(result_records)} rows")

    # ── Pass 2: format results as chart JSON ──────────────────────────────
    results_str = json.dumps(result_records, ensure_ascii=False, indent=2, default=str)
    pass2_prompt = CHART_FORMAT_PROMPT.format(question=prompt, results=results_str)
    pass2_resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=pass2_prompt,
    )
    if pass2_resp.usage_metadata:
        total_prompt_tokens += pass2_resp.usage_metadata.prompt_token_count or 0
        total_completion_tokens += pass2_resp.usage_metadata.candidates_token_count or 0

    raw_json = pass2_resp.text.strip()
    print(f"[PIPELINE] Pass 2 — chart JSON received ({len(raw_json)} chars)")

    token_usage = TokenUsage(
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_prompt_tokens + total_completion_tokens,
        agent_turns=2,
    )
    return raw_json, token_usage


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
        print(f"[PARSE ERROR] {e}")
        print(f"[RAW RESPONSE] {raw[:500]}")
        return VisualizeResponse(
            rejected=True,
            reject_reason="The AI agent returned an invalid response. Please try rephrasing your question.",
        )

    if data.get("rejected", False):
        return VisualizeResponse(
            rejected=True,
            reject_reason=data.get("reject_reason", "Your question is not related to data visualization."),
        )

    # Build chart config
    chart_config_data = data.get("chart_config", {})
    chart_config = ChartConfig(
        x_field=chart_config_data.get("x_field", ""),
        y_field=chart_config_data.get("y_field", ""),
        data=chart_config_data.get("data", []),
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
# Endpoints
# ──────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "agent": "visualization_agent", "framework": "google-adk"}


@app.get("/api/tables", response_model=TableListResponse)
async def list_tables(dataset: str = ""):
    """List available BigQuery tables for the given dataset (company)."""
    # Force reload
    if not dataset or dataset not in ALLOWED_DATASETS:
        raise HTTPException(status_code=400, detail=f"Invalid dataset. Allowed: {ALLOWED_DATASETS}")
    try:
        tables_data = bq.list_tables(dataset)
        tables = [TableInfo(name=t["name"]) for t in tables_data]
        return TableListResponse(dataset=dataset, tables=tables)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tables: {str(e)}")


@app.post("/api/count-tokens", response_model=CountTokensResponse)
async def count_tokens(request: VisualizeRequest):
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
        print(f"Token counting error: {e}")
        raise HTTPException(status_code=500, detail=f"Token counting failed: {str(e)}")


@app.post("/api/visualize", response_model=VisualizeResponse)
async def visualize(request: VisualizeRequest):
    """
    Generate a visualization from a user prompt and data.

    Supports two modes:
    1. JSON mode: request.data contains the JSON array
    2. BigQuery mode: request.table_name specifies the BQ table
    """
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    table_name = ""
    data_id = ""

    if request.table_name:
        # BigQuery mode — pre-fetch ALL columns into a DataFrame
        # This way the agent treats it identically to JSON paste mode
        table_name = request.table_name
        dataset = request.dataset or ALLOWED_DATASETS[0]
        # Use a UUID so concurrent users requesting the same table don't share/overwrite data
        data_id = f"bq_{dataset}_{table_name}_{uuid.uuid4().hex[:8]}"

        try:
            rows = bq.fetch_all_rows(table_name, dataset)
            data_manager.store_data_with_id(data_id, rows)
            print(f"[BQ] Loaded {len(rows)} rows from {dataset}.{table_name}")
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
        raw_response, token_usage = await run_pipeline(request.prompt, data_id)

        if not raw_response:
            return VisualizeResponse(
                rejected=True,
                reject_reason="The AI agent did not return a response. Please try again.",
                token_usage=token_usage,
            )

        response = parse_agent_response(raw_response)
        response.token_usage = token_usage
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    finally:
        data_manager.clear(data_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
