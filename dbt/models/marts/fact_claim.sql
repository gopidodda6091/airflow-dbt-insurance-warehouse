-- One row per claim payment, joined to the policy version in force on the loss date.
with payments as (
    select * from {{ ref('stg_claim_payments') }}
),

joined as (
    select
        payments.*,
        policy.policy_sk,
        policy.customer_id,
        policy.product_code
    from payments
    left join {{ ref('dim_policy') }} as policy
        on payments.policy_id = policy.policy_id
        and cast(payments.loss_date as timestamp) >= policy.valid_from
        and cast(payments.loss_date as timestamp)
            < coalesce(policy.valid_to, cast('9999-12-31' as timestamp))
)

select
    {{ surrogate_key(['joined.payment_id']) }} as claim_payment_sk,
    joined.payment_id,
    joined.claim_id,
    joined.policy_sk,
    customer.customer_sk,
    product.product_sk,
    {{ date_key('joined.loss_date') }} as loss_date_key,
    {{ date_key('joined.payment_date') }} as payment_date_key,
    joined.reported_date,
    joined.claim_status,
    joined.payment_amount as paid_amount
from joined
left join {{ ref('dim_customer') }} as customer on joined.customer_id = customer.customer_id
left join {{ ref('dim_product') }} as product on joined.product_code = product.product_code
