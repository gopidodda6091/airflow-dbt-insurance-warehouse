{#- SCD2 history for dim_policy. The timestamp strategy uses the source system's
    updated_at, so dbt_valid_from is the business change time, not the run time.
    Versions that start and are replaced between two extracts are never seen. -#}
{% snapshot snap_policy %}
    {{
        config(
            unique_key='policy_id',
            strategy='timestamp',
            updated_at='updated_at',
        )
    }}
    select * from {{ ref('stg_policies') }}
{% endsnapshot %}
