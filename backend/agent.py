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
from bq_client import bq


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


def fetch_columns(table_name: str, columns: str, data_id: str) -> dict:
    """Fetch specific columns from a BigQuery table into the local DataFrame store.

    Use this tool AFTER reviewing the table stats from get_data_schema to select
    only the columns you need for visualization. The fetched data (up to 10,000 rows)
    is stored locally and can then be queried with query_data.

    Args:
        table_name: The BigQuery table name (e.g., "master_customer").
        columns: Comma-separated column names to fetch (e.g., "name,city,revenue").
        data_id: The data_id to store the fetched data under (same one from get_data_schema).

    Returns:
        dict: A dictionary with 'status', 'rows_fetched', 'columns_fetched',
              or 'error' if the fetch failed.
    """
    try:
        col_list = [c.strip() for c in columns.split(",") if c.strip()]
        if not col_list:
            return {"error": "No columns specified. Provide comma-separated column names."}

        rows = bq.fetch_columns(table_name, col_list, limit=10000)
        # Store the fetched data in the data manager
        data_manager.store_data_with_id(data_id, rows)

        return {
            "status": "success",
            "rows_fetched": len(rows),
            "columns_fetched": col_list,
            "message": f"Fetched {len(rows)} rows with columns {col_list}. Use query_data with data_id='{data_id}' to analyze.",
        }
    except Exception as e:
        return {"error": f"Failed to fetch columns: {str(e)}"}


# ──────────────────────────────────────────────
# System instruction
# ──────────────────────────────────────────────

SYSTEM_INSTRUCTION = """You are a Data Visualization Agent. Your ONLY purpose is to create data visualizations from datasets.

## CRITICAL RULE — YOU MUST FOLLOW THIS
You MUST call tools to get real data before generating your response.
NEVER generate chart data from your imagination. The "data" field MUST contain values returned by query_data.
If you return a response without calling query_data first, your output is WRONG.

## Step-by-Step Workflow (MANDATORY — do NOT skip any step)

### For JSON-pasted data (data_id is a short UUID like "abc123"):
Step 1: Call `get_data_schema(data_id)` → see columns, types, sample rows
Step 2: Call `query_data(data_id, query)` → get aggregated data for the chart
Step 3: Use the query_data result to build your JSON response

### For BigQuery tables (data_id starts with "bq_"):
Step 1: Call `get_data_schema(data_id)` → see column names, types, and stats (min/max/mean/distinct). No raw rows.
Step 2: Based on the user's question and column stats, decide which columns you need.
Step 3: Call `fetch_columns(table_name, columns, data_id)` → fetches real rows into a DataFrame.
Step 4: Call `query_data(data_id, query)` → aggregate/filter the fetched data for the chart.
Step 5: Use the query_data result to build your JSON response.

## Response Format
After completing ALL tool calls above, return ONLY a valid JSON object:
{
    "rejected": false,
    "chart_type": "line|bar|pie|scatter|area",
    "chart_config": {
        "x_field": "column_name_for_x_axis",
        "y_field": "column_name_for_y_axis",
        "data": [{"x_col": "val1", "y_col": 10}],
        "title": "Chart Title",
        "x_label": "X Axis Label",
        "y_label": "Y Axis Label"
    },
    "insight": "A brief observation about the data."
}

The "data" field MUST contain the actual data returned by query_data. NEVER make up data.

## Chart Type Guidelines
- **line**: Time series, trends over time
- **bar**: Category comparisons, rankings
- **pie**: Proportions (7 or fewer categories)
- **scatter**: Correlations between two numeric variables
- **area**: Cumulative trends, volume over time

## Rejection Rules
If the question is NOT about data visualization, return:
{"rejected": true, "reject_reason": "I can only help with data visualization."}

## Important Rules
- ALWAYS call get_data_schema FIRST — NEVER skip this step.
- ALWAYS call query_data to get chart data — NEVER skip this step.  
- For BigQuery tables, ALWAYS call fetch_columns between get_data_schema and query_data.
- Return ONLY valid JSON, no markdown fences, no extra text.
- The data field must contain REAL data from query_data, not placeholders.
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
    tools=[get_data_schema, query_data, fetch_columns],
)
