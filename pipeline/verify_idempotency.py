"""
End-to-end idempotency verification (I-06).

Captures row counts across all layers, attempts a historical pipeline re-run
(expecting exit 1 from the watermark guard), then confirms all counts are
unchanged. The watermark guard firing IS the expected behaviour — it confirms
the pipeline protects data from being re-processed once complete.
"""
import subprocess
import sys
import duckdb


def count(query: str) -> int:
    try:
        return duckdb.connect().execute(query).fetchone()[0]
    except Exception:
        return -1


def snapshot_counts() -> dict:
    return {
        "bronze_txn": count(
            "SELECT COUNT(*) FROM read_parquet('data/bronze/transactions/**/*.parquet')"
        ),
        "bronze_acct": count(
            "SELECT COUNT(*) FROM read_parquet('data/bronze/accounts/**/*.parquet')"
        ),
        "bronze_codes": count(
            "SELECT COUNT(*) FROM read_parquet('data/bronze/transaction_codes/data.parquet')"
        ),
        "silver_txn": count(
            "SELECT COUNT(*) FROM read_parquet('data/silver/transactions/**/*.parquet')"
        ),
        "silver_acct": count(
            "SELECT COUNT(*) FROM read_parquet('data/silver/accounts/data.parquet')"
        ),
        "quarantine": count(
            "SELECT COUNT(*) FROM read_parquet('data/silver/quarantine/**/*.parquet')"
        ),
        "gold_daily_rows": count(
            "SELECT COUNT(*) FROM read_parquet('data/gold/daily_summary/data.parquet')"
        ),
        "gold_daily_txns": count(
            "SELECT SUM(total_transactions) FROM read_parquet('data/gold/daily_summary/data.parquet')"
        ),
        "gold_weekly_rows": count(
            "SELECT COUNT(*) FROM read_parquet('data/gold/weekly_account_summary/data.parquet')"
        ),
    }


def main():
    print("Idempotency verification (I-06)\n")

    print("Capturing counts before re-run attempt...")
    before = snapshot_counts()
    for k, v in before.items():
        print(f"  {k}: {v}")

    print("\nAttempting historical pipeline re-run (watermark guard expected)...")
    result = subprocess.run(
        ["python", "/app/pipeline/pipeline_historical.py",
         "--start-date", "2024-01-01", "--end-date", "2024-01-07"],
        capture_output=True, text=True
    )
    print(f"  exit code: {result.returncode}")
    print(f"  stdout: {result.stdout[:300]}")

    if result.returncode != 1:
        print("FAIL: expected exit code 1 from watermark guard — pipeline may have run")
        sys.exit(1)
    if "watermark already exists" not in result.stdout:
        print("FAIL: watermark guard message not found — unexpected failure mode")
        sys.exit(1)
    print("  watermark guard fired correctly")

    print("\nCapturing counts after re-run attempt...")
    after = snapshot_counts()
    for k, v in after.items():
        print(f"  {k}: {v}")

    print("\nComparing counts:")
    all_pass = True
    for key in before:
        b, a = before[key], after[key]
        match = b == a
        status = "PASS" if match else "FAIL"
        print(f"  {status}: {key}  before={b}  after={a}")
        if not match:
            all_pass = False

    print()
    if all_pass:
        print("All idempotency checks: PASS")
        sys.exit(0)
    else:
        print("One or more idempotency checks: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
