"""
Visualization Agent — Google ADK agent with data query tools.

Uses google.adk.agents.Agent with function calling tools for
token-efficient data inspection and querying. The agent is constrained
to data visualization tasks only via its system instruction.

Supports two data sources:
  1. JSON paste mode: data already stored in pandas via DataManager
  2. BigQuery mode: agent fetches columns from BQ into pandas
"""
import os
from dotenv import load_dotenv

# Load .env BEFORE importing ADK so env vars are available
load_dotenv()

# Tell the ADK/genai client to use Vertex AI backend
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

from google.adk.agents import Agent
from data_manager import data_manager

# ──────────────────────────────────────────────
# Tool functions (auto-wrapped by ADK as FunctionTools)
# ──────────────────────────────────────────────

def get_data_schema(data_id: str) -> dict:
    """Inspect the schema of a dataset.

    Returns column names, data types, total row count, and 3 sample rows.
    Use this tool FIRST to understand the data before querying it.

    Args:
        data_id: The unique identifier of the dataset to inspect.

    Returns:
        dict: A dictionary containing columns, dtypes, row_count, and sample_rows.
    """
    return data_manager.get_schema(data_id)


def query_data(data_id: str, operation: str) -> dict:
    """Query and transform a dataset using pandas operations.

    Use this tool to filter, aggregate, sort, or select specific columns
    from the dataset. The operation must be a valid pandas expression.

    Examples of valid operations:
    - "df.groupby('category')['sales'].sum().reset_index()"
    - "df[df['amount'] > 100]"
    - "df.sort_values('date')"
    - "df[['name', 'value']].head(20)"
    - "df.describe()"
    - "df['column'].value_counts().reset_index()"

    Args:
        data_id: The unique identifier of the dataset to query.
        operation: A pandas expression to execute on the DataFrame.
                   The DataFrame is available as 'df' in the expression.

    Returns:
        dict: A dictionary with 'data' (list of records) and 'row_count',
              or 'error' if the operation failed.
    """
    return data_manager.query_data(data_id, operation)





# ──────────────────────────────────────────────
# System instruction
# ──────────────────────────────────────────────

SYSTEM_INSTRUCTION = """You are a Data Visualization Agent.

## ABSOLUTE RULE — TOOL CALLS ARE MANDATORY
You MUST call the `query_data` tool BEFORE you produce ANY text output.
DO NOT output any JSON, any text, or any response before you have called `query_data` and received its results.
A response without a preceding `query_data` tool call is INVALID and FORBIDDEN.

## MANDATORY WORKFLOW — follow these steps IN ORDER, with NO exceptions:

### Step 1: Understand the request
Read the user's question and the conversation history. Identify what data operation is needed.

### Step 2: Inspect schema (if needed)
If you are unsure about column names or data types, call `get_data_schema(data_id)`.

### Step 3: CALL `query_data` — THIS IS MANDATORY
You MUST call the `query_data(data_id, operation)` tool with a pandas expression.
- Use the `data_id` provided in the user message.
- The DataFrame is available as `df` in the expression.
- Limit results to at most 30 rows.
- For date filtering, use `pd.Timestamp("YYYY-MM-DD")`. Do NOT cast columns manually as they are **already converted** to pandas datetime objects.
- Example operations:
  - `df.groupby('category')['amount'].sum().reset_index().sort_values('amount', ascending=False).head(10)`
  - `df[df['date'] >= pd.Timestamp("2026-03-20")].groupby(pd.Grouper(key='date', freq='W'))['qty'].sum().reset_index()`

After calling `query_data`, STOP and WAIT for the tool result. Do NOT generate any text yet.

### Step 4: Format the response using REAL data
ONLY after you receive the `query_data` result, produce your final answer as pure JSON (no markdown fences):
{
    "rejected": false,
    "chart_type": "<line|bar|pie|scatter|area>",
    "chart_config": {
        "x_field": "<column_name_for_x_axis>",
        "y_field": "<column_name_for_y_axis>",
        "data": <PASTE THE EXACT RECORDS FROM query_data HERE>,
        "title": "<descriptive title>",
        "x_label": "<x axis label>",
        "y_label": "<y axis label>"
    },
    "insight": "<one sentence observation about the data>"
}

## RULES
1. The `data` field MUST contain the EXACT records returned by `query_data`. NEVER invent data.
2. If the user question is unrelated to data visualization, return: {"rejected": true, "reject_reason": "..."}
3. Chart types: line, bar, pie, scatter, area.
4. Chart type selection: use "line" for time-series, "bar" for category comparisons, "pie" for proportions (≤7 slices), "scatter" for correlations, "area" for cumulative volume.
5. For follow-up questions, REUSE the previous query logic and MODIFY only the changed parts — but you MUST still call `query_data` again with the updated expression.

## WHAT NOT TO DO
- NEVER skip the `query_data` tool call.
- NEVER output the final JSON before calling `query_data`.
- NEVER fabricate or estimate data values.
- NEVER wrap your JSON in markdown code fences (no triple backticks).
"""

# ──────────────────────────────────────────────
# ADK Agent definition
# ──────────────────────────────────────────────

from google.genai import types

root_agent = Agent(
    name="visualization_agent",
    model="gemini-2.0-flash",
    description="Agent that creates data visualizations from user datasets.",
    instruction=SYSTEM_INSTRUCTION,
    tools=[get_data_schema, query_data],
)

