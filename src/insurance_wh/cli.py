"""Command line used by the Airflow tasks, the Makefile and CI.

python -m insurance_wh.cli load     --extract-date 2026-02-01 [--table policies]
python -m insurance_wh.cli validate --extract-date 2026-02-01
python -m insurance_wh.cli report
python -m insurance_wh.cli run-all          # every extract, same steps as the DAG
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import duckdb

from insurance_wh.loader import load_extract
from insurance_wh.settings import DBT_DIR, DUCKDB_PATH, RAW_TABLES, extract_dates
from insurance_wh.validation import validate_extract

DBT_STEPS = (
    ["build", "--select", "staging"],
    ["snapshot"],
    ["build", "--select", "marts", "--indirect-selection", "cautious"],
    ["build", "--select", "reports"],
)


def cmd_load(extract_date: str, tables: tuple[str, ...]) -> int:
    counts = load_extract(extract_date, tables)
    for table, rows in counts.items():
        print(f"loaded {rows:>6} rows into raw.{table} ({extract_date})")
    return 0


def cmd_validate(extract_date: str) -> int:
    result = validate_extract(extract_date)
    print(result.summary())
    print(f"data docs: {result.docs_path}")
    return 0 if result.success else 1


def dbt(args: list[str]) -> None:
    """Run a dbt command against the project; raises on failure."""
    dbt_bin = os.environ.get("DBT_BIN", str(Path(sys.executable).with_name("dbt")))
    target = os.environ.get("DBT_TARGET", "duckdb")
    cmd = [dbt_bin, *args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    subprocess.run([*cmd, "--target", target], check=True)


def fetch_report(limit: int = 24) -> list[tuple]:
    query = """
        select month_start, line_of_business, state, earned_premium, paid_losses, loss_ratio
        from reports.loss_ratio_monthly
        order by month_start desc, line_of_business, state
        limit ?
    """
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
        return con.execute(query, [limit]).fetchall()


def cmd_report(limit: int) -> int:
    header = (
        f"{'month':<10} {'line of business':<20} {'st':<3} "
        f"{'earned':>11} {'paid':>11} {'LR':>6}"
    )
    print(header)
    print("-" * len(header))
    for month, lob, state, earned, paid, ratio in fetch_report(limit):
        lr = f"{ratio:.1%}" if ratio is not None else "n/a"
        print(f"{month!s:<10} {lob:<20} {state:<3} {earned:>11,.2f} {paid:>11,.2f} {lr:>6}")
    return 0


def cmd_run_all() -> int:
    """Replay every extract in order: load -> validate -> dbt (staging, snapshot, marts)."""
    dbt(["deps"])
    for extract_date in extract_dates():
        print(f"=== extract {extract_date} ===")
        cmd_load(extract_date, RAW_TABLES)
        if cmd_validate(extract_date) != 0:
            print("stopping: data-quality gate failed")
            return 1
        for step in DBT_STEPS:
            dbt(step)
    return cmd_report(limit=24)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lone Star Mutual warehouse pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    load = sub.add_parser("load")
    load.add_argument("--extract-date", required=True)
    load.add_argument("--table", action="append", choices=RAW_TABLES)
    val = sub.add_parser("validate")
    val.add_argument("--extract-date", required=True)
    rep = sub.add_parser("report")
    rep.add_argument("--limit", type=int, default=24)
    sub.add_parser("run-all")
    args = parser.parse_args(argv)

    if args.command == "load":
        return cmd_load(args.extract_date, tuple(args.table or RAW_TABLES))
    if args.command == "validate":
        return cmd_validate(args.extract_date)
    if args.command == "report":
        return cmd_report(args.limit)
    return cmd_run_all()


if __name__ == "__main__":
    raise SystemExit(main())
