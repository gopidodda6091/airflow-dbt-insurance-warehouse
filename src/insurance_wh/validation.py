"""Raw-layer data-quality gate using the Great Expectations checkpoint in ``great_expectations/``.

Raw tables are all-text, so numeric and date columns are coerced before validation; a
value that cannot be parsed becomes null and fails the matching ``not_null`` expectation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from insurance_wh.settings import DUCKDB_PATH, GE_DIR, RAW_SCHEMA, RAW_TABLES

NUMERIC_COLUMNS = {
    "policies": ["annual_premium", "coverage_limit", "deductible"],
    "premium_transactions": ["written_premium"],
    "claim_payments": ["payment_amount"],
    "products": ["base_premium"],
}
DATE_COLUMNS = {
    "customers": ["date_of_birth"],
    "policies": ["effective_date", "expiration_date"],
    "premium_transactions": ["coverage_start", "coverage_end"],
    "claim_payments": ["loss_date", "payment_date"],
}


@dataclass(frozen=True)
class GateResult:
    success: bool
    failed: dict[str, list[str]]  # table -> failed expectation types
    docs_path: str

    def summary(self) -> str:
        if self.success:
            return "raw checkpoint passed"
        lines = [f"  {table}: {', '.join(exps)}" for table, exps in self.failed.items()]
        return "raw checkpoint FAILED\n" + "\n".join(lines)


def coerce_types(table: str, df: pd.DataFrame) -> pd.DataFrame:
    """Cast known numeric/date text columns so range and comparison checks are meaningful."""
    out = df.copy()
    for col in NUMERIC_COLUMNS.get(table, []):
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in DATE_COLUMNS.get(table, []):
        if col in out:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def read_extract(table: str, extract_date: str, db_path: Path = DUCKDB_PATH) -> pd.DataFrame:
    """Rows of one raw table for one extract, without the loader's audit columns."""
    with duckdb.connect(str(db_path), read_only=True) as con:
        exists = con.execute(
            "select count(*) from information_schema.tables "
            "where table_schema = ? and table_name = ?",
            [RAW_SCHEMA, table],
        ).fetchone()
        if not exists or exists[0] == 0:
            return pd.DataFrame()
        df = con.execute(
            f"select * exclude (_extract_date, _loaded_at) from {RAW_SCHEMA}.{table} "
            "where _extract_date = ?",
            [extract_date],
        ).df()
    return coerce_types(table, df)


def run_checkpoint(frames: dict[str, pd.DataFrame], ge_dir: Path = GE_DIR) -> GateResult:
    """Validate each DataFrame against ``raw_<table>`` with the ``raw_checkpoint``."""
    import great_expectations as gx

    context = gx.get_context(context_root_dir=str(ge_dir))
    datasource = context.get_datasource("raw_extracts")
    validations = [
        {
            "batch_request": datasource.get_asset(table).build_batch_request(dataframe=df),
            "expectation_suite_name": f"raw_{table}",
        }
        for table, df in frames.items()
    ]
    result = context.run_checkpoint(checkpoint_name="raw_checkpoint", validations=validations)
    failed: dict[str, list[str]] = {}
    for run in result.list_validation_results():
        suite = run.meta["expectation_suite_name"].removeprefix("raw_")
        bad = [r.expectation_config.expectation_type for r in run.results if not r.success]
        if bad:
            failed[suite] = bad
    docs = ge_dir / "uncommitted" / "data_docs" / "local_site" / "index.html"
    return GateResult(bool(result.success), failed, str(docs))


def validate_extract(
    extract_date: str, tables: tuple[str, ...] = RAW_TABLES, db_path: Path = DUCKDB_PATH
) -> GateResult:
    """Gate one loaded extract. Empty incremental tables are skipped."""
    frames = {t: read_extract(t, extract_date, db_path) for t in tables}
    non_empty = {t: df for t, df in frames.items() if not df.empty}
    if not non_empty:
        return GateResult(False, {"<extract>": [f"no rows loaded for {extract_date}"]}, "")
    return run_checkpoint(non_empty)
