"""Synthetic source extracts for Lone Star Mutual (a fictional P&C insurer).

Writes one folder per monthly extract, e.g. ``data/raw/2026-02-01/policies.csv``.
Each extract looks like what an operational policy system would hand over:

- customers, products, policies : full snapshot as of the extract date
  (policies show their *current* version, so mid-term endorsements appear over time)
- premium_transactions, claim_payments : incremental since the previous extract

Deliberate defects the warehouse must handle:
- duplicates        : ~2% of rows repeated verbatim inside an extract
- late corrections  : ~4% of premium transactions and claim payments from the previous
                      extract are restated in the next one with a new amount/updated_at
- ``--inject-bad``  : adds invalid rows (null ids, negative payments, unknown product) so
                      the Great Expectations gate can be seen failing

All names are drawn from small generic lists; no real people or companies.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path

STATES = ["TX", "OK", "LA", "NM", "AR"]
PRODUCTS = [
    # code, name, line of business, base annual premium
    ("AUTO-STD", "Auto Standard", "Personal Auto", 1_350),
    ("AUTO-PRM", "Auto Premier", "Personal Auto", 1_900),
    ("HO-STD", "Homeowners Standard", "Homeowners", 1_700),
    ("HO-PLUS", "Homeowners Plus", "Homeowners", 2_400),
    ("CP-SMB", "Small Business Property", "Commercial Property", 4_800),
]
FIRST = ["Avery", "Blake", "Casey", "Drew", "Emery", "Finley", "Harper", "Jordan", "Kai", "Logan"]
LAST = ["Alder", "Birch", "Cedar", "Dale", "Elm", "Field", "Glen", "Hill", "Lake", "Moss"]
CITIES = ["Riverbend", "Oak Hollow", "Mesa Verde", "Pine Ridge", "Cottonwood"]
EXTRACT_DATES = [date(2026, m, 1) for m in (2, 3, 4, 5)]


@dataclass
class PolicyVersion:
    policy_id: str
    customer_id: str
    product_code: str
    state: str
    effective_date: date
    expiration_date: date
    annual_premium: float
    coverage_limit: int
    deductible: int
    status: str
    updated_at: date


@dataclass
class Policy:
    versions: list[PolicyVersion] = field(default_factory=list)

    def as_of(self, day: date) -> PolicyVersion | None:
        """The version a full extract taken on ``day`` would show."""
        seen = [v for v in self.versions if v.updated_at < day]
        return seen[-1] if seen else None


def build_customers(rng: random.Random, n: int) -> list[dict]:
    return [
        {
            "customer_id": f"C{100000 + i}",
            "first_name": rng.choice(FIRST),
            "last_name": rng.choice(LAST),
            "date_of_birth": date(1950, 1, 1) + timedelta(days=rng.randint(0, 18_000)),
            "city": rng.choice(CITIES),
            "state": rng.choice(STATES),
            "created_at": date(2025, 6, 1),
        }
        for i in range(n)
    ]


def build_policy(rng: random.Random, i: int, customer: dict) -> Policy:
    """New business, then maybe an endorsement, then maybe a cancellation."""
    code, _, _, base = rng.choice(PRODUCTS)
    eff = date(2025, 7, 1) + timedelta(days=rng.randint(0, 270))
    v = PolicyVersion(
        policy_id=f"P{200000 + i}",
        customer_id=customer["customer_id"],
        product_code=code,
        state=customer["state"],
        effective_date=eff,
        expiration_date=eff + timedelta(days=365),
        annual_premium=round(base * rng.uniform(0.8, 1.3), 2),
        coverage_limit=rng.choice([100_000, 250_000, 500_000]),
        deductible=rng.choice([500, 1_000, 2_500]),
        status="ACTIVE",
        updated_at=eff,
    )
    policy = Policy([v])
    if rng.random() < 0.30:
        endo = eff + timedelta(days=rng.randint(20, 200))
        v = replace(
            v,
            annual_premium=round(v.annual_premium * rng.uniform(1.05, 1.25), 2),
            coverage_limit=v.coverage_limit * 2,
            updated_at=endo,
        )
        policy.versions.append(v)
    if rng.random() < 0.08:
        cancel = v.updated_at + timedelta(days=rng.randint(15, 120))
        policy.versions.append(replace(v, status="CANCELLED", updated_at=cancel))
    return policy


def premium_transactions(policy: Policy) -> list[dict]:
    """Written premium per version change, each with the coverage period it earns over."""
    rows: list[dict] = []
    prev: PolicyVersion | None = None
    for n, v in enumerate(policy.versions, start=1):
        start, end = v.updated_at, v.expiration_date
        remaining = (end - start).days / 365
        if prev is None:
            ttype, written = "NEW", v.annual_premium
        elif v.status == "CANCELLED":
            ttype, written = "CANCELLATION", -prev.annual_premium * remaining
        else:
            ttype, written = "ENDORSEMENT", (v.annual_premium - prev.annual_premium) * remaining
        rows.append(
            {
                "transaction_id": f"T{v.policy_id[1:]}-{n}",
                "policy_id": v.policy_id,
                "transaction_type": ttype,
                "transaction_date": start,
                "coverage_start": start,
                "coverage_end": end,
                "written_premium": round(written, 2),
                "updated_at": start,
            }
        )
        prev = v
    return rows


def claim_payments(rng: random.Random, policy: Policy, n: int) -> list[dict]:
    """~25% of policies have a claim with 1-3 payments after it is reported."""
    if rng.random() > 0.25:
        return []
    first = policy.versions[0]
    loss = first.effective_date + timedelta(days=rng.randint(1, 300))
    reported = loss + timedelta(days=rng.randint(0, 20))
    total = rng.lognormvariate(8.4, 0.9)
    parts = rng.randint(1, 3)
    return [
        {
            "payment_id": f"PAY{n:05d}-{k}",
            "claim_id": f"CLM{n:05d}",
            "policy_id": first.policy_id,
            "loss_date": loss,
            "reported_date": reported,
            "payment_date": reported + timedelta(days=15 * k + rng.randint(0, 10)),
            "payment_amount": round(total / parts, 2),
            "claim_status": "CLOSED" if k == parts else "OPEN",
            "updated_at": reported + timedelta(days=15 * k),
        }
        for k in range(1, parts + 1)
    ]


def corrections(rng: random.Random, rows: list[dict], amount_col: str, day: date) -> list[dict]:
    """Restate a few earlier rows: same id, new amount, newer updated_at."""
    picked = [r for r in rows if rng.random() < 0.04]
    return [
        {**r, amount_col: round(r[amount_col] * rng.uniform(0.85, 1.15), 2), "updated_at": day}
        for r in picked
    ]


def with_duplicates(rng: random.Random, rows: list[dict], rate: float = 0.02) -> list[dict]:
    out = list(rows)
    out += [dict(r) for r in rows if rng.random() < rate]
    rng.shuffle(out)
    return out


def bad_rows() -> dict[str, list[dict]]:
    """Rows that must trip the raw-layer expectations."""
    return {
        "claim_payments": [
            {"payment_id": None, "claim_id": "CLM-BAD", "policy_id": "P200000",
             "loss_date": date(2026, 1, 5), "reported_date": date(2026, 1, 6),
             "payment_date": date(2026, 1, 20), "payment_amount": -500.0,
             "claim_status": "UNKNOWN", "updated_at": date(2026, 1, 20)},
        ],
    }  # fmt: skip


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(
    out: Path, seed: int = 7, n_customers: int = 400, inject_bad: bool = False
) -> list[date]:
    """Write all extracts; returns the extract dates."""
    rng = random.Random(seed)
    customers = build_customers(rng, n_customers)
    policies = [build_policy(rng, i, rng.choice(customers)) for i in range(int(n_customers * 1.5))]
    all_txns = [t for p in policies for t in premium_transactions(p)]
    all_pays = [x for n, p in enumerate(policies) for x in claim_payments(rng, p, n)]
    products = [
        {"product_code": c, "product_name": n, "line_of_business": lob, "base_premium": b}
        for c, n, lob, b in PRODUCTS
    ]

    previous = date(2025, 1, 1)
    prev_txns: list[dict] = []
    prev_pays: list[dict] = []
    for day in EXTRACT_DATES:
        folder = out / day.isoformat()
        current = [v for v in (p.as_of(day) for p in policies) if v is not None]
        txns = [t for t in all_txns if previous <= t["transaction_date"] < day]
        pays = [x for x in all_pays if previous <= x["payment_date"] < day]
        txns += corrections(rng, prev_txns, "written_premium", day - timedelta(days=2))
        pays += corrections(rng, prev_pays, "payment_amount", day - timedelta(days=2))
        tables = {
            "customers": with_duplicates(rng, customers),
            "products": products,
            "policies": with_duplicates(rng, [asdict(v) for v in current]),
            "premium_transactions": with_duplicates(rng, txns),
            "claim_payments": with_duplicates(rng, pays),
        }
        if inject_bad and day == EXTRACT_DATES[-1]:
            for name, rows in bad_rows().items():
                tables[name] = tables[name] + rows
        for name, rows in tables.items():
            write_csv(folder / f"{name}.csv", rows)
        previous, prev_txns, prev_pays = day, txns, pays
    return EXTRACT_DATES


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Lone Star Mutual source extracts")
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--customers", type=int, default=400)
    parser.add_argument("--inject-bad", action="store_true", help="add rows that fail GE")
    args = parser.parse_args()
    dates = generate(args.out, args.seed, args.customers, args.inject_bad)
    print(f"wrote {len(dates)} extracts to {args.out}: {', '.join(d.isoformat() for d in dates)}")


if __name__ == "__main__":
    main()
