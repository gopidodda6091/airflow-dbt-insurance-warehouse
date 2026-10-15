-- One row per policy version (SCD2) from the snap_policy snapshot.
-- The first version is extended back to the policy's effective date, so every
-- transaction and loss inside the policy term finds the version in force.
with versions as (
    select
        *,
        row_number() over (partition by policy_id order by dbt_valid_from) as version_number
    from {{ ref('snap_policy') }}
)

select
    dbt_scd_id as policy_sk,
    policy_id,
    version_number,
    customer_id,
    product_code,
    state,
    effective_date,
    expiration_date,
    annual_premium,
    coverage_limit,
    deductible,
    status,
    case
        when version_number = 1 then cast(effective_date as timestamp)
        else dbt_valid_from
    end as valid_from,
    dbt_valid_to as valid_to,
    dbt_valid_to is null as is_current
from versions
