"""Data Manager — stores and queries user-provided data via pandas."""
import uuid
import pandas as pd
from typing import Any


class DataManager:
    """In-memory session store: data_id → pandas DataFrame."""

    def __init__(self):
        self._store: dict[str, pd.DataFrame] = {}
        self._schemas: dict[str, dict] = {}  # BQ table stats

    def store_data(self, json_data: list[dict[str, Any]]) -> str:
        """Store JSON data as a DataFrame and return a unique data_id."""
        data_id = str(uuid.uuid4())[:8]
        df = pd.DataFrame(json_data)
        self._store[data_id] = df
        return data_id

    def store_data_with_id(self, data_id: str, json_data: list[dict[str, Any]]):
        """Store JSON data under a specific data_id (used by fetch_columns tool)."""
        df = pd.DataFrame(json_data)
        self._store[data_id] = df

    def store_schema(self, data_id: str, stats: dict):
        """Store BQ table stats as a schema-only entry.

        When get_schema is called for this data_id, it returns the precomputed
        stats (min/max/mean/distinct) instead of sample rows.
        """
        self._schemas[data_id] = stats

    def get_schema(self, data_id: str) -> dict:
        """Return column names, dtypes, row count, and sample rows (or BQ stats)."""
        # If BQ stats are stored, return them (no raw data)
        if data_id in self._schemas:
            return self._schemas[data_id]

        df = self._store.get(data_id)
        if df is None:
            return {"error": f"No data found for id '{data_id}'"}

        return {
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "row_count": len(df),
            "sample_rows": df.head(3).to_dict(orient="records"),
        }

    def query_data(self, data_id: str, operation: str) -> dict:
        """
        Execute a pandas operation on the stored DataFrame.

        The `operation` string is a valid pandas expression that will be evaluated
        on the DataFrame. Examples:
          - "df.groupby('category')['sales'].sum().reset_index()"
          - "df[df['amount'] > 100]"
          - "df.sort_values('date')"
          - "df.describe()"
          - "df[['name', 'value']].head(10)"

        Returns the result as a list of dicts (records).
        """
        df = self._store.get(data_id)
        if df is None:
            return {"error": f"No data found for id '{data_id}'"}

        try:
            # Execute the pandas operation
            result = eval(operation, {"df": df, "pd": pd})

            # Convert result to records
            if isinstance(result, pd.DataFrame):
                return {"data": result.to_dict(orient="records"), "row_count": len(result)}
            elif isinstance(result, pd.Series):
                result_df = result.reset_index()
                return {"data": result_df.to_dict(orient="records"), "row_count": len(result_df)}
            else:
                return {"data": str(result), "row_count": 1}

        except Exception as e:
            return {"error": f"Query failed: {str(e)}"}

    def clear(self, data_id: str):
        """Remove stored data."""
        self._store.pop(data_id, None)


# Singleton instance
data_manager = DataManager()
