-- One row per premium transaction. A late correction (same transaction_id, newer
-- updated_at, later extract) replaces the original; exact duplicates collapse.
with deduped as (
    {{ dedupe(source('raw', 'premium_transactions'), 'transaction_id', 'updated_at desc, _extract_date desc') }}
)

select
    transaction_id,
    policy_id,
    transaction_type,
    cast(transaction_date as date) as transaction_date,
    cast(coverage_start as date) as coverage_start,
    cast(coverage_end as date) as coverage_end,
    cast(written_premium as numeric(12, 2)) as written_premium,
    cast(updated_at as timestamp) as updated_at,
    _extract_date as source_extract_date
from deduped
