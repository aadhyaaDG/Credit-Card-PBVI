-- verification/bronze_checks.sql
-- Phase 8 Bronze completeness verification queries (Section 10.1 sign-off).
-- Run with: duckdb -c "$(cat verification/bronze_checks.sql)"
-- All paths use container paths (/app/data/, /app/source/).
-- Expected result for each query is stated in the comment above it.


-- ----------------------------------------------------------------------------
-- Query 1: Bronze transactions row count vs source CSVs across all 7 partitions
-- Expected: Every date row shows bronze_count = source_count (delta = 0).
-- ----------------------------------------------------------------------------
SELECT
    date_part,
    source_count,
    bronze_count,
    (bronze_count - source_count) AS delta
FROM (
    SELECT
        partition.date_part,
        (SELECT COUNT(*) FROM read_csv_auto('/app/source/transactions_' || partition.date_part || '.csv')) AS source_count,
        (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date=' || partition.date_part || '/data.parquet')) AS bronze_count
    FROM (
        VALUES
            ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
            ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
    ) AS partition(date_part)
)
ORDER BY date_part;


-- ----------------------------------------------------------------------------
-- Query 2: Bronze accounts row count vs source CSVs across all 7 partitions
-- Expected: Every date row shows bronze_count = source_count (delta = 0).
-- ----------------------------------------------------------------------------
SELECT
    date_part,
    source_count,
    bronze_count,
    (bronze_count - source_count) AS delta
FROM (
    SELECT
        partition.date_part,
        (SELECT COUNT(*) FROM read_csv_auto('/app/source/accounts_' || partition.date_part || '.csv')) AS source_count,
        (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/accounts/date=' || partition.date_part || '/data.parquet')) AS bronze_count
    FROM (
        VALUES
            ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
            ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
    ) AS partition(date_part)
)
ORDER BY date_part;


-- ----------------------------------------------------------------------------
-- Query 3: Bronze transaction_codes row count vs source CSV
-- Expected: bronze_count = source_count (delta = 0).
-- ----------------------------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM read_csv_auto('/app/source/transaction_codes.csv'))      AS source_count,
    (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet')) AS bronze_count,
    (
        (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet'))
        - (SELECT COUNT(*) FROM read_csv_auto('/app/source/transaction_codes.csv'))
    ) AS delta;


-- ----------------------------------------------------------------------------
-- Query 4: No null _pipeline_run_id in any Bronze partition (INV-11)
-- Expected: null_count = 0 for all rows. Any non-zero value is a violation.
-- ----------------------------------------------------------------------------
SELECT 'transactions' AS layer, date_part, null_count FROM (
    SELECT
        partition.date_part,
        (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date=' || partition.date_part || '/data.parquet')
         WHERE _pipeline_run_id IS NULL) AS null_count
    FROM (
        VALUES
            ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
            ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
    ) AS partition(date_part)
)
UNION ALL
SELECT 'accounts' AS layer, date_part, null_count FROM (
    SELECT
        partition.date_part,
        (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/accounts/date=' || partition.date_part || '/data.parquet')
         WHERE _pipeline_run_id IS NULL) AS null_count
    FROM (
        VALUES
            ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
            ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
    ) AS partition(date_part)
)
UNION ALL
SELECT
    'transaction_codes' AS layer,
    'static'            AS date_part,
    (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet')
     WHERE _pipeline_run_id IS NULL) AS null_count
ORDER BY layer, date_part;


-- ----------------------------------------------------------------------------
-- Query 5: No negative amounts in bronze/transactions (INV-06)
-- Expected: negative_count = 0 for all partitions. Any non-zero value is a violation.
-- ----------------------------------------------------------------------------
SELECT
    date_part,
    (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date=' || partition.date_part || '/data.parquet')
     WHERE amount < 0) AS negative_count
FROM (
    VALUES
        ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
        ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
) AS partition(date_part)
ORDER BY date_part;
