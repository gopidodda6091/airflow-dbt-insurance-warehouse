-- The report spreads premium over dim_date; its total must equal the fact's
-- earned-to-date total (catches join fan-out or dropped rows). Tolerance covers rounding.
with report as (
    select sum(earned_premium) as total from {{ ref('loss_ratio_monthly') }}
),

fact as (
    select sum(earned_premium) as total from {{ ref('fact_premium') }}
)

select report.total as report_total, fact.total as fact_total
from report
cross join fact
where abs(report.total - fact.total) > 5
