-- One row per premium transaction. Earned premium is daily pro-rata over the coverage
-- period, measured as of the latest extract date.
with txn as (
    select * from {{ ref('stg_premium_transactions') }}
),

as_of as (
    select max(source_extract_date) as as_of_date from txn
),

policy as (
    select * from {{ ref('dim_policy') }}
),

joined as (
    select
        txn.*,
        policy.policy_sk,
        policy.customer_id,
        policy.product_code,
        {{ dbt.datediff('txn.coverage_start', 'txn.coverage_end', 'day') }} as coverage_days,
        {{ dbt.datediff('txn.coverage_start', 'as_of.as_of_date', 'day') }} as days_elapsed
    from txn
    cross join as_of
    left join policy
        on txn.policy_id = policy.policy_id
        and cast(txn.transaction_date as timestamp) >= policy.valid_from
        and cast(txn.transaction_date as timestamp)
            < coalesce(policy.valid_to, cast('9999-12-31' as timestamp))
)

select
    {{ surrogate_key(['joined.transaction_id']) }} as premium_sk,
    joined.transaction_id,
    joined.transaction_type,
    joined.policy_sk,
    customer.customer_sk,
    product.product_sk,
    {{ date_key('joined.transaction_date') }} as transaction_date_key,
    joined.coverage_start,
    joined.coverage_end,
    joined.coverage_days,
    joined.written_premium,
    joined.written_premium / nullif(joined.coverage_days, 0) as daily_earned_premium,
    round(
        joined.written_premium
        * least(greatest(joined.days_elapsed, 0), joined.coverage_days)
        / nullif(joined.coverage_days, 0),
        2
    ) as earned_premium
from joined
left join {{ ref('dim_customer') }} as customer on joined.customer_id = customer.customer_id
left join {{ ref('dim_product') }} as product on joined.product_code = product.product_code
