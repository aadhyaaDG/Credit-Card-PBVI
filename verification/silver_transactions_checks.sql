-- verification/silver_transactions_checks.sql
-- Phase 8 Silver transactions quality verification queries (Section 10.2 sign-off).
-- Run with: duckdb -c "$(cat verification/silver_transactions_checks.sql)"
-- All paths use container paths (/app/data/).
-- Expected result for each query is stated in the comment above it.


-- ----------------------------------------------------------------------------
-- Query 1: Cross-partition transaction_id uniqueness (INV-14)
-- Expected: Zero rows returned. Any row is a duplicate violation.
-- ----------------------------------------------------------------------------
SELECT
    transaction_id,
    COUNT(*) AS occurrences
FROM read_parquet(
    '/app/data/silver/transactions/**/data.parquet',
    hive_partitioning=true
)
GROUP BY transaction_id
HAVING COUNT(*) > 1
ORDER BY transaction_id;


-- ----------------------------------------------------------------------------
-- Query 2: No null _signed_amount in Silver transactions (INV-11, INV-13)
-- Expected: null_count = 0.
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*) AS null_count
FROM read_parquet(
    '/app/data/silver/transactions/**/data.parquet',
    hive_partitioning=true
)
WHERE _signed_amount IS NULL;


-- ----------------------------------------------------------------------------
-- Query 3: No null _is_resolvable in Silver transactions (INV-11)
-- Expected: null_count = 0.
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*) AS null_count
FROM read_parquet(
    '/app/data/silver/transactions/**/data.parquet',
    hive_partitioning=true
)
WHERE _is_resolvable IS NULL;


-- ----------------------------------------------------------------------------
-- Query 4: Row count reconciliation per date — Bronze = Silver + Quarantine (INV-09)
-- Expected: Every date row shows delta = 0. Any non-zero value is a violation.
-- ----------------------------------------------------------------------------
SELECT
    date_part,
    bronze_count,
    silver_count,
    quarantine_count,
    (bronze_count - silver_count - quarantine_count) AS delta
FROM (
    SELECT
        partition.date_part,
        (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date='     || partition.date_part || '/data.parquet'))    AS bronze_count,
        (SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/date='     || partition.date_part || '/data.parquet'))    AS silver_count,
        (SELECT COUNT(*) FROM read_parquet('/app/data/silver/quarantine/date='       || partition.date_part || '/rejected.parquet')) AS quarantine_count
    FROM (
        VALUES
            ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
            ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
    ) AS partition(date_part)
)
ORDER BY date_part;


-- ----------------------------------------------------------------------------
-- Query 5: All quarantine _rejection_reason values from exhaustive list (INV-08)
-- Expected: Zero rows returned. Any row contains an unrecognised rejection code.
-- ----------------------------------------------------------------------------
SELECT
    _rejection_reason,
    COUNT(*) AS occurrences
FROM read_parquet(
    '/app/data/silver/quarantine/**/rejected.parquet',
    hive_partitioning=true,
    union_by_name=true
)
WHERE _rejection_reason NOT IN (
    'NULL_REQUIRED_FIELD',
    'INVALID_AMOUNT',
    'DUPLICATE_TRANSACTION_ID',
    'INVALID_TRANSACTION_CODE',
    'INVALID_CHANNEL',
    'INVALID_ACCOUNT_STATUS'
)
   OR _rejection_reason IS NULL
GROUP BY _rejection_reason;


-- ----------------------------------------------------------------------------
-- Query 6: No record appears in both Silver transactions and quarantine
--          for the same date and transaction_id (INV-08 / INV-09 double-count guard)
-- Expected: Zero rows returned.
-- ----------------------------------------------------------------------------
SELECT
    s.transaction_id,
    s.transaction_date
FROM read_parquet(
    '/app/data/silver/transactions/**/data.parquet',
    hive_partitioning=true
) s
WHERE s.transaction_id IN (
    SELECT q.transaction_id
    FROM read_parquet(
        '/app/data/silver/quarantine/**/rejected.parquet',
        hive_partitioning=true,
        union_by_name=true
    ) q
    WHERE q.transaction_id IS NOT NULL
)
ORDER BY s.transaction_date, s.transaction_id;


-- ----------------------------------------------------------------------------
-- Query 7: Every _pipeline_run_id in Silver transactions has a SUCCESS entry
--          in the run log (INV-12)
-- Expected: Zero rows returned. Any row indicates an orphaned run_id.
-- ----------------------------------------------------------------------------
SELECT DISTINCT
    s._pipeline_run_id
FROM read_parquet(
    '/app/data/silver/transactions/**/data.parquet',
    hive_partitioning=true
) s
WHERE s._pipeline_run_id NOT IN (
    SELECT run_id
    FROM read_parquet('/app/data/pipeline/run_log.parquet')
    WHERE status = 'SUCCESS'
)
ORDER BY s._pipeline_run_id;


-- ----------------------------------------------------------------------------
-- Query 8: Combined totals — Silver + Quarantine = Bronze across all 7 partitions (INV-09)
-- Expected: delta = 0. Any non-zero value means records are unaccounted for.
-- ----------------------------------------------------------------------------
SELECT
    SUM(bronze_count)                               AS total_bronze,
    SUM(silver_count)                               AS total_silver,
    SUM(quarantine_count)                           AS total_quarantine,
    SUM(bronze_count) - SUM(silver_count) - SUM(quarantine_count) AS delta
FROM (
    SELECT
        partition.date_part,
        (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date=' || partition.date_part || '/data.parquet'))    AS bronze_count,
        (SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/date=' || partition.date_part || '/data.parquet'))    AS silver_count,
        (SELECT COUNT(*) FROM read_parquet('/app/data/silver/quarantine/date='   || partition.date_part || '/rejected.parquet')) AS quarantine_count
    FROM (
        VALUES
            ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
            ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
    ) AS partition(date_part)
);


-- ----------------------------------------------------------------------------
-- Query 9: Every Silver transaction has a valid transaction_code in silver_transaction_codes
--          (INV-13 — sign derivation source must exist for every Silver record)
-- Expected: Zero rows returned. Any row has an unresolvable transaction_code.
-- ----------------------------------------------------------------------------
SELECT
    s.transaction_id,
    s.transaction_code
FROM read_parquet(
    '/app/data/silver/transactions/**/data.parquet',
    hive_partitioning=true
) s
WHERE s.transaction_code NOT IN (
    SELECT transaction_code
    FROM read_parquet('/app/data/silver/transaction_codes/data.parquet')
)
ORDER BY s.transaction_id;


-- ----------------------------------------------------------------------------
-- Query 10: TODO — No record with _is_resolvable = false appears in Gold output (INV-17)
-- Implemented in S6 once Gold models are in place.
-- Expected: Zero rows returned. Any row means an unresolvable record reached Gold.
-- ----------------------------------------------------------------------------
-- SELECT g.transaction_id
-- FROM read_parquet('/app/data/gold/daily_summary/data.parquet') g
-- JOIN read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true) s
--   ON g.transaction_id = s.transaction_id
-- WHERE s._is_resolvable = false;
-- TODO: uncomment and finalise in S6
