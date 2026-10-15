"""Test settings. Airflow is pointed at a throwaway home so tests never touch ~/airflow."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("AIRFLOW_HOME", tempfile.mkdtemp(prefix="airflow-home-"))
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")

REPO = Path(__file__).resolve().parents[1]
DAGS_DIR = REPO / "dags"
