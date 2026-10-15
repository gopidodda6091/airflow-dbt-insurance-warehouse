import csv
from collections import Counter

from generate_data import generate


def _rows(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_extracts_contain_duplicates_and_late_corrections(tmp_path):
    dates = generate(tmp_path, seed=3, n_customers=300)
    assert len(dates) == 4

    first = _rows(tmp_path / dates[0].isoformat() / "policies.csv")
    counts = Counter(tuple(r.values()) for r in first)
    assert any(n > 1 for n in counts.values()), "expected verbatim duplicate rows"

    seen: dict[str, str] = {}
    corrected = 0
    for day in dates:
        for row in _rows(tmp_path / day.isoformat() / "premium_transactions.csv"):
            tid, amount = row["transaction_id"], row["written_premium"]
            if tid in seen and seen[tid] != amount:
                corrected += 1
            seen[tid] = amount
    assert corrected > 0, "expected late corrections restated in a later extract"


def test_generator_is_deterministic(tmp_path):
    generate(tmp_path / "a", seed=11, n_customers=50)
    generate(tmp_path / "b", seed=11, n_customers=50)
    a = (tmp_path / "a" / "2026-03-01" / "policies.csv").read_text()
    b = (tmp_path / "b" / "2026-03-01" / "policies.csv").read_text()
    assert a == b
