{#- Keep one row per key: the latest by order_by (e.g. updated_at desc, _extract_date desc).
    Written as a subquery + row_number so it runs on warehouses without QUALIFY (Redshift). -#}
{% macro dedupe(relation, partition_by, order_by) -%}
    select * from (
        select
            src.*,
            row_number() over (partition by {{ partition_by }} order by {{ order_by }}) as _row_num
        from {{ relation }} as src
    ) as ranked
    where _row_num = 1
{%- endmacro %}
