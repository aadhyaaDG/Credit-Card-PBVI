-- verification/idempotency_checks.sql
-- Queries used by run_idempotency_test.sh to capture layer row counts.
-- Run these manually to inspect counts after any pipeline invocation.
-- All paths use container paths (/app/data/).
-- Expected: identical results between any two runs on the same input (INV-10).


-- ----------------------------------------------------------------------------
-- Q1: Bronze transactions — total rows across all date partitions
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS bronze_txn_rows
FROM read_parquet(
    '/app/data/bronze/transactions/**/data.parquet',
    hive_partitioning=true
);


-- ----------------------------------------------------------------------------
-- Q2: Bronze accounts — total rows across all date partitions
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS bronze_acc_rows
FROM read_parquet(
    '/app/data/bronze/accounts/**/data.parquet',
    hive_partitioning=true
);


-- ----------------------------------------------------------------------------
-- Q3: Bronze transaction codes — row count (static reference file)
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS bronze_tc_rows
FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet');


-- ----------------------------------------------------------------------------
-- Q4: Silver transactions — total rows across all date partitions
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS silver_txn_rows
FROM read_parquet(
    '/app/data/silver/transactions/**/data.parquet',
    hive_partitioning=true
);


-- ----------------------------------------------------------------------------
-- Q5: Silver accounts — row count (single cumulative file)
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS silver_acc_rows
FROM read_parquet('/app/data/silver/accounts/data.parquet');


-- ----------------------------------------------------------------------------
-- Q6: Silver quarantine — total rejected rows across all partitions
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS quarantine_rows
FROM read_parquet(
    '/app/data/silver/quarantine/**/rejected.parquet',
    hive_partitioning=true,
    union_by_name=true
);


-- ----------------------------------------------------------------------------
-- Q7: Gold daily summary — row count and total_signed_amount sum
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*)                    AS gold_daily_rows,
    SUM(total_signed_amount)    AS gold_daily_signed_sum
FROM read_parquet('/app/data/gold/daily_summary/data.parquet');


-- ----------------------------------------------------------------------------
-- Q8: Gold weekly account summary — row count
-- ----------------------------------------------------------------------------
SELECT COUNT(*) AS gold_weekly_rows
FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet');


-- ----------------------------------------------------------------------------
-- Q9: Watermark — last_processed_date must equal 2024-01-07 after full run
-- ----------------------------------------------------------------------------
SELECT last_processed_date AS watermark
FROM read_parquet('/app/data/pipeline/control.parquet');
