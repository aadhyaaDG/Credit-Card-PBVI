{{
    config(
        materialized='table',
        post_hook=[
            "COPY (SELECT * FROM {{ this }})
             TO '/app/data/gold/daily_summary/data.parquet' (FORMAT PARQUET)"
        ]
    )
}}

-- Gold must not reference any bronze/ path (INV-15).
-- Only _is_resolvable = true records contribute to Gold (INV-17).

WITH silver AS (
    SELECT *
    FROM read_parquet(
        '/app/data/silver/transactions/**/data.parquet',
        hive_partitioning=true
    )
),

-- Date spine: every date present in Silver regardless of resolvability.
-- Ensures dates where ALL transactions are unresolvable still produce a zero row.
date_spine AS (
    SELECT DISTINCT transaction_date::DATE AS transaction_date
    FROM silver
),

-- transaction_type from Silver transaction_codes (INV-15 compliant — no Bronze read)
silver_tc AS (
    SELECT transaction_code, transaction_type
    FROM read_parquet('/app/data/silver/transaction_codes/data.parquet')
),

-- Period bounds over all Silver dates (used as metadata columns)
period AS (
    SELECT
        MIN(transaction_date::DATE) AS period_start,
        MAX(transaction_date::DATE) AS period_end
    FROM silver
),

-- Resolvable records only, enriched with transaction_type (INV-17)
resolvable AS (
    SELECT
        s.*,
        tc.transaction_type
    FROM silver s
    LEFT JOIN silver_tc tc ON s.transaction_code = tc.transaction_code
    WHERE s._is_resolvable = true
),

-- Daily aggregates from resolvable records
daily_agg AS (
    SELECT
        transaction_date::DATE                                                  AS transaction_date,
        COUNT(*)                                                                AS total_transactions,
        SUM(_signed_amount)                                                     AS total_signed_amount,
        COUNT(*) FILTER (WHERE channel = 'ONLINE')                             AS online_transactions,
        COUNT(*) FILTER (WHERE channel = 'IN_STORE')                           AS instore_transactions,
        -- Per-type counts and sums (used to build STRUCT below)
        COUNT(*)            FILTER (WHERE transaction_type = 'PURCHASE')        AS purchase_count,
        SUM(_signed_amount) FILTER (WHERE transaction_type = 'PURCHASE')        AS purchase_sum,
        COUNT(*)            FILTER (WHERE transaction_type = 'PAYMENT')         AS payment_count,
        SUM(_signed_amount) FILTER (WHERE transaction_type = 'PAYMENT')         AS payment_sum,
        COUNT(*)            FILTER (WHERE transaction_type = 'FEE')             AS fee_count,
        SUM(_signed_amount) FILTER (WHERE transaction_type = 'FEE')             AS fee_sum,
        COUNT(*)            FILTER (WHERE transaction_type = 'INTEREST')        AS interest_count,
        SUM(_signed_amount) FILTER (WHERE transaction_type = 'INTEREST')        AS interest_sum
    FROM resolvable
    GROUP BY transaction_date::DATE
)

SELECT
    d.transaction_date,
    COALESCE(a.total_transactions,   0)::INTEGER                        AS total_transactions,
    COALESCE(a.total_signed_amount,  0.0)::DECIMAL                      AS total_signed_amount,
    -- STRUCT: one entry per transaction_type with count and signed_amount sum (INV-17)
    {
        'PURCHASE': {
            'count': COALESCE(a.purchase_count, 0)::INTEGER,
            'sum':   COALESCE(a.purchase_sum,   0.0)::DECIMAL
        },
        'PAYMENT': {
            'count': COALESCE(a.payment_count,  0)::INTEGER,
            'sum':   COALESCE(a.payment_sum,    0.0)::DECIMAL
        },
        'FEE': {
            'count': COALESCE(a.fee_count,      0)::INTEGER,
            'sum':   COALESCE(a.fee_sum,        0.0)::DECIMAL
        },
        'INTEREST': {
            'count': COALESCE(a.interest_count, 0)::INTEGER,
            'sum':   COALESCE(a.interest_sum,   0.0)::DECIMAL
        }
    }                                                                    AS transactions_by_type,
    COALESCE(a.online_transactions,  0)::INTEGER                        AS online_transactions,
    COALESCE(a.instore_transactions, 0)::INTEGER                        AS instore_transactions,
    NOW()::TIMESTAMP                                                     AS _computed_at,
    '{{ var("run_id") }}'                                               AS _pipeline_run_id,
    p.period_start                                                       AS _source_period_start,
    p.period_end                                                         AS _source_period_end

FROM date_spine d
LEFT JOIN daily_agg  a ON d.transaction_date = a.transaction_date
CROSS JOIN period    p
ORDER BY d.transaction_date
