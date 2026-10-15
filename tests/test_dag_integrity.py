"""DAG integrity.

The AST checks always run (no Airflow needed). The DagBag checks need Airflow and are
skipped with a clear reason when it is not installed; CI runs them in a separate job
because Airflow's and dbt's pinned dependencies cannot share one environment.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

DAG_FILE = Path(__file__).resolve().parents[1] / "dags" / "insurance_warehouse.py"
EXPECTED_GROUPS = ["load", "validate", "dbt_build", "report"]
HEAVY_IMPORTS = {"dbt", "great_expectations", "duckdb", "pandas"}
AIRFLOW_MISSING = importlib.util.find_spec("airflow") is None


def _tree() -> ast.Module:
    return ast.parse(DAG_FILE.read_text(encoding="utf-8"), filename=str(DAG_FILE))


def test_dag_file_is_valid_python():
    assert isinstance(_tree(), ast.Module)


def test_dag_declares_task_groups_in_order():
    groups = [
        node.args[0].value
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "TaskGroup"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    assert groups == EXPECTED_GROUPS


def test_dag_has_no_heavy_top_level_imports():
    """The scheduler parses this file often; dbt/GE/duckdb must not be imported here."""
    imported = set()
    for node in _tree().body:
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & HEAVY_IMPORTS


@pytest.fixture(scope="module")
def dagbag():
    if AIRFLOW_MISSING:
        pytest.skip("apache-airflow not installed here; install requirements-airflow.txt")
    from airflow.models import DagBag

    return DagBag(dag_folder=str(DAG_FILE.parent), include_examples=False)


def test_dagbag_imports_without_errors(dagbag):
    assert dagbag.import_errors == {}
    assert "insurance_warehouse" in dagbag.dags


def test_dag_structure(dagbag):
    from airflow.utils.dag_cycle_tester import check_cycle

    dag = dagbag.dags["insurance_warehouse"]
    check_cycle(dag)
    ids = set(dag.task_ids)
    assert {
        "load.load_policies",
        "validate.ge_raw_checkpoint",
        "dbt_build.snapshot_dim_policy",
        "report.build_loss_ratio_monthly",
        "report.quality_failure_report",
    } <= ids

    gate = dag.get_task("validate.ge_raw_checkpoint")
    assert all(t.startswith("load.") for t in gate.upstream_task_ids)
    assert "dbt_build.build_staging" in gate.downstream_task_ids
    assert dag.get_task("dbt_build.snapshot_dim_policy").upstream_task_ids == {
        "dbt_build.build_staging"
    }
    assert dag.get_task("report.quality_failure_report").trigger_rule == "one_failed"


def test_default_args_have_retries_and_sla(dagbag):
    dag = dagbag.dags["insurance_warehouse"]
    for task in dag.tasks:
        if task.task_id in {"validate.ge_raw_checkpoint", "report.quality_failure_report"}:
            assert task.retries == 0
        else:
            assert task.retries >= 1
        assert task.sla is not None
