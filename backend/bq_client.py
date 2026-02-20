"""
BigQuery Client — fetches table metadata and data from BigQuery.

Uses the same service account credentials as the rest of the backend.
Dataset is passed dynamically per-request (selected by the user as "Company").
"""
import os
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

# Read config from environment
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
BQ_LOCATION = os.getenv("BIGQUERY_LOCATION", "asia-southeast2")

# Hardcoded list of allowed datasets (= companies)
ALLOWED_DATASETS = ["pis", "igr", "kingpack"]


class BQClient:
    """Wrapper around BigQuery client for table listing, stats, and column fetching."""

    def __init__(self):
        self._client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)

    def _dataset_ref(self, dataset: str) -> str:
        return f"{PROJECT_ID}.{dataset}"

    def list_tables(self, dataset: str) -> list[dict]:
        """List all tables in the given dataset."""
        ref = self._dataset_ref(dataset)
        tables = self._client.list_tables(ref)
        return [{"name": table.table_id} for table in tables]

    def fetch_all_rows(
        self, table_name: str, dataset: str, limit: int = 10000
    ) -> list[dict]:
        """
        Fetch ALL columns from a table, limited to `limit` rows.
        Returns data as list of dicts (records).
        """
        table_ref = f"{self._dataset_ref(dataset)}.{table_name}"
        query = f"SELECT * FROM `{table_ref}` LIMIT {limit}"
        result = self._client.query(query, location=BQ_LOCATION).result()
        return [dict(row) for row in result]

    def fetch_columns(
        self, table_name: str, columns: list[str], dataset: str, limit: int = 10000
    ) -> list[dict]:
        """
        Fetch specific columns from a table, limited to `limit` rows.
        Returns data as list of dicts (records).
        """
        table_ref = f"{self._dataset_ref(dataset)}.{table_name}"
        safe_cols = [f"`{col}`" for col in columns]
        cols_str = ", ".join(safe_cols)
        query = f"SELECT {cols_str} FROM `{table_ref}` LIMIT {limit}"
        result = self._client.query(query, location=BQ_LOCATION).result()
        return [dict(row) for row in result]


# Singleton instance
bq = BQClient()
