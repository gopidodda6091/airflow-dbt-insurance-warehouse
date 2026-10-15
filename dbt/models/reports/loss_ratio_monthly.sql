-- Accident-month loss ratio by line of business and policy state:
-- paid losses by loss month / premium earned in that month (daily pro-rata).
with as_of as (
    select max(source_extract_date) as as_of_date from {{ ref('stg_premium_transactions') }}
),

policy as (
    select p.policy_sk, p.state, pr.line_of_business
    from {{ ref('dim_policy') }} as p
    inner join {{ ref('dim_product') }} as pr on p.product_code = pr.product_code
),

earned as (
    select
        d.month_start,
        policy.line_of_business,
        policy.state,
        sum(f.daily_earned_premium) as earned_premium,
        0 as written_premium,
        0 as paid_losses
    from {{ ref('fact_premium') }} as f
    inner join policy on f.policy_sk = policy.policy_sk
    inner join {{ ref('dim_date') }} as d
        on d.date_day >= f.coverage_start
        and d.date_day < f.coverage_end
    cross join as_of
    where d.date_day < as_of.as_of_date
    group by 1, 2, 3
),

written as (
    select
        d.month_start,
        policy.line_of_business,
        policy.state,
        0 as earned_premium,
        sum(f.written_premium) as written_premium,
        0 as paid_losses
    from {{ ref('fact_premium') }} as f
    inner join policy on f.policy_sk = policy.policy_sk
    inner join {{ ref('dim_date') }} as d on f.transaction_date_key = d.date_key
    group by 1, 2, 3
),

losses as (
    select
        d.month_start,
        policy.line_of_business,
        policy.state,
        0 as earned_premium,
        0 as written_premium,
        sum(c.paid_amount) as paid_losses
    from {{ ref('fact_claim') }} as c
    inner join policy on c.policy_sk = policy.policy_sk
    inner join {{ ref('dim_date') }} as d on c.loss_date_key = d.date_key
    group by 1, 2, 3
),

combined as (
    select * from earned
    union all
    select * from written
    union all
    select * from losses
)

select
    month_start,
    line_of_business,
    state,
    round(sum(written_premium), 2) as written_premium,
    round(sum(earned_premium), 2) as earned_premium,
    round(sum(paid_losses), 2) as paid_losses,
    round(sum(paid_losses) / nullif(sum(earned_premium), 0), 4) as loss_ratio
from combined
group by 1, 2, 3
