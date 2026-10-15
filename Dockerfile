# Airflow image + a separate virtualenv for dbt / Great Expectations / DuckDB.
# The two dependency sets conflict, so the DAG calls the pipeline venv by path.
FROM apache/airflow:2.10.3-python3.11

USER root
RUN python -m venv /opt/pipeline-venv && chown -R airflow: /opt/pipeline-venv
USER airflow

COPY requirements.txt /tmp/requirements.txt
RUN /opt/pipeline-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

ENV PROJECT_DIR=/opt/project \
    PIPELINE_PYTHON=/opt/pipeline-venv/bin/python \
    DBT_BIN=/opt/pipeline-venv/bin/dbt \
    DUCKDB_PATH=/opt/project/data/warehouse.duckdb \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false
