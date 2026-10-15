with deduped as (
    {{ dedupe(source('raw', 'products'), 'product_code', '_extract_date desc') }}
)

select
    product_code,
    product_name,
    line_of_business,
    cast(base_premium as numeric(12, 2)) as base_premium,
    _extract_date as source_extract_date
from deduped
