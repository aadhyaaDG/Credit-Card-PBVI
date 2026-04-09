{{
    config(
        materialized='table',
        post_hook=[
            "COPY (
                SELECT
                    * EXCLUDE (_ingested_at, _pipeline_run_id),
                    '{{ var(\"run_id\") }}'  AS _pipeline_run_id,
                    NOW()::TIMESTAMP          AS _rejected_at,
                    CASE
                        WHEN transaction_id IS NULL OR TRIM(transaction_id::VARCHAR) = ''
                          OR account_id     IS NULL OR TRIM(account_id::VARCHAR)     = ''
                          OR transaction_date IS NULL
                          OR amount           IS NULL
                          OR transaction_code IS NULL OR TRIM(transaction_code::VARCHAR) = ''
                          OR channel          IS NULL OR TRIM(channel::VARCHAR)          = ''
                        THEN 'NULL_REQUIRED_FIELD'
                        WHEN amount::DOUBLE <= 0
                        THEN 'INVALID_AMOUNT'
                        WHEN transaction_id IN (
                            SELECT transaction_id FROM {{ this }}
                        )
                        THEN 'DUPLICATE_TRANSACTION_ID'
                        WHEN transaction_code NOT IN (
                            SELECT transaction_code
                            FROM read_parquet('/app/data/silver/transaction_codes/data.parquet')
                        )
                        THEN 'INVALID_TRANSACTION_CODE'
                        WHEN channel NOT IN ('ONLINE', 'IN_STORE')
                        THEN 'INVALID_CHANNEL'
                        ELSE NULL
                    END AS _rejection_reason
                FROM read_parquet('/app/data/bronze/transactions/date={{ var(\"processing_date\") }}/data.parquet')
                WHERE
                    transaction_id IS NULL OR TRIM(transaction_id::VARCHAR) = ''
                    OR account_id IS NULL OR TRIM(account_id::VARCHAR) = ''
                    OR transaction_date IS NULL
                    OR amount IS NULL
                    OR transaction_code IS NULL OR TRIM(transaction_code::VARCHAR) = ''
                    OR channel IS NULL OR TRIM(channel::VARCHAR) = ''
                    OR amount::DOUBLE <= 0
                    OR transaction_id NOT IN (
                        SELECT transaction_id FROM {{ this }}
                    )
                    OR transaction_code NOT IN (
                        SELECT transaction_code
                        FROM read_parquet('/app/data/silver/transaction_codes/data.parquet')
                    )
                    OR channel NOT IN ('ONLINE', 'IN_STORE')
            ) TO '/app/data/silver/quarantine/date={{ var(\"processing_date\") }}/rejected.parquet'
              (FORMAT PARQUET)",

            "COPY (SELECT * FROM {{ this }})
             TO '/app/data/silver/transactions/date={{ var(\"processing_date\") }}/data.parquet'
             (FORMAT PARQUET)"
        ]
    )
}}

{% if execute %}
  {% set silver_file_count = run_query(
      "SELECT COUNT(*) FROM glob('/app/data/silver/transactions/**/data.parquet')"
  ).columns[0].values()[0] %}
  {% set has_existing_silver = silver_file_count > 0 %}
{% else %}
  {% set has_existing_silver = false %}
{% endif %}

WITH bronze AS (
    SELECT *
    FROM read_parquet('/app/data/bronze/transactions/date={{ var("processing_date") }}/data.parquet')
),

{% if has_existing_silver %}
-- Cross-partition duplicate check (INV-14) — only run if prior Silver partitions exist
existing_ids AS (
    SELECT DISTINCT transaction_id
    FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
),
{% endif %}

tc AS (
    SELECT transaction_code, debit_credit_indicator
    FROM read_parquet('/app/data/silver/transaction_codes/data.parquet')
),

accts AS (
    SELECT account_id
    FROM read_parquet('/app/data/silver/accounts/data.parquet')
),

classified AS (
    SELECT
        b.* EXCLUDE (_ingested_at, _pipeline_run_id),
        b._ingested_at::TIMESTAMP   AS _bronze_ingested_at,
        tc.debit_credit_indicator,
        (accts.account_id IS NOT NULL) AS _is_resolvable,
        CASE
            -- Priority 1: null/empty required fields
            WHEN b.transaction_id IS NULL OR TRIM(b.transaction_id::VARCHAR) = ''
              OR b.account_id IS NULL OR TRIM(b.account_id::VARCHAR) = ''
              OR b.transaction_date IS NULL
              OR b.amount IS NULL
              OR b.transaction_code IS NULL OR TRIM(b.transaction_code::VARCHAR) = ''
              OR b.channel IS NULL OR TRIM(b.channel::VARCHAR) = ''
            THEN 'NULL_REQUIRED_FIELD'
            -- Priority 2: invalid amount (zero or negative)
            WHEN b.amount::DOUBLE <= 0
            THEN 'INVALID_AMOUNT'
            -- Priority 3: cross-partition duplicate (INV-14)
            {% if has_existing_silver %}
            WHEN b.transaction_id IN (SELECT transaction_id FROM existing_ids)
            THEN 'DUPLICATE_TRANSACTION_ID'
            {% endif %}
            -- Priority 4: unknown transaction code
            WHEN tc.transaction_code IS NULL
            THEN 'INVALID_TRANSACTION_CODE'
            -- Priority 5: invalid channel
            WHEN b.channel NOT IN ('ONLINE', 'IN_STORE')
            THEN 'INVALID_CHANNEL'
            ELSE NULL  -- passes all rules
        END AS _rejection_reason
    FROM bronze b
    LEFT JOIN tc    ON b.transaction_code = tc.transaction_code
    LEFT JOIN accts ON b.account_id       = accts.account_id
)

-- Silver output: only passing records with full audit columns (INV-07, INV-08, INV-11)
SELECT
    * EXCLUDE (debit_credit_indicator, _rejection_reason),
    -- _signed_amount derived exclusively from transaction_codes join (INV-13)
    amount::DOUBLE * CASE WHEN debit_credit_indicator = 'DR' THEN 1.0 ELSE -1.0 END
        AS _signed_amount,
    '{{ var("run_id") }}'   AS _pipeline_run_id,
    NOW()::TIMESTAMP        AS _promoted_at
FROM classified
WHERE _rejection_reason IS NULL
