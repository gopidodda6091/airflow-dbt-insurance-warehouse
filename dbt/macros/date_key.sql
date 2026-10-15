{#- yyyymmdd integer key for dim_date joins; portable across DuckDB/Snowflake/Redshift. -#}
{% macro date_key(col) -%}
    cast(
        extract(year from {{ col }}) * 10000
        + extract(month from {{ col }}) * 100
        + extract(day from {{ col }})
    as integer)
{%- endmacro %}
