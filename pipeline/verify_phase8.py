"""
Phase 8 sign-off verification suite.

Runs all 16 checks from requirements brief Section 10 in order.
Every check prints CHECK [n]: [description] — PASS or FAIL.
Exits 0 only if all checks pass.

This script's output is the documented Phase 8 sign-off record.
"""
import os
import sys
import subprocess
import duckdb

SOURCE_DIR = "source"
VALID_REJECTION_CODES = {
    "NULL_REQUIRED_FIELD", "INVALID_AMOUNT", "DUPLICATE_TRANSACTION_ID",
    "INVALID_TRANSACTION_CODE", "INVALID_CHANNEL", "INVALID_ACCOUNT_STATUS",
}


def q(sql: str):
    try:
        return duckdb.connect().execute(sql).fetchone()[0]
    except Exception as e:
        return f"ERROR: {e}"


def source_count(filename: str) -> int:
    path = os.path.join(SOURCE_DIR, filename)
    if not os.path.exists(path):
        return -1
    return q(f"SELECT COUNT(*) FROM read_csv_auto('{path}')")


results = []


def check(n: str, desc: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    line = f"CHECK {n}: {desc} — {status}"
    if detail:
        line += f"  [{detail}]"
    print(line)
    results.append(passed)
    return passed


def main():
    print("Phase 8 Sign-Off Verification Suite\n")

    # ── §10.1 BRONZE COMPLETENESS ────────────────────────────────────────────

    print("§10.1 Bronze completeness")

    # B-1: Bronze transactions = sum of 7 source CSVs
    src_txn_total = sum(
        source_count(f"transactions_2024-01-0{i}.csv") for i in range(1, 8)
    )
    brz_txn_total = q(
        "SELECT COUNT(*) FROM read_parquet('data/bronze/transactions/**/*.parquet')"
    )
    check("B-1", "Bronze transactions = source CSV total",
          src_txn_total == brz_txn_total,
          f"source={src_txn_total}, bronze={brz_txn_total}")

    # B-2: Bronze accounts = sum of 7 source CSVs
    src_acct_total = sum(
        source_count(f"accounts_2024-01-0{i}.csv") for i in range(1, 8)
    )
    brz_acct_total = q(
        "SELECT COUNT(*) FROM read_parquet('data/bronze/accounts/**/*.parquet')"
    )
    check("B-2", "Bronze accounts = source CSV total",
          src_acct_total == brz_acct_total,
          f"source={src_acct_total}, bronze={brz_acct_total}")

    # B-3: Bronze transaction_codes = source CSV
    src_codes = source_count("transaction_codes.csv")
    brz_codes = q(
        "SELECT COUNT(*) FROM read_parquet('data/bronze/transaction_codes/data.parquet')"
    )
    check("B-3", "Bronze transaction_codes = source CSV",
          src_codes == brz_codes,
          f"source={src_codes}, bronze={brz_codes}")

    # ── §10.2 SILVER QUALITY ─────────────────────────────────────────────────

    print("\n§10.2 Silver quality")

    # S-1: Silver + quarantine = Bronze (all partitions, I-01)
    violations = q("""
        SELECT COUNT(*) FROM (
            SELECT regexp_extract(filename,'date=([0-9\\-]+)',1) AS dp, COUNT(*) AS bc
            FROM read_parquet('data/bronze/transactions/**/*.parquet', filename=true)
            GROUP BY dp
        ) b
        JOIN (
            SELECT regexp_extract(filename,'date=([0-9\\-]+)',1) AS dp, COUNT(*) AS sc
            FROM read_parquet('data/silver/transactions/**/*.parquet', filename=true)
            GROUP BY dp
        ) s USING (dp)
        JOIN (
            SELECT regexp_extract(filename,'date=([0-9\\-]+)',1) AS dp, COUNT(*) AS qc
            FROM read_parquet('data/silver/quarantine/**/*.parquet', filename=true)
            GROUP BY dp
        ) q USING (dp)
        WHERE bc != sc + qc
    """)
    check("S-1", "Silver + quarantine = Bronze (I-01)", violations == 0,
          f"violations={violations}")

    # S-2: No duplicate transaction_id in Silver (I-06)
    dups = q("""
        SELECT COUNT(*) FROM (
            SELECT transaction_id, COUNT(*) AS n
            FROM read_parquet('data/silver/transactions/**/*.parquet')
            GROUP BY transaction_id HAVING n > 1
        )
    """)
    check("S-2", "No duplicate transaction_id in Silver (I-06)", dups == 0,
          f"duplicates={dups}")

    # S-3: Every Silver transaction has valid transaction_code
    invalid_codes = q("""
        SELECT COUNT(*) FROM read_parquet('data/silver/transactions/**/*.parquet') t
        LEFT JOIN read_parquet('data/silver/transaction_codes/data.parquet') tc
          ON t.transaction_code = tc.transaction_code
        WHERE tc.transaction_code IS NULL
    """)
    check("S-3", "Every Silver transaction has valid transaction_code",
          invalid_codes == 0, f"invalid={invalid_codes}")

    # S-4: No null _signed_amount (I-10)
    null_signed = q("""
        SELECT COUNT(*) FROM read_parquet('data/silver/transactions/**/*.parquet')
        WHERE _signed_amount IS NULL
    """)
    check("S-4", "No null _signed_amount in Silver (I-10)", null_signed == 0,
          f"null_count={null_signed}")

    # S-5: Every quarantine record has valid _rejection_reason (I-15)
    con = duckdb.connect()
    reasons = con.execute("""
        SELECT DISTINCT _rejection_reason
        FROM read_parquet('data/silver/quarantine/**/*.parquet')
    """).fetchall()
    invalid_reasons = [r[0] for r in reasons
                       if r[0] not in VALID_REJECTION_CODES and r[0] is not None]
    null_reasons = q("""
        SELECT COUNT(*) FROM read_parquet('data/silver/quarantine/**/*.parquet')
        WHERE _rejection_reason IS NULL
    """)
    check("S-5", "All quarantine _rejection_reason values valid (I-15)",
          not invalid_reasons and null_reasons == 0,
          f"invalid={invalid_reasons}, null={null_reasons}")

    # ── §10.3 GOLD CORRECTNESS ───────────────────────────────────────────────

    print("\n§10.3 Gold correctness")

    # G-1: Gold daily has one row per date where _is_resolvable=true in Silver
    silver_dates = q("""
        SELECT COUNT(DISTINCT transaction_date)
        FROM read_parquet('data/silver/transactions/**/*.parquet')
        WHERE _is_resolvable = true
    """)
    gold_dates = q(
        "SELECT COUNT(*) FROM read_parquet('data/gold/daily_summary/data.parquet')"
    )
    check("G-1", "Gold daily: one row per resolvable date (I-04)",
          silver_dates == gold_dates,
          f"silver_dates={silver_dates}, gold_rows={gold_dates}")

    # G-2: Gold weekly total_purchases matches Silver COUNT per (account, week)
    purchase_mismatches = q("""
        SELECT COUNT(*) FROM (
            SELECT g.account_id, g.week_start_date,
                   g.total_purchases, s.sc
            FROM read_parquet('data/gold/weekly_account_summary/data.parquet') g
            JOIN (
                SELECT t.account_id,
                       DATE_TRUNC('week', t.transaction_date) AS wsd,
                       COUNT(*) AS sc
                FROM read_parquet('data/silver/transactions/**/*.parquet') t
                JOIN read_parquet('data/silver/transaction_codes/data.parquet') tc
                  ON t.transaction_code = tc.transaction_code
                WHERE t._is_resolvable = true AND tc.transaction_type = 'PURCHASE'
                GROUP BY t.account_id, DATE_TRUNC('week', t.transaction_date)
            ) s ON g.account_id = s.account_id AND g.week_start_date = s.wsd
            WHERE g.total_purchases != s.sc
        )
    """)
    check("G-2", "Gold weekly total_purchases matches Silver (I-05)",
          purchase_mismatches == 0, f"mismatches={purchase_mismatches}")

    # G-3: Gold total_signed_amount per day matches Silver SUM
    amount_mismatches = q("""
        SELECT COUNT(*) FROM (
            SELECT g.transaction_date,
                   ABS(g.total_signed_amount - s.ss) AS delta
            FROM read_parquet('data/gold/daily_summary/data.parquet') g
            JOIN (
                SELECT transaction_date, SUM(_signed_amount) AS ss
                FROM read_parquet('data/silver/transactions/**/*.parquet')
                WHERE _is_resolvable = true
                GROUP BY transaction_date
            ) s ON g.transaction_date = s.transaction_date
            WHERE ABS(g.total_signed_amount - s.ss) >= 0.0001
        )
    """)
    check("G-3", "Gold total_signed_amount matches Silver SUM (I-04)",
          amount_mismatches == 0, f"mismatches={amount_mismatches}")

    # ── §10.4 IDEMPOTENCY ────────────────────────────────────────────────────

    print("\n§10.4 Idempotency")

    before_brz = q(
        "SELECT COUNT(*) FROM read_parquet('data/bronze/transactions/**/*.parquet')"
    )
    before_slv = q(
        "SELECT COUNT(*) FROM read_parquet('data/silver/transactions/**/*.parquet')"
    )
    before_gld = q(
        "SELECT COUNT(*) FROM read_parquet('data/gold/daily_summary/data.parquet')"
    )

    rerun = subprocess.run(
        ["python", "/app/pipeline/pipeline_historical.py",
         "--start-date", "2024-01-01", "--end-date", "2024-01-07"],
        capture_output=True, text=True
    )
    guard_fired = rerun.returncode == 1 and "watermark already exists" in rerun.stdout

    after_brz = q(
        "SELECT COUNT(*) FROM read_parquet('data/bronze/transactions/**/*.parquet')"
    )
    after_slv = q(
        "SELECT COUNT(*) FROM read_parquet('data/silver/transactions/**/*.parquet')"
    )
    after_gld = q(
        "SELECT COUNT(*) FROM read_parquet('data/gold/daily_summary/data.parquet')"
    )

    check("I-1", "Bronze row counts identical after re-run (I-06)",
          guard_fired and before_brz == after_brz,
          f"before={before_brz}, after={after_brz}, guard={guard_fired}")
    check("I-2", "Silver row counts identical after re-run (I-06)",
          guard_fired and before_slv == after_slv,
          f"before={before_slv}, after={after_slv}")
    check("I-3", "Gold output identical after re-run (I-06)",
          guard_fired and before_gld == after_gld,
          f"before={before_gld}, after={after_gld}")

    # ── §10.5 AUDIT TRAIL ────────────────────────────────────────────────────

    print("\n§10.5 Audit trail")

    # A-1: Bronze _pipeline_run_id non-null (I-14)
    brz_null = q("""
        SELECT COUNT(*) FROM read_parquet('data/bronze/transactions/**/*.parquet')
        WHERE _pipeline_run_id IS NULL OR _source_file IS NULL OR _ingested_at IS NULL
    """)
    check("A-1", "Every Bronze record has non-null audit columns (I-14)",
          brz_null == 0, f"null_count={brz_null}")

    # A-2: Silver _pipeline_run_id non-null (I-14)
    slv_null = q("""
        SELECT COUNT(*) FROM read_parquet('data/silver/transactions/**/*.parquet')
        WHERE _pipeline_run_id IS NULL OR _promoted_at IS NULL
          OR _source_file IS NULL OR _bronze_ingested_at IS NULL
    """)
    check("A-2", "Every Silver record has non-null audit columns (I-14)",
          slv_null == 0, f"null_count={slv_null}")

    # A-3: Gold _pipeline_run_id non-null (I-14)
    gld_null = q("""
        SELECT COUNT(*) FROM read_parquet('data/gold/daily_summary/data.parquet')
        WHERE _pipeline_run_id IS NULL OR _computed_at IS NULL
    """)
    check("A-3", "Every Gold record has non-null audit columns (I-14)",
          gld_null == 0, f"null_count={gld_null}")

    # A-4: Every Silver _pipeline_run_id has SUCCESS in run log (I-07)
    unmatched_run_ids = q("""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT _pipeline_run_id
            FROM read_parquet('data/silver/transactions/**/*.parquet')
        ) s
        LEFT JOIN (
            SELECT DISTINCT run_id
            FROM read_parquet('data/pipeline/run_log.parquet')
            WHERE status = 'SUCCESS'
        ) rl ON s._pipeline_run_id = rl.run_id
        WHERE rl.run_id IS NULL
    """)
    check("A-4", "Every Silver _pipeline_run_id has SUCCESS in run log (I-07)",
          unmatched_run_ids == 0, f"unmatched={unmatched_run_ids}")

    # ── SUMMARY ──────────────────────────────────────────────────────────────

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")

    if passed == total:
        print("Phase 8 sign-off: PASS")
        sys.exit(0)
    else:
        print("Phase 8 sign-off: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
