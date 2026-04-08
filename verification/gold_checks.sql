-- verification/gold_checks.sql
-- Phase 8 Gold layer quality verification queries (Section 10.2 sign-off).
-- Run with: duckdb -c "$(cat verification/gold_checks.sql)"
-- All paths use container paths (/app/data/).
-- Expected result for each query is stated in the comment above it.


-- ----------------------------------------------------------------------------
-- Query 1: gold_daily_summary row count = distinct Silver transaction_date count
--          (date spine completeness — every date in Silver, even unresolvable-only, appears in Gold)
-- Expected: Zero rows returned. Any row indicates a missing or extra date in Gold.
-- ----------------------------------------------------------------------------
SELECT
    spine.transaction_date,
    CASE
        WHEN g.transaction_date IS NULL THEN 'MISSING_FROM_GOLD'
        ELSE                                 'EXTRA_IN_GOLD'
    END AS anomaly
FROM (
    SELECT DISTINCT transaction_date::DATE AS transaction_date
    FROM read_parquet(
        '/app/data/silver/transactions/**/data.parquet',
        hive_partitioning=true
    )
) spine
FULL OUTER JOIN read_parquet('/app/data/gold/daily_summary/data.parquet') g
    ON spine.transaction_date = g.transaction_date
WHERE spine.transaction_date IS NULL
   OR g.transaction_date     IS NULL
ORDER BY COALESCE(spine.transaction_date, g.transaction_date);


-- ----------------------------------------------------------------------------
-- Query 2: gold_daily_summary.total_transactions = resolvable Silver count per date (INV-17)
-- Expected: Zero rows returned. Any row means unresolvable records or a count mismatch.
-- ----------------------------------------------------------------------------
SELECT
    g.transaction_date,
    g.total_transactions                                AS gold_count,
    COALESCE(s.resolvable_count, 0)                    AS silver_resolvable_count,
    g.total_transactions - COALESCE(s.resolvable_count, 0) AS delta
FROM read_parquet('/app/data/gold/daily_summary/data.parquet') g
LEFT JOIN (
    SELECT
        transaction_date::DATE  AS transaction_date,
        COUNT(*)                AS resolvable_count
    FROM read_parquet(
        '/app/data/silver/transactions/**/data.parquet',
        hive_partitioning=true
    )
    WHERE _is_resolvable = true
    GROUP BY transaction_date::DATE
) s ON g.transaction_date = s.transaction_date
WHERE g.total_transactions != COALESCE(s.resolvable_count, 0)
ORDER BY g.transaction_date;


-- ----------------------------------------------------------------------------
-- Query 3: gold_daily_summary.total_signed_amount = SUM of resolvable Silver _signed_amount (INV-17)
-- Expected: Zero rows returned. Any row indicates an arithmetic mismatch.
-- ----------------------------------------------------------------------------
SELECT
    g.transaction_date,
    g.total_signed_amount                               AS gold_sum,
    COALESCE(s.resolvable_sum, 0.0)                    AS silver_resolvable_sum,
    g.total_signed_amount - COALESCE(s.resolvable_sum, 0.0) AS delta
FROM read_parquet('/app/data/gold/daily_summary/data.parquet') g
LEFT JOIN (
    SELECT
        transaction_date::DATE      AS transaction_date,
        SUM(_signed_amount)         AS resolvable_sum
    FROM read_parquet(
        '/app/data/silver/transactions/**/data.parquet',
        hive_partitioning=true
    )
    WHERE _is_resolvable = true
    GROUP BY transaction_date::DATE
) s ON g.transaction_date = s.transaction_date
WHERE ABS(g.total_signed_amount - COALESCE(s.resolvable_sum, 0.0)) > 0.001
ORDER BY g.transaction_date;


-- ----------------------------------------------------------------------------
-- Query 4: gold_weekly_account_summary.total_purchases = resolvable PURCHASE count
--          per account × week in Silver (INV-17 at weekly granularity)
-- Expected: Zero rows returned. Any row means a count mismatch or leaked unresolvable records.
-- ----------------------------------------------------------------------------
SELECT
    w.account_id,
    w.week_start_date,
    w.total_purchases                                   AS gold_purchase_count,
    COALESCE(s.purchase_count, 0)                      AS silver_resolvable_purchase_count,
    w.total_purchases - COALESCE(s.purchase_count, 0) AS delta
FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet') w
LEFT JOIN (
    SELECT
        txn.account_id,
        DATE_TRUNC('week', txn.transaction_date::DATE)::DATE    AS week_start,
        COUNT(*)                                                 AS purchase_count
    FROM read_parquet(
        '/app/data/silver/transactions/**/data.parquet',
        hive_partitioning=true
    ) txn
    JOIN read_parquet('/app/data/silver/transaction_codes/data.parquet') tc
        ON txn.transaction_code = tc.transaction_code
    WHERE txn._is_resolvable = true
      AND tc.transaction_type = 'PURCHASE'
    GROUP BY txn.account_id, DATE_TRUNC('week', txn.transaction_date::DATE)::DATE
) s ON w.account_id = s.account_id AND w.week_start_date = s.week_start
WHERE w.total_purchases != COALESCE(s.purchase_count, 0)
ORDER BY w.week_start_date, w.account_id;


-- ----------------------------------------------------------------------------
-- Query 5: week_start_date is always Monday in gold_weekly_account_summary (TC-5)
--          DuckDB EXTRACT(DOW): 0=Sunday, 1=Monday, ..., 6=Saturday
-- Expected: Zero rows returned. Any row has a non-Monday week_start_date.
-- ----------------------------------------------------------------------------
SELECT
    account_id,
    week_start_date,
    EXTRACT(DOW FROM week_start_date) AS day_of_week
FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet')
WHERE EXTRACT(DOW FROM week_start_date) != 1
ORDER BY week_start_date, account_id;


-- ----------------------------------------------------------------------------
-- Query 6: week_end_date = week_start_date + INTERVAL 6 DAYS always
-- Expected: Zero rows returned. Any row has an incorrect week_end_date.
-- ----------------------------------------------------------------------------
SELECT
    account_id,
    week_start_date,
    week_end_date,
    (week_start_date + INTERVAL 6 DAYS)::DATE AS expected_week_end_date
FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet')
WHERE week_end_date != (week_start_date + INTERVAL 6 DAYS)::DATE
ORDER BY week_start_date, account_id;


-- ----------------------------------------------------------------------------
-- Query 7: No null _pipeline_run_id in either Gold output file (INV-11)
-- Expected: Both null_count values = 0.
-- ----------------------------------------------------------------------------
SELECT 'gold_daily_summary'          AS model,     COUNT(*) AS null_count
FROM read_parquet('/app/data/gold/daily_summary/data.parquet')
WHERE _pipeline_run_id IS NULL

UNION ALL

SELECT 'gold_weekly_account_summary' AS model,     COUNT(*) AS null_count
FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet')
WHERE _pipeline_run_id IS NULL

ORDER BY model;
