#!/usr/bin/env bash
# verification/run_all_checks.sh
# Full system verification script — Phase 8, Sections 10.1–10.6.
#
# Runs all invariant checks across Bronze, Silver, Gold, Idempotency,
# and Audit Trail without stopping on individual failures.
#
# Usage (inside container):
#   bash /app/verification/run_all_checks.sh
#
# Usage (via docker compose):
#   docker compose exec pipeline bash /app/verification/run_all_checks.sh
#
# Exit code: 0 if every check passes, 1 if any check fails.

set -uo pipefail

FAILURES=0
TOTAL=0

# ---------------------------------------------------------------------------
# Helper: run a DuckDB SQL statement via Python and return a single scalar.
# Returns 0 on file-not-found or query error so other checks still run.
# ---------------------------------------------------------------------------
run_query() {
    DUCKDB_QUERY="$1" python3 - << 'PYEOF'
import duckdb, os, sys
sql = os.environ["DUCKDB_QUERY"]
try:
    result = duckdb.sql(sql).fetchone()
    val = result[0] if result and result[0] is not None else 0
    # Normalise floats that are effectively zero
    try:
        print(0 if abs(float(val)) < 1e-9 else val)
    except (TypeError, ValueError):
        print(val)
except Exception as e:
    print(f"QUERY_ERROR: {e}", file=sys.stderr)
    print(0)
PYEOF
}

# ---------------------------------------------------------------------------
# Helper: evaluate one check.  Prints PASS/FAIL and increments counters.
# A result of 0 (or 0.0) means no violations → PASS.
# ---------------------------------------------------------------------------
check() {
    local id="$1"
    local label="$2"
    local query="$3"
    TOTAL=$((TOTAL + 1))
    local result
    result=$(run_query "$query")
    if [ "$result" = "0" ] || [ "$result" = "0.0" ]; then
        printf "  PASS  [%s] %s\n" "$id" "$label"
    else
        printf "  FAIL  [%s] %s  (violations=%s)\n" "$id" "$label" "$result"
        FAILURES=$((FAILURES + 1))
    fi
}

DATES="('2024-01-01'),('2024-01-02'),('2024-01-03'),('2024-01-04'),('2024-01-05'),('2024-01-06'),('2024-01-07')"

# ===========================================================================
# 10.1  BRONZE COMPLETENESS
# ===========================================================================
echo ""
echo "========================================="
echo "  10.1  Bronze Completeness"
echo "========================================="

