{{
    config(materialized='table')
}}

{% if execute %}
  {% set quarantine_file_count = run_query(
      "SELECT COUNT(*) FROM (SELECT unnest(glob('/app/data/silver/quarantine/**/rejected.parquet')) AS f)"
  ).columns[0].values()[0] %}
  {% set has_quarantine = quarantine_file_count > 0 %}
{% else %}
  {% set has_quarantine = false %}
{% endif %}

-- Dependency: silver_transactions must run before this model writes quarantine files
-- {{ ref('silver_transactions') }}

{% if has_quarantine %}
SELECT *
FROM read_parquet(
    '/app/data/silver/quarantine/**/rejected.parquet',
    hive_partitioning=true,
    union_by_name=true
)
{% else %}
-- No quarantine records yet — return empty result with known audit columns
SELECT
    NULL::VARCHAR   AS _source_file,
    NULL::VARCHAR   AS _pipeline_run_id,
    NULL::TIMESTAMP AS _rejected_at,
    NULL::VARCHAR   AS _rejection_reason
WHERE 1=0
{% endif %}
