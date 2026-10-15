{#- Deterministic surrogate key: md5 over the null-safe, delimited column values.
    md5() exists on DuckDB, Snowflake and Redshift, so keys match across warehouses. -#}
{% macro surrogate_key(columns) -%}
    md5(
    {%- for col in columns %}
        coalesce(cast({{ col }} as {{ dbt.type_string() }}), '~null~'){% if not loop.last %} || '|' ||{% endif %}
    {%- endfor %}
    )
{%- endmacro %}
