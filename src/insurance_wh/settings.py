"""Locations shared by the loader, validation, report and the Airflow DAG."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[2]))
RAW_DIR = Path(os.environ.get("RAW_DIR", PROJECT_DIR / "data" / "raw"))
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", PROJECT_DIR / "data" / "warehouse.duckdb"))
DBT_DIR = PROJECT_DIR / "dbt"
GE_DIR = PROJECT_DIR / "great_expectations"
RAW_SCHEMA = os.environ.get("RAW_SCHEMA", "raw")

RAW_TABLES = ("customers", "products", "policies", "premium_transactions", "claim_payments")


def extract_dates(raw_dir: Path = RAW_DIR) -> list[str]:
    """Extract folders present on disk, oldest first (folder names are ISO dates)."""
    if not raw_dir.exists():
        return []
    return sorted(p.name for p in raw_dir.iterdir() if p.is_dir())