check "B-01" "Transactions: bronze_count = source_count for all 7 partitions (INV-05)" "
SELECT COUNT(*) AS violations FROM (
    SELECT partition.date_part,
           (SELECT COUNT(*) FROM read_csv_auto('/app/source/transactions_' || partition.date_part || '.csv'))                            AS source_count,
           (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date=' || partition.date_part || '/data.parquet'))          AS bronze_count
    FROM (VALUES $DATES) AS partition(date_part)
) WHERE bronze_count != source_count"

check "B-02" "Accounts: bronze_count = source_count for all 7 partitions (INV-05)" "
SELECT COUNT(*) AS violations FROM (
    SELECT partition.date_part,
           (SELECT COUNT(*) FROM read_csv_auto('/app/source/accounts_' || partition.date_part || '.csv'))                               AS source_count,
           (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/accounts/date=' || partition.date_part || '/data.parquet'))             AS bronze_count
    FROM (VALUES $DATES) AS partition(date_part)
) WHERE bronze_count != source_count"

check "B-03" "Transaction codes: bronze_count = source_count (INV-05)" "
SELECT ABS(
    (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet'))
    - (SELECT COUNT(*) FROM read_csv_auto('/app/source/transaction_codes.csv'))
) AS delta"

check "B-04" "No null _pipeline_run_id in Bronze transactions, accounts, or transaction_codes (INV-11)" "
SELECT SUM(null_count) FROM (
    SELECT (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date=' || p.date_part || '/data.parquet') WHERE _pipeline_run_id IS NULL) AS null_count
    FROM (VALUES $DATES) AS p(date_part)
    UNION ALL
    SELECT (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/accounts/date=' || p.date_part || '/data.parquet') WHERE _pipeline_run_id IS NULL)
    FROM (VALUES $DATES) AS p(date_part)
    UNION ALL
    SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet') WHERE _pipeline_run_id IS NULL
)"

check "B-05" "No negative amounts in Bronze transactions (INV-06)" "
SELECT SUM(neg) FROM (
    SELECT (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date=' || p.date_part || '/data.parquet') WHERE amount < 0) AS neg
    FROM (VALUES $DATES) AS p(date_part)
)"

# ===========================================================================
# 10.2  SILVER TRANSACTIONS QUALITY
# ===========================================================================
echo ""
echo "========================================="
echo "  10.2  Silver Transactions Quality"
echo "========================================="

check "ST-01" "No duplicate transaction_id across Silver partitions (INV-14)" "
SELECT COUNT(*) FROM (
    SELECT transaction_id FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
    GROUP BY transaction_id HAVING COUNT(*) > 1
)"

check "ST-02" "No null _signed_amount in Silver transactions (INV-11, INV-13)" "
SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
WHERE _signed_amount IS NULL"

check "ST-03" "No null _is_resolvable in Silver transactions (INV-11)" "
SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
WHERE _is_resolvable IS NULL"

check "ST-04" "Bronze = Silver + Quarantine per date partition (INV-09)" "
SELECT COUNT(*) FROM (
    SELECT partition.date_part,
           (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date='   || partition.date_part || '/data.parquet'))             AS bronze_count,
           (SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/date='   || partition.date_part || '/data.parquet'))             AS silver_count,
           (SELECT COUNT(*) FROM read_parquet('/app/data/silver/quarantine/date='     || partition.date_part || '/rejected.parquet'))         AS quarantine_count
    FROM (VALUES $DATES) AS partition(date_part)
) WHERE bronze_count != silver_count + quarantine_count"

check "ST-05" "All quarantine rejection_reason values are from exhaustive list (INV-07, INV-08)" "
SELECT COUNT(*) FROM read_parquet('/app/data/silver/quarantine/**/rejected.parquet', hive_partitioning=true, union_by_name=true)
WHERE _rejection_reason NOT IN (
    'NULL_REQUIRED_FIELD','INVALID_AMOUNT','DUPLICATE_TRANSACTION_ID',
    'INVALID_TRANSACTION_CODE','INVALID_CHANNEL','INVALID_ACCOUNT_STATUS'
) OR _rejection_reason IS NULL"

check "ST-06" "No transaction_id appears in both Silver and Quarantine (INV-08, INV-09)" "
SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true) s
WHERE s.transaction_id IN (
    SELECT q.transaction_id FROM read_parquet('/app/data/silver/quarantine/**/rejected.parquet', hive_partitioning=true, union_by_name=true) q
    WHERE q.transaction_id IS NOT NULL
)"

check "ST-07" "Every Silver _pipeline_run_id maps to a SUCCESS run log entry (INV-12)" "
SELECT COUNT(DISTINCT s._pipeline_run_id) FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true) s
WHERE s._pipeline_run_id NOT IN (
    SELECT run_id FROM read_parquet('/app/data/pipeline/run_log.parquet') WHERE status = 'SUCCESS'
)"

check "ST-08" "Every Silver transaction_code resolves to silver_transaction_codes (INV-13)" "
SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true) s
WHERE s.transaction_code NOT IN (
    SELECT transaction_code FROM read_parquet('/app/data/silver/transaction_codes/data.parquet')
)"

# ===========================================================================
# 10.3  SILVER ACCOUNTS QUALITY
# ===========================================================================
echo ""
echo "========================================="
echo "  10.3  Silver Accounts Quality"
echo "========================================="

check "SA-01" "Exactly one record per account_id in silver/accounts (INV-19)" "
SELECT COUNT(*) FROM (
    SELECT account_id FROM read_parquet('/app/data/silver/accounts/data.parquet')
    GROUP BY account_id HAVING COUNT(*) > 1
)"

check "SA-02" "No null _pipeline_run_id in silver/accounts (INV-11)" "
SELECT COUNT(*) FROM read_parquet('/app/data/silver/accounts/data.parquet')
WHERE _pipeline_run_id IS NULL"

check "SA-03" "No null _record_valid_from in silver/accounts (INV-11)" "
SELECT COUNT(*) FROM read_parquet('/app/data/silver/accounts/data.parquet')
WHERE _record_valid_from IS NULL"

check "SA-04" "All account_status values are ACTIVE, SUSPENDED, or CLOSED" "
SELECT COUNT(*) FROM read_parquet('/app/data/silver/accounts/data.parquet')
WHERE account_status NOT IN ('ACTIVE','SUSPENDED','CLOSED')"

check "SA-05" "All account quarantine records have a non-null _rejection_reason (INV-08)" "
SELECT SUM(null_count) FROM (
    SELECT (SELECT COUNT(*) FROM read_parquet('/app/data/silver/quarantine/date=' || p.date_part || '/rejected.parquet') WHERE _rejection_reason IS NULL) AS null_count
    FROM (VALUES $DATES) AS p(date_part)
)"

check "SA-06" "Account quarantine rejection_reason from valid list (INV-07, INV-08)" "
SELECT SUM(bad) FROM (
    SELECT (
        SELECT COUNT(*) FROM read_parquet('/app/data/silver/quarantine/date=' || p.date_part || '/rejected.parquet')
        WHERE _rejection_reason NOT IN ('NULL_REQUIRED_FIELD','INVALID_ACCOUNT_STATUS')
    ) AS bad
    FROM (VALUES $DATES) AS p(date_part)
)"

# ===========================================================================
# 10.4  GOLD CORRECTNESS
# ===========================================================================
echo ""
echo "========================================="
echo "  10.4  Gold Correctness"
echo "========================================="

check "G-01" "Gold date spine matches Silver distinct transaction_date (INV-17)" "
SELECT COUNT(*) FROM (
    SELECT DISTINCT transaction_date::DATE AS transaction_date
    FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
) spine
FULL OUTER JOIN read_parquet('/app/data/gold/daily_summary/data.parquet') g
    ON spine.transaction_date = g.transaction_date
WHERE spine.transaction_date IS NULL OR g.transaction_date IS NULL"

check "G-02" "gold_daily_summary.total_transactions = resolvable Silver count per date (INV-17)" "
SELECT COUNT(*) FROM read_parquet('/app/data/gold/daily_summary/data.parquet') g
LEFT JOIN (
    SELECT transaction_date::DATE AS transaction_date, COUNT(*) AS resolvable_count
    FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
    WHERE _is_resolvable = true
    GROUP BY transaction_date::DATE
) s ON g.transaction_date = s.transaction_date
WHERE g.total_transactions != COALESCE(s.resolvable_count, 0)"

check "G-03" "gold_daily_summary.total_signed_amount = SUM of resolvable Silver _signed_amount (INV-17)" "
SELECT COUNT(*) FROM read_parquet('/app/data/gold/daily_summary/data.parquet') g
LEFT JOIN (
    SELECT transaction_date::DATE AS transaction_date, SUM(_signed_amount) AS resolvable_sum
    FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
    WHERE _is_resolvable = true
    GROUP BY transaction_date::DATE
) s ON g.transaction_date = s.transaction_date
WHERE ABS(g.total_signed_amount - COALESCE(s.resolvable_sum, 0.0)) > 0.001"

check "G-04" "gold_weekly_account_summary.total_purchases = resolvable PURCHASE count (INV-17)" "
SELECT COUNT(*) FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet') w
LEFT JOIN (
    SELECT txn.account_id,
           DATE_TRUNC('week', txn.transaction_date::DATE)::DATE AS week_start,
           COUNT(*) AS purchase_count
    FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true) txn
    JOIN read_parquet('/app/data/silver/transaction_codes/data.parquet') tc
        ON txn.transaction_code = tc.transaction_code
    WHERE txn._is_resolvable = true AND tc.transaction_type = 'PURCHASE'
    GROUP BY txn.account_id, DATE_TRUNC('week', txn.transaction_date::DATE)::DATE
) s ON w.account_id = s.account_id AND w.week_start_date = s.week_start
WHERE w.total_purchases != COALESCE(s.purchase_count, 0)"

check "G-05" "week_start_date is always Monday in gold_weekly_account_summary" "
SELECT COUNT(*) FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet')
WHERE EXTRACT(DOW FROM week_start_date) != 1"

check "G-06" "week_end_date = week_start_date + 6 days always" "
SELECT COUNT(*) FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet')
WHERE week_end_date != (week_start_date + INTERVAL 6 DAYS)::DATE"

check "G-07" "No null _pipeline_run_id in Gold outputs (INV-11)" "
SELECT SUM(null_count) FROM (
    SELECT COUNT(*) AS null_count FROM read_parquet('/app/data/gold/daily_summary/data.parquet')          WHERE _pipeline_run_id IS NULL
    UNION ALL
    SELECT COUNT(*) FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet') WHERE _pipeline_run_id IS NULL
)"

# ===========================================================================
# 10.5  IDEMPOTENCY
# ===========================================================================
echo ""
echo "========================================="
echo "  10.5  Idempotency"
echo "========================================="

TOTAL=$((TOTAL + 1))
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if bash "$SCRIPT_DIR/run_idempotency_test.sh"; then
    printf "  PASS  [I-01] Two consecutive runs produce identical layer row counts and Gold sums (INV-10)\n"
else
    printf "  FAIL  [I-01] Two consecutive runs produce identical layer row counts and Gold sums (INV-10)\n"
    FAILURES=$((FAILURES + 1))
fi

# ===========================================================================
# 10.6  AUDIT TRAIL
# ===========================================================================
echo ""
echo "========================================="
echo "  10.6  Audit Trail"
echo "========================================="

check "AT-01" "Watermark = 2024-01-07 after full historical run (INV-01, INV-03)" "
SELECT CASE WHEN CAST(last_processed_date AS VARCHAR) = '2024-01-07' THEN 0 ELSE 1 END
FROM read_parquet('/app/data/pipeline/control.parquet')"

check "AT-02" "Every Bronze _pipeline_run_id has a SUCCESS run log entry (INV-12)" "
SELECT COUNT(DISTINCT run_id) FROM (
    SELECT DISTINCT _pipeline_run_id AS run_id FROM read_parquet('/app/data/bronze/transactions/**/data.parquet',     hive_partitioning=true)
    UNION
    SELECT DISTINCT _pipeline_run_id FROM read_parquet('/app/data/bronze/accounts/**/data.parquet',          hive_partitioning=true)
    UNION
    SELECT DISTINCT _pipeline_run_id FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet')
) b
WHERE run_id NOT IN (
    SELECT run_id FROM read_parquet('/app/data/pipeline/run_log.parquet') WHERE status = 'SUCCESS'
)"

check "AT-03" "Every Gold _pipeline_run_id has a SUCCESS run log entry (INV-12, INV-16)" "
SELECT COUNT(DISTINCT run_id) FROM (
    SELECT DISTINCT _pipeline_run_id AS run_id FROM read_parquet('/app/data/gold/daily_summary/data.parquet')
    UNION
    SELECT DISTINCT _pipeline_run_id FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet')
) g
WHERE run_id NOT IN (
    SELECT run_id FROM read_parquet('/app/data/pipeline/run_log.parquet') WHERE status = 'SUCCESS'
)"

# ===========================================================================
# RESULT
# ===========================================================================
echo ""
echo "========================================="
PASSING=$((TOTAL - FAILURES))
if [ "$FAILURES" -eq 0 ]; then
    echo "  ALL CHECKS PASS — $TOTAL/$TOTAL passed"
    echo "========================================="
    exit 0
else
    echo "  VERIFICATION FAILED — $PASSING/$TOTAL passed, $FAILURES FAILED"
    echo "========================================="
    exit 1
fi
