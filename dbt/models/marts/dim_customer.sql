-- Type 1 customer dimension (current attributes only).
select
    {{ surrogate_key(['customer_id']) }} as customer_sk,
    customer_id,
    first_name,
    last_name,
    first_name || ' ' || last_name as full_name,
    date_of_birth,
    city,
    state
from {{ ref('stg_customers') }}
