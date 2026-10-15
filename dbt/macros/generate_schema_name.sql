{#- Use the folder's schema (staging, marts, reports) as-is instead of
    "<target_schema>_<custom>", so every warehouse gets the same schema names. -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}
