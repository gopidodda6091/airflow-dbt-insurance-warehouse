-- SCD2 integrity: versions of the same policy must not overlap in time.
select a.policy_id, a.policy_sk, b.policy_sk as overlapping_sk
from {{ ref('dim_policy') }} as a
inner join {{ ref('dim_policy') }} as b
    on a.policy_id = b.policy_id
    and a.policy_sk <> b.policy_sk
    and a.valid_from < coalesce(b.valid_to, cast('9999-12-31' as timestamp))
    and b.valid_from < coalesce(a.valid_to, cast('9999-12-31' as timestamp))
