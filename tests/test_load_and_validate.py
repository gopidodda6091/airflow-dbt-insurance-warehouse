"""Loader idempotency and the Great Expectations gate (needs the pipeline environment)."""

from __future__ import annotations

import pytest

duckdb = pytest.importorskip("duckdb", reason="pipeline deps not installed (requirements.txt)")
pytest.importorskip("great_expectations", reason="great_expectations not installed")

from generate_data import generate  # noqa: E402

from insurance_wh.loader import load_extract  # noqa: E402
from insurance_wh.validation import validate_extract  # noqa: E402


@pytest.fixture()
def extracts(tmp_path):
    raw = tmp_path / "raw"
    generate(raw, seed=5, n_customers=80, inject_bad=True)
    return raw, tmp_path / "wh.duckdb"


def test_reloading_an_extract_does_not_duplicate(extracts):
    raw, db = extracts
    first = load_extract("2026-02-01", db_path=db, raw_dir=raw)
    second = load_extract("2026-02-01", db_path=db, raw_dir=raw)
    assert first == second
    with duckdb.connect(str(db)) as con:
        total = con.execute("select count(*) from raw.policies").fetchone()[0]
    assert total == first["policies"]


def test_gate_passes_clean_extract_and_fails_bad_one(extracts):
    raw, db = extracts
    load_extract("2026-02-01", db_path=db, raw_dir=raw)
    load_extract("2026-05-01", db_path=db, raw_dir=raw)  # has injected bad rows

    clean = validate_extract("2026-02-01", db_path=db)
    assert clean.success, clean.summary()

    bad = validate_extract("2026-05-01", db_path=db)
    assert not bad.success
    assert "claim_payments" in bad.failed
    assert "expect_column_values_to_not_be_null" in bad.failed["claim_payments"]
    assert "expect_column_values_to_be_in_set" in bad.failed["claim_payments"]
