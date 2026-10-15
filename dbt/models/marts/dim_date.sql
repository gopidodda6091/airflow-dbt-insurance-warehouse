with spine as (
    {{ dbt.date_spine(
        'day',
        "cast('" ~ var('date_spine_start') ~ "' as date)",
        "cast('" ~ var('date_spine_end') ~ "' as date)"
    ) }}
),

days as (
    select cast(date_day as date) as date_day from spine
)

select
    {{ date_key('date_day') }} as date_key,
    date_day,
    cast({{ dbt.date_trunc('month', 'date_day') }} as date) as month_start,
    cast(extract(year from date_day) as integer) as year_number,
    cast(extract(quarter from date_day) as integer) as quarter_number,
    cast(extract(month from date_day) as integer) as month_number,
    cast(extract(day from date_day) as integer) as day_of_month,
    date_day = cast({{ dbt.last_day('date_day', 'month') }} as date) as is_month_end
from days
