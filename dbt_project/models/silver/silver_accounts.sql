{{
    config(
        materialized='incremental',
        unique_key='account_id',
        incremental_strategy='delete+insert',
        post_hook=[
               "COPY (
                    SELECT
                        * EXCLUDE (_ingested_at, _pipeline_run_id),
                        '{{ var(\"run_id\") }}'  AS _pipeline_run_id,
                        NOW()::TIMESTAMP          AS _rejected_at,
                        CASE
                            WHEN account_id IS NULL OR TRIM(CAST(account_id AS VARCHAR)) = ''
                              OR open_date IS NULL
                              OR credit_limit IS NULL
                              OR current_balance IS NULL
                              OR billing_cycle_start IS NULL
                              OR billing_cycle_end IS NULL
                              OR account_status IS NULL OR TRIM(CAST(account_status AS VARCHAR)) = ''
                            THEN 'NULL_REQUIRED_FIELD'
                            ELSE 'INVALID_ACCOUNT_STATUS'
                        END AS _rejection_reason
                    FROM read_parquet('/app/data/bronze/accounts/date={{ var(\"processing_date\") }}/data.parquet')
                    WHERE account_id IS NULL OR TRIM(CAST(account_id AS VARCHAR)) = ''
                       OR open_date IS NULL
                       OR credit_limit IS NULL
                       OR current_balance IS NULL
                       OR billing_cycle_start IS NULL
                       OR billing_cycle_end IS NULL
                       OR account_status IS NULL OR TRIM(CAST(account_status AS VARCHAR)) = ''
                       OR account_status NOT IN ('ACTIVE', 'SUSPENDED', 'CLOSED')
                ) TO '/app/data/silver/quarantine/date={{ var(\"processing_date\") }}/rejected.parquet'
                  (FORMAT PARQUET)",

               "COPY (SELECT * FROM {{ this }})
                TO '/app/data/silver/accounts/data.parquet' (FORMAT PARQUET)"
           ])
}}

WITH bronze_incoming AS (
    SELECT *
    FROM read_parquet('/app/data/bronze/accounts/date={{ var("processing_date") }}/data.parquet')
),

-- Records that pass all quality rules (INV-07, INV-08)
passing AS (
    SELECT
        * EXCLUDE (_ingested_at, _pipeline_run_id),
        _ingested_at::TIMESTAMP     AS _bronze_ingested_at,
        '{{ var("run_id") }}'       AS _pipeline_run_id,
        NOW()::TIMESTAMP            AS _record_valid_from
    FROM bronze_incoming
    WHERE account_id IS NOT NULL AND TRIM(CAST(account_id AS VARCHAR)) != ''
      AND open_date IS NOT NULL
      AND credit_limit IS NOT NULL
      AND current_balance IS NOT NULL
      AND billing_cycle_start IS NOT NULL
      AND billing_cycle_end IS NOT NULL
      AND account_status IS NOT NULL AND TRIM(CAST(account_status AS VARCHAR)) != ''
      AND account_status IN ('ACTIVE', 'SUSPENDED', 'CLOSED')
)

-- Emit passing rows only. The incremental delete+insert strategy on unique_key='account_id'
-- keeps exactly one row per account_id across all batches (INV-19).
SELECT * FROM passing
