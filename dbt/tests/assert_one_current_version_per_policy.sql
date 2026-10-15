select policy_id, count(*) as current_versions
from {{ ref('dim_policy') }}
where is_current
group by policy_id
having count(*) <> 1
