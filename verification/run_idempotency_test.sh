#!/usr/bin/env bash
# verification/run_idempotency_test.sh
# End-to-end idempotency test (INV-10, Section 10.4).
#
# Runs the historical pipeline twice over the same date range and asserts
# that all layer row counts and Gold sums are identical between the two runs.
#
# Usage (inside container):
#   bash /app/verification/run_idempotency_test.sh
#
# Usage (via docker compose):
#   docker compose exec pipeline bash /app/verification/run_idempotency_test.sh

set -euo pipefail

PIPELINE="python /app/pipeline.py"
START_DATE="2024-01-01"
END_DATE="2024-01-07"

# ---------------------------------------------------------------------------
# Helper: run a DuckDB SQL statement via Python and return a single scalar.
# Handles missing files (returns 0 instead of erroring out).
# ---------------------------------------------------------------------------
run_query() {
    DUCKDB_QUERY="$1" python3 - << 'PYEOF'
import duckdb, os, sys
sql = os.environ["DUCKDB_QUERY"]
try:
    result = duckdb.sql(sql).fetchone()
    print(result[0] if result and result[0] is not None else 0)
except Exception:
    print(0)
PYEOF
}

# ---------------------------------------------------------------------------
# Helper: capture all metrics into variables with a given suffix (1 or 2).
# ---------------------------------------------------------------------------
capture_metrics() {
    local suffix="$1"

    eval "BRONZE_TXN_${suffix}=$(run_query "SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/**/data.parquet', hive_partitioning=true)")"
    eval "BRONZE_ACC_${suffix}=$(run_query "SELECT COUNT(*) FROM read_parquet('/app/data/bronze/accounts/**/data.parquet', hive_partitioning=true)")"
    eval "BRONZE_TC_${suffix}=$(run_query "SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet')")"
    eval "SILVER_TXN_${suffix}=$(run_query "SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)")"
    eval "SILVER_ACC_${suffix}=$(run_query "SELECT COUNT(*) FROM read_parquet('/app/data/silver/accounts/data.parquet')")"
    eval "QUARANTINE_${suffix}=$(run_query "SELECT COUNT(*) FROM read_parquet('/app/data/silver/quarantine/**/rejected.parquet', hive_partitioning=true, union_by_name=true)")"
    eval "GOLD_DAILY_ROWS_${suffix}=$(run_query "SELECT COUNT(*) FROM read_parquet('/app/data/gold/daily_summary/data.parquet')")"
    eval "GOLD_DAILY_SUM_${suffix}=$(run_query "SELECT COALESCE(SUM(total_signed_amount), 0) FROM read_parquet('/app/data/gold/daily_summary/data.parquet')")"
    eval "GOLD_WEEKLY_ROWS_${suffix}=$(run_query "SELECT COUNT(*) FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet')")"
    eval "WATERMARK_${suffix}=$(run_query "SELECT CAST(last_processed_date AS VARCHAR) FROM read_parquet('/app/data/pipeline/control.parquet')")"
}

# ---------------------------------------------------------------------------
# Helper: compare two values and record pass/fail.
# ---------------------------------------------------------------------------
FAILURES=0

check() {
    local label="$1"
    local val1="$2"
    local val2="$3"
    if [ "$val1" = "$val2" ]; then
        echo "  PASS  $label: $val1"
    else
        echo "  FAIL  $label: run1=$val1  run2=$val2"
        FAILURES=$((FAILURES + 1))
    fi
}

# ===========================================================================
# Run 1
# ===========================================================================
echo ""
echo "========================================="
echo "  Run 1 — historical $START_DATE → $END_DATE"
echo "========================================="
$PIPELINE historical --start-date "$START_DATE" --end-date "$END_DATE"

echo ""
echo "Capturing metrics after run 1..."
capture_metrics 1

# ===========================================================================
# Run 2 (same range — must produce identical output)
# ===========================================================================
echo ""
echo "========================================="
echo "  Run 2 — historical $START_DATE → $END_DATE (idempotency check)"
echo "========================================="
$PIPELINE historical --start-date "$START_DATE" --end-date "$END_DATE"

echo ""
echo "Capturing metrics after run 2..."
capture_metrics 2

# ===========================================================================
# Assertions
# ===========================================================================
echo ""
echo "========================================="
echo "  Comparison"
echo "========================================="

check "bronze_transactions rows" "$BRONZE_TXN_1" "$BRONZE_TXN_2"
check "bronze_accounts rows    " "$BRONZE_ACC_1" "$BRONZE_ACC_2"
check "bronze_tc rows          " "$BRONZE_TC_1"  "$BRONZE_TC_2"
check "silver_transactions rows" "$SILVER_TXN_1" "$SILVER_TXN_2"
check "silver_accounts rows    " "$SILVER_ACC_1" "$SILVER_ACC_2"
check "quarantine rows         " "$QUARANTINE_1" "$QUARANTINE_2"
check "gold_daily rows         " "$GOLD_DAILY_ROWS_1" "$GOLD_DAILY_ROWS_2"
check "gold_daily signed_sum   " "$GOLD_DAILY_SUM_1"  "$GOLD_DAILY_SUM_2"
check "gold_weekly rows        " "$GOLD_WEEKLY_ROWS_1" "$GOLD_WEEKLY_ROWS_2"
check "watermark               " "$WATERMARK_1" "$WATERMARK_2"

# ===========================================================================
# Result
# ===========================================================================
echo ""
echo "========================================="
if [ "$FAILURES" -eq 0 ]; then
    echo "  IDEMPOTENCY PASS — all $((10)) checks matched"
    echo "========================================="
    exit 0
else
    echo "  IDEMPOTENCY FAIL — $FAILURES check(s) did not match"
    echo "========================================="
    exit 1
fi
