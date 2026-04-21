"""Data Manager — stores and queries user-provided data via pandas."""
import uuid
import pandas as pd
from typing import Any


class DataManager:
    """In-memory session store: data_id → pandas DataFrame."""

    def __init__(self):
        self._store: dict[str, pd.DataFrame] = {}
        self._schemas: dict[str, dict] = {}  # BQ table stats

    def _auto_convert_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Scan string columns and convert to datetime if they match date patterns."""
        import logging
        logger = logging.getLogger(__name__)
        
        for col in df.columns:
            # We mostly care about 'object' (string) columns
            if df[col].dtype == object:
                # 1. Check for common date names to be more aggressive
                is_date_named = any(word in col.lower() for word in ['date', 'time', 'posted', 'created', 'updated'])
                
                # 2. Try converting
                try:
                    # errors='coerce' turns non-decodable strings into NaT
                    converted = pd.to_datetime(df[col], errors='coerce')
                    
                    # 3. Decision: If at least 50% of non-null values converted successfully, 
                    # OR it's a date-named column and has at least one valid date.
                    valid_count = converted.notna().sum()
                    total_non_null = df[col].notna().sum()
                    
                    if total_non_null > 0:
                        if valid_count / total_non_null > 0.5 or (is_date_named and valid_count > 0):
                            df[col] = converted
                            logger.info(f"[DATA MANAGER] Auto-converted column '{col}' to datetime (Valid: {valid_count}/{total_non_null})")
                except Exception as e:
                    # If it's a huge mess, just skip
                    pass
        return df

    def store_data(self, json_data: list[dict[str, Any]]) -> str:
        """Store JSON data as a DataFrame and return a unique data_id."""
        data_id = str(uuid.uuid4())[:8]
        df = pd.DataFrame(json_data)
        df = self._auto_convert_dates(df)
        self._store[data_id] = df
        return data_id

    def store_data_with_id(self, data_id: str, json_data: list[dict[str, Any]]):
        """Store JSON data under a specific data_id (used by fetch_columns tool)."""
        df = pd.DataFrame(json_data)
        df = self._auto_convert_dates(df)
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
            "sample_rows": self._to_serializable_dict(df.head(3)),
        }

    def _to_serializable_dict(self, df: pd.DataFrame) -> list[dict]:
        """Helper to convert DataFrame to dict while handling non-serializable dates and timestamps."""
        if df.empty:
            return []
        
        # Create a temporary copy for serialization
        temp_df = df.copy()
        
        # Convert all datetime/date/timestamp columns to ISO format strings
        for col in temp_df.columns:
            # 1. Handle explicit datetime64 columns
            if pd.api.types.is_datetime64_any_dtype(temp_df[col]):
                temp_df[col] = temp_df[col].dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', None)
            
            # 2. Handle 'object' columns that might contain date/datetime objects (even if mixed with None/NaN)
            elif pd.api.types.is_object_dtype(temp_df[col]):
                # Convert to datetime (errors='ignore' handles non-date strings)
                # Then check if it actually resulted in datetime objects
                converted = pd.to_datetime(temp_df[col], errors='coerce')
                if not converted.isna().all():
                    # If this column has valid dates, convert them to strings
                    # We only apply this if the column seems meant to be dates
                    temp_df[col] = converted.dt.strftime('%Y-%m-%d %H:%M:%S').where(converted.notna(), temp_df[col])
                    # If it was purely dates, it will now be strings. 
                    # If it was mixed, the date parts are now ISO strings.

            # 3. Fallback for any remaining non-serializable objects (like datetime.date)
            # Use apply with a lambda to handle row-by-row
        # Finally, convert to list of dicts
        records = temp_df.to_dict(orient="records")
        
        # FINAL SANITIZATION: JSON standard does NOT support NaN, Inf, or -Inf.
        # We must replace them with None (which becomes null in JSON) to avoid
        # '400 INVALID_ARGUMENT' errors from the GenAI API.
        import math
        for row in records:
            for key, val in row.items():
                # 1. Handle NumPy/Python NaNs and Infs
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    row[key] = None
                # 2. Handle pandas NaT (Not a Time) which might remain in some edge cases
                elif pd.isna(val):
                    row[key] = None
        
        return records

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
            import datetime as _dt
            # Execute the pandas operation
            # Provide a rich eval context so LLM-generated date expressions work
            eval_context = {
                "df": df,
                "pd": pd,
                "datetime": _dt,
                "date": _dt.date,
                "timedelta": _dt.timedelta,
            }
            result = eval(operation, eval_context)
            # Convert result to records
            if isinstance(result, pd.DataFrame):
                return {"data": self._to_serializable_dict(result), "row_count": len(result)}
            elif isinstance(result, pd.Series):
                result_df = result.reset_index()
                return {"data": self._to_serializable_dict(result_df), "row_count": len(result_df)}
            else:
                return {"data": str(result), "row_count": 1}

        except Exception as e:
            return {"error": f"Query failed: {str(e)}"}

    def clear(self, data_id: str):
        """Remove stored data."""
        self._store.pop(data_id, None)


# Singleton instance
data_manager = DataManager()
