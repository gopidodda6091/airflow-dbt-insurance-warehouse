"""Load one extract's CSV files into the DuckDB ``raw`` schema.

Raw tables keep every column as text plus ``_extract_date`` and ``_loaded_at``; typing
and deduplication happen in dbt staging. Re-loading an extract first deletes its rows,
so a retried Airflow task never double-loads.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from insurance_wh.settings import DUCKDB_PATH, RAW_DIR, RAW_SCHEMA, RAW_TABLES


def _csv_relation(csv_path: Path, extract_date: str) -> str:
    return (
        f"select *, cast('{extract_date}' as date) as _extract_date, "
        f"current_timestamp as _loaded_at "
        f"from read_csv('{csv_path.as_posix()}', header = true, all_varchar = true)"
    )


def load_table(
    con: duckdb.DuckDBPyConnection, table: str, extract_date: str, raw_dir: Path = RAW_DIR
) -> int:
    """Idempotently load ``<raw_dir>/<extract_date>/<table>.csv``; returns rows loaded."""
    csv_path = raw_dir / extract_date / f"{table}.csv"
    if not csv_path.exists():
        return 0
    target = f"{RAW_SCHEMA}.{table}"
    relation = _csv_relation(csv_path, extract_date)
    con.execute(f"create schema if not exists {RAW_SCHEMA}")
    con.execute(f"create table if not exists {target} as {relation} limit 0")
    con.execute(f"delete from {target} where _extract_date = ?", [extract_date])
    con.execute(f"insert into {target} by name {relation}")
    result = con.execute(
        f"select count(*) from {target} where _extract_date = ?", [extract_date]
    ).fetchone()
    return int(result[0]) if result else 0


def load_extract(
    extract_date: str,
    tables: tuple[str, ...] = RAW_TABLES,
    db_path: Path = DUCKDB_PATH,
    raw_dir: Path = RAW_DIR,
) -> dict[str, int]:
    """Load several tables of one extract in a single transaction."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path)) as con:
        con.execute("begin transaction")
        counts = {t: load_table(con, t, extract_date, raw_dir) for t in tables}
        con.execute("commit")
    return counts
