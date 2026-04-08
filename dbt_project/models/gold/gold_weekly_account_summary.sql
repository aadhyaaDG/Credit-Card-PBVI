{{
    config(
        materialized='table',
        post_hook=[
            "COPY (SELECT * FROM {{ this }})
             TO '/app/data/gold/weekly_account_summary/data.parquet' (FORMAT PARQUET)"
        ]
    )
}}

-- Gold must not reference any bronze/ path (INV-15).
-- Only _is_resolvable = true records contribute to Gold (INV-17).

WITH silver_txn AS (
    SELECT *
    FROM read_parquet(
        '/app/data/silver/transactions/**/data.parquet',
        hive_partitioning=true
    )
    WHERE _is_resolvable = true
),

-- transaction_type from Silver transaction_codes (INV-15 — no Bronze read)
silver_tc AS (
    SELECT transaction_code, transaction_type
    FROM read_parquet('/app/data/silver/transaction_codes/data.parquet')
),

-- closing_balance from Silver accounts (LEFT JOIN — NULL if account not found)
silver_acc AS (
    SELECT account_id, current_balance AS closing_balance
    FROM read_parquet('/app/data/silver/accounts/data.parquet')
),

-- Enrich transactions with transaction_type and ISO week bounds
-- DATE_TRUNC('week', ...) in DuckDB truncates to Monday (ISO week start)
enriched AS (
    SELECT
        t.*,
        tc.transaction_type,
        DATE_TRUNC('week', t.transaction_date::DATE)::DATE                       AS week_start_date,
        (DATE_TRUNC('week', t.transaction_date::DATE) + INTERVAL 6 DAYS)::DATE   AS week_end_date
    FROM silver_txn t
    LEFT JOIN silver_tc tc ON t.transaction_code = tc.transaction_code
),

-- One row per account × week — only weeks with at least one resolvable transaction
weekly_agg AS (
    SELECT
        week_start_date,
        week_end_date,
        account_id,
        -- COUNT returns 0 (not NULL) when filter matches nothing
        COUNT(*) FILTER (WHERE transaction_type = 'PURCHASE')               AS total_purchases,
        -- AVG returns NULL when no purchases — left as NULL (0 would be misleading)
        AVG(_signed_amount) FILTER (WHERE transaction_type = 'PURCHASE')    AS avg_purchase_amount,
        -- SUM returns NULL when no matches — COALESCE to 0
        SUM(_signed_amount) FILTER (WHERE transaction_type = 'PAYMENT')     AS total_payments,
        SUM(_signed_amount) FILTER (WHERE transaction_type = 'FEE')         AS total_fees,
        SUM(_signed_amount) FILTER (WHERE transaction_type = 'INTEREST')    AS total_interest
    FROM enriched
    GROUP BY week_start_date, week_end_date, account_id
)

SELECT
    w.week_start_date,
    w.week_end_date,
    w.account_id,
    w.total_purchases::INTEGER                      AS total_purchases,
    w.avg_purchase_amount::DECIMAL                  AS avg_purchase_amount,
    COALESCE(w.total_payments,  0.0)::DECIMAL       AS total_payments,
    COALESCE(w.total_fees,      0.0)::DECIMAL       AS total_fees,
    COALESCE(w.total_interest,  0.0)::DECIMAL       AS total_interest,
    a.closing_balance                                AS closing_balance,
    NOW()::TIMESTAMP                                 AS _computed_at,
    '{{ var("run_id") }}'                           AS _pipeline_run_id

FROM weekly_agg w
LEFT JOIN silver_acc a ON w.account_id = a.account_id
ORDER BY w.week_start_date, w.account_id
