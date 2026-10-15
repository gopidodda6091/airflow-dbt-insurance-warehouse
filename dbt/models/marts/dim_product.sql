select
    {{ surrogate_key(['product_code']) }} as product_sk,
    product_code,
    product_name,
    line_of_business,
    base_premium
from {{ ref('stg_products') }}
