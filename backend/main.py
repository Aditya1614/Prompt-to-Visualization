"""
FastAPI backend for Prompt-to-Visualization feature.

Exposes /api/visualize endpoint that accepts a prompt + JSON data or BigQuery table name,
runs the Google ADK visualization agent via InMemoryRunner,
and returns chart config + insight.
"""
import json
import os

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


async def run_agent(prompt: str, data_id: str, table_name: str = "") -> tuple[str, TokenUsage]:
    """Run the ADK visualization agent and return the raw text response + token usage."""
    # Create a fresh session per request
    session = await runner.session_service.create_session(
        app_name=APP_NAME,
        user_id="user",
    )

    # Build user message with data_id context
    # Both BQ and JSON modes use the same message format:
    # The data is already stored as a DataFrame, agent just calls get_data_schema + query_data
    schema_info = data_manager.get_schema(data_id)
    schema_str = json.dumps(schema_info, indent=2, default=str)

    user_message = (
        f"Data ID: {data_id}\n\n"
        f"User Question: {prompt}\n\n"
        f"Here is the data schema:\n"
        f"{schema_str}\n\n"
        f"IMPORTANT: Call query_data(data_id=\"{data_id}\", query=\"...\") "
        f"to get the data for the chart, then return the visualization JSON."
    )

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)],
    )

    # Collect the final response and token usage from the agent
    # SAFETY: cap at 10 turns to prevent infinite loops and billing spikes
    MAX_AGENT_TURNS = 10
    final_response = ""
    total_prompt_tokens = 0
    total_completion_tokens = 0
    agent_turns = 0

    async for event in runner.run_async(
        session_id=session.id,
        user_id="user",
        new_message=content,
    ):
        # Debug logging (concise)
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"[AGENT] Tool call: {part.function_call.name}")
                if part.text:
                    print(f"[AGENT] Text from {event.author} (final={event.is_final_response()}, {len(part.text)} chars)")

        # Accumulate token usage from every event that has it
        if event.usage_metadata:
            um = event.usage_metadata
            total_prompt_tokens += getattr(um, 'prompt_token_count', 0) or 0
            total_completion_tokens += getattr(um, 'candidates_token_count', 0) or 0
            agent_turns += 1

        # Capture text from the agent — use the LAST text event as the response
        # (the agent may emit its final JSON in a non-final event)
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text and event.author and "agent" in event.author.lower():
                    final_response = part.text  # overwrite with latest text

        # Safety: break if agent exceeds max turns
        if agent_turns >= MAX_AGENT_TURNS:
            print(f"[SAFETY] Agent hit {MAX_AGENT_TURNS} turns limit — stopping.")
            break

    token_usage = TokenUsage(
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_prompt_tokens + total_completion_tokens,
        agent_turns=agent_turns,
    )

    return final_response, token_usage


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
        data_id = f"bq_{dataset}_{table_name}"

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
        raw_response, token_usage = await run_agent(request.prompt, data_id, table_name)

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
