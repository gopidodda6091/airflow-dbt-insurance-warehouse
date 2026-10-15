SHELL := /bin/bash
PYTHON ?= python3.11
VENV ?= .venv
AF_VENV ?= .venv-airflow
BIN := $(VENV)/bin
AF_BIN := $(AF_VENV)/bin
COMPOSE ?= docker compose
AIRFLOW_CONSTRAINTS ?= https://raw.githubusercontent.com/apache/airflow/constraints-2.10.3/constraints-3.11.txt
EXTRACTS := 2026-02-01 2026-03-01 2026-04-01 2026-05-01
export DBT_SEND_ANONYMOUS_USAGE_STATS=false

.PHONY: help up down demo demo-local generate dbt-build test test-dbt test-py test-dag lint format install install-airflow clean

help: ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

up: ## Airflow standalone (UI on :8080) with the pipeline venv, DuckDB file under ./data
	$(COMPOSE) up -d --build --wait

down: ## stop containers
	$(COMPOSE) down

demo: ## generate data, run the DAG once per extract (inside the container), print the report
	$(COMPOSE) exec airflow /opt/pipeline-venv/bin/python scripts/generate_data.py --out data/raw
	for d in $(EXTRACTS); do \
		$(COMPOSE) exec airflow airflow dags test insurance_warehouse $$d || exit 1; \
	done
	$(COMPOSE) exec airflow bash -c 'cd /opt/project && PYTHONPATH=src /opt/pipeline-venv/bin/python -m insurance_wh.cli report'

$(BIN)/dbt:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r requirements.txt -r requirements-dev.txt

install: $(BIN)/dbt ## pipeline venv (dbt, GE, DuckDB, pytest, ruff)

$(AF_BIN)/airflow:
	$(PYTHON) -m venv $(AF_VENV)
	$(AF_BIN)/pip install -q --upgrade pip
	$(AF_BIN)/pip install -q -r requirements-airflow.txt -c $(AIRFLOW_CONSTRAINTS)
	$(AF_BIN)/pip install -q -r requirements-dev.txt

install-airflow: $(AF_BIN)/airflow ## separate Airflow venv (official constraints)

generate: install ## write synthetic extracts to data/raw
	rm -rf data/raw && $(BIN)/python scripts/generate_data.py --out data/raw

demo-local: generate ## no Docker: same steps as the DAG for every extract, then the report
	rm -f data/warehouse.duckdb
	PYTHONPATH=src $(BIN)/python -m insurance_wh.cli run-all

dbt-build: install ## dbt build (models + tests) on the existing DuckDB file
	$(BIN)/dbt build --project-dir dbt --profiles-dir dbt --target duckdb

test-dbt: demo-local ## load + GE + snapshot + dbt build across all extracts

test-py: install ## pytest (DAG AST checks, generator, loader, GE gate)
	$(BIN)/pytest

test-dag: install-airflow ## DAG integrity with Airflow's DagBag
	$(AF_BIN)/pytest tests/test_dag_integrity.py

test: test-dbt test-py test-dag ## dbt build (models + tests) and pytest for DAG integrity

lint: install ## ruff lint + format check
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format: install
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

clean: ## remove generated data, dbt artifacts and caches
	rm -rf data dbt/target dbt/logs dbt/dbt_packages logs great_expectations/uncommitted
	rm -rf .pytest_cache .ruff_cache great_expectations/expectations/.ge_store_backend_id
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
