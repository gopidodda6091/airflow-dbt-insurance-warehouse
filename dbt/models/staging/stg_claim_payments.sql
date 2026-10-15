-- One row per claim payment; late corrections replace the original amount.
with deduped as (
    {{ dedupe(source('raw', 'claim_payments'), 'payment_id', 'updated_at desc, _extract_date desc') }}
)

select
    payment_id,
    claim_id,
    policy_id,
    cast(loss_date as date) as loss_date,
    cast(reported_date as date) as reported_date,
    cast(payment_date as date) as payment_date,
    cast(payment_amount as numeric(12, 2)) as payment_amount,
    claim_status,
    cast(updated_at as timestamp) as updated_at,
    _extract_date as source_extract_date
from deduped
