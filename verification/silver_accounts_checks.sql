-- verification/silver_accounts_checks.sql
-- Phase 8 Silver accounts quality verification queries.
-- Run with: duckdb -c "$(cat verification/silver_accounts_checks.sql)"
-- All paths use container paths (/app/data/).
-- Expected result for each query is stated in the comment above it.


-- ----------------------------------------------------------------------------
-- Query 1: Exactly one record per account_id in silver/accounts/data.parquet (INV-19)
-- Expected: Zero rows returned. Any row is a duplicate violation.
-- ----------------------------------------------------------------------------
SELECT
    account_id,
    COUNT(*) AS record_count
FROM read_parquet('/app/data/silver/accounts/data.parquet')
GROUP BY account_id
HAVING COUNT(*) > 1
ORDER BY account_id;


-- ----------------------------------------------------------------------------
-- Query 2: No null _pipeline_run_id in silver/accounts/data.parquet (INV-11)
-- Expected: null_count = 0.
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*) AS null_count
FROM read_parquet('/app/data/silver/accounts/data.parquet')
WHERE _pipeline_run_id IS NULL;


-- ----------------------------------------------------------------------------
-- Query 3: No null _record_valid_from in silver/accounts/data.parquet (INV-11)
-- Expected: null_count = 0.
-- ----------------------------------------------------------------------------
SELECT
    COUNT(*) AS null_count
FROM read_parquet('/app/data/silver/accounts/data.parquet')
WHERE _record_valid_from IS NULL;


-- ----------------------------------------------------------------------------
-- Query 4: All account_status values are valid (ACTIVE, SUSPENDED, CLOSED)
-- Expected: Zero rows returned. Any row contains an invalid status.
-- ----------------------------------------------------------------------------
SELECT
    account_id,
    account_status
FROM read_parquet('/app/data/silver/accounts/data.parquet')
WHERE account_status NOT IN ('ACTIVE', 'SUSPENDED', 'CLOSED')
ORDER BY account_id;


-- ----------------------------------------------------------------------------
-- Query 5: All quarantine records have a non-null _rejection_reason (INV-08)
-- Expected: null_count = 0 for all date partitions.
-- ----------------------------------------------------------------------------
SELECT
    date_part,
    COUNT(*) AS null_count
FROM (
    SELECT
        partition.date_part,
        (SELECT COUNT(*)
         FROM read_parquet('/app/data/silver/quarantine/date=' || partition.date_part || '/rejected.parquet')
         WHERE _rejection_reason IS NULL) AS null_count
    FROM (
        VALUES
            ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
            ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
    ) AS partition(date_part)
)
WHERE null_count > 0
ORDER BY date_part;


-- ----------------------------------------------------------------------------
-- Query 6: All quarantine _rejection_reason values are from the exhaustive list
--          (NULL_REQUIRED_FIELD, INVALID_ACCOUNT_STATUS) (INV-08)
-- Expected: Zero rows returned. Any row contains an unrecognised rejection code.
-- ----------------------------------------------------------------------------
SELECT
    date_part,
    _rejection_reason,
    COUNT(*) AS occurrences
FROM (
    SELECT
        partition.date_part,
        q._rejection_reason
    FROM (
        VALUES
            ('2024-01-01'), ('2024-01-02'), ('2024-01-03'), ('2024-01-04'),
            ('2024-01-05'), ('2024-01-06'), ('2024-01-07')
    ) AS partition(date_part)
    JOIN read_parquet('/app/data/silver/quarantine/date=' || partition.date_part || '/rejected.parquet') q ON TRUE
)
WHERE _rejection_reason NOT IN ('NULL_REQUIRED_FIELD', 'INVALID_ACCOUNT_STATUS')
GROUP BY date_part, _rejection_reason
ORDER BY date_part;
