-- Current version of each policy (latest updated_at, then latest extract). Feeds the
-- snap_policy snapshot, which turns successive versions into SCD2 history.
with deduped as (
    {{ dedupe(source('raw', 'policies'), 'policy_id', 'updated_at desc, _extract_date desc') }}
)

select
    policy_id,
    customer_id,
    product_code,
    upper(state) as state,
    cast(effective_date as date) as effective_date,
    cast(expiration_date as date) as expiration_date,
    cast(annual_premium as numeric(12, 2)) as annual_premium,
    cast(coverage_limit as integer) as coverage_limit,
    cast(deductible as integer) as deductible,
    status,
    cast(updated_at as timestamp) as updated_at,
    _extract_date as source_extract_date
from deduped
