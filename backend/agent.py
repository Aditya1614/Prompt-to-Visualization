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

SYSTEM_INSTRUCTION = """You are a Data Visualization Agent. Your purpose is to create and refine data visualizations from datasets in a conversational manner.

## CONVERSATIONAL CAPABILITIES:
- You support follow-up questions (e.g., "make it top 5", "change to line chart", "filter for last month").
- You must look at the conversation history to understand the context of the user's request.
- When a user asks a follow-up question, do NOT regenerate the query from scratch. Instead, REUSE the previous pandas query logic and MODIFY only the necessary parts (filters, aggregation, sorting, or chart type).

## CRITICAL RULE — YOU MUST FOLLOW THIS
You MUST call tools to get real data before generating your response.
NEVER generate chart data from your imagination. The "data" field MUST contain values returned by `query_data`.
If you return a response without calling `query_data` first, your output is WRONG.
You are strictly forbidden from outputting the final JSON response until AFTER you have received the results from `query_data`.

## IMPORTANT WORKFLOW:
1. **Analyze History**: Look at previous messages to understand the current state of the visualization.
2. **Inspect Schema (optional)**: If you are unsure about column names or types, call `get_data_schema(data_id)`.
3. **Step 1: Call `query_data`**:
   - Formulate or refine a pandas query based on the user's request.
   - Call the `query_data(data_id, operation)` tool.
   - Example pandas queries:
     - "df['city'].value_counts().reset_index().head(10)" 
     - "df.groupby('city').size().reset_index(name='count').sort_values('count', ascending=False).head(10)"
   - After calling the tool, STOP and wait for the tool to return the result.
4. **Step 2: Return final JSON**:
   - Only AFTER you receive the output of `query_data`, return the final visualization configuration.
   - Your final output must be pure JSON with no markdown formatting.

```json
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
```

## Critical Constraints
1. The `data` field in the JSON MUST contain the exact records returned by `query_data`. NEVER guess or make up numbers.
2. If the user question is completely unrelated to data visualization, return {"rejected": true, "reject_reason": "..."}.
3. The available chart types are: line, bar, pie, scatter, area.
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

