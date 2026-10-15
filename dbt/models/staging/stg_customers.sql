-- One row per customer: the latest extract wins (also removes in-extract duplicates).
with deduped as (
    {{ dedupe(source('raw', 'customers'), 'customer_id', '_extract_date desc') }}
)

select
    customer_id,
    trim(first_name) as first_name,
    trim(last_name) as last_name,
    cast(date_of_birth as date) as date_of_birth,
    trim(city) as city,
    upper(trim(state)) as state,
    cast(created_at as date) as created_at,
    _extract_date as source_extract_date
from deduped
