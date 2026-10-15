"""Lone Star Mutual warehouse: load -> validate -> dbt build -> report.

One run per monthly extract: the run with logical date 2026-02-01 loads
``data/raw/2026-02-01``. Trigger with ``{"extract_date": "YYYY-MM-DD"}`` to reload a
specific extract (all steps are idempotent).

Airflow only orchestrates. Loading, validation and dbt run in a separate Python
environment (``PIPELINE_PYTHON`` / ``DBT_BIN``) because Airflow's and dbt's pinned
dependencies conflict when installed together.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule

PROJECT_DIR = os.environ.get("PROJECT_DIR", "/opt/project")
PIPELINE_PYTHON = os.environ.get("PIPELINE_PYTHON", "python")
DBT_BIN = os.environ.get("DBT_BIN", "dbt")
DBT_TARGET = os.environ.get("DBT_TARGET", "duckdb")
RAW_TABLES = ("customers", "products", "policies", "premium_transactions", "claim_payments")
EXTRACT_DATE = "{{ params.extract_date or ds }}"

CLI = f"cd {PROJECT_DIR} && PYTHONPATH=src {PIPELINE_PYTHON} -m insurance_wh.cli"
DBT = (
    f"cd {PROJECT_DIR} && {DBT_BIN} {{cmd}} --project-dir dbt --profiles-dir dbt "
    f"--target {DBT_TARGET}"
)

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
    "sla": timedelta(hours=2),
}

with DAG(
    dag_id="insurance_warehouse",
    description="Raw extracts -> GE gate -> dbt star schema -> loss ratio report",
    schedule="@monthly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,  # DuckDB allows one writer at a time
    default_args=default_args,
    params={"extract_date": None},
    tags=["insurance", "dbt", "great-expectations"],
    doc_md=__doc__,
) as dag:
    start = EmptyOperator(task_id="start")

    with TaskGroup("load", tooltip="CSV extract -> raw schema (idempotent per extract)") as load:
        for table in RAW_TABLES:
            BashOperator(
                task_id=f"load_{table}",
                bash_command=f"{CLI} load --extract-date {EXTRACT_DATE} --table {table}",
            )

    with TaskGroup("validate", tooltip="Great Expectations raw checkpoint") as validate:
        ge_checkpoint = BashOperator(
            task_id="ge_raw_checkpoint",
            bash_command=f"{CLI} validate --extract-date {EXTRACT_DATE}",
            retries=0,  # a failed expectation will not fix itself on retry
        )

    with TaskGroup("dbt_build", tooltip="staging -> snapshot -> marts + tests") as dbt_build:
        staging = BashOperator(
            task_id="build_staging", bash_command=DBT.format(cmd="build --select staging")
        )
        snapshot = BashOperator(
            task_id="snapshot_dim_policy", bash_command=DBT.format(cmd="snapshot")
        )
        marts = BashOperator(
            task_id="build_marts",
            bash_command=DBT.format(cmd="build --select marts --indirect-selection cautious"),
        )
        staging >> snapshot >> marts

    with TaskGroup("report", tooltip="gold report + failure report") as report:
        loss_ratio = BashOperator(
            task_id="build_loss_ratio_monthly",
            bash_command=DBT.format(cmd="build --select reports") + f" && {CLI} report",
        )
        quality_failure_report = BashOperator(
            task_id="quality_failure_report",
            bash_command=(
                f"echo 'Data-quality gate failed for extract {EXTRACT_DATE}; "
                f"see {PROJECT_DIR}/great_expectations/uncommitted/data_docs/local_site/index.html'"
                " && exit 1"
            ),
            trigger_rule=TriggerRule.ONE_FAILED,
            retries=0,
        )

    start >> load >> validate >> dbt_build >> loss_ratio
    ge_checkpoint >> quality_failure_report
