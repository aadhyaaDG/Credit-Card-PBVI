"""
Gold layer verification script.
Runs all Gold invariant checks in sequence.
Exits 1 if any check fails.
"""
import sys
import duckdb


def check(label, query, expect_zero=True):
    con = duckdb.connect()
    result = con.execute(query).fetchone()[0]
    passed = (result == 0) if expect_zero else bool(result)
    status = "PASS" if passed else "FAIL"
    print(f"  {status}: {label} (value={result})")
    return passed


def main():
    all_pass = True
    print("Gold verification\n")

    # 1 — I-04: Gold daily count matches Silver per date
    print("Check 1: Gold daily count matches Silver (I-04)")
    ok = check("daily count mismatches", """
        SELECT COUNT(*) FROM (
            SELECT g.transaction_date,
                   g.total_transactions AS gold_count,
                   s.silver_count,
                   g.total_transactions = s.silver_count AS match
            FROM read_parquet('data/gold/daily_summary/data.parquet') g
            JOIN (
                SELECT transaction_date, COUNT(*) AS silver_count
                FROM read_parquet('data/silver/transactions/**/*.parquet')
                WHERE _is_resolvable = true
                GROUP BY transaction_date
            ) s ON g.transaction_date = s.transaction_date
            WHERE g.total_transactions != s.silver_count
        )
    """)
    if not ok: all_pass = False

    # 2 — I-05: total_purchases matches Silver COUNT per (account, week)
    print("Check 2: Weekly total_purchases matches Silver (I-05)")
    ok = check("total_purchases mismatches", """
        SELECT COUNT(*) FROM (
            SELECT g.account_id, g.week_start_date,
                   g.total_purchases, s.silver_count
            FROM read_parquet('data/gold/weekly_account_summary/data.parquet') g
            JOIN (
                SELECT t.account_id,
                       DATE_TRUNC('week', t.transaction_date) AS week_start_date,
                       COUNT(*) AS silver_count
                FROM read_parquet('data/silver/transactions/**/*.parquet') t
                JOIN read_parquet('data/silver/transaction_codes/data.parquet') tc
                  ON t.transaction_code = tc.transaction_code
                WHERE t._is_resolvable = true AND tc.transaction_type = 'PURCHASE'
                GROUP BY t.account_id, DATE_TRUNC('week', t.transaction_date)
            ) s ON g.account_id = s.account_id AND g.week_start_date = s.week_start_date
            WHERE g.total_purchases != s.silver_count
        )
    """)
    if not ok: all_pass = False

    # 3 — I-17: no unresolvable source in Gold daily
    print("Check 3: No unresolvable records in Gold daily (I-17)")
    ok = check("Gold count inflation vs resolvable Silver", """
        SELECT COUNT(*) FROM (
            SELECT g.transaction_date,
                   g.total_transactions AS gold_count,
                   s.resolvable_count
            FROM read_parquet('data/gold/daily_summary/data.parquet') g
            JOIN (
                SELECT transaction_date, COUNT(*) AS resolvable_count
                FROM read_parquet('data/silver/transactions/**/*.parquet')
                WHERE _is_resolvable = true
                GROUP BY transaction_date
            ) s ON g.transaction_date = s.transaction_date
            WHERE g.total_transactions != s.resolvable_count
        )
    """)
    if not ok: all_pass = False

    # 4 — I-14: audit column completeness Gold daily
    print("Check 4: Audit column completeness Gold daily (I-14)")
    ok = check("null audit cols in gold/daily_summary", """
        SELECT COUNT(*) FROM read_parquet('data/gold/daily_summary/data.parquet')
        WHERE _pipeline_run_id IS NULL OR _computed_at IS NULL
    """)
    if not ok: all_pass = False

    # 4b — I-14: audit column completeness Gold weekly
    print("Check 4b: Audit column completeness Gold weekly (I-14)")
    ok = check("null audit cols in gold/weekly_account_summary", """
        SELECT COUNT(*) FROM read_parquet('data/gold/weekly_account_summary/data.parquet')
        WHERE _pipeline_run_id IS NULL OR _computed_at IS NULL
    """)
    if not ok: all_pass = False

    # 5 — I-04: one row per date in Gold daily
    print("Check 5: One row per date in Gold daily (I-04)")
    ok = check("duplicate dates in Gold daily", """
        SELECT COUNT(*) FROM (
            SELECT transaction_date, COUNT(*) AS n
            FROM read_parquet('data/gold/daily_summary/data.parquet')
            GROUP BY transaction_date HAVING n > 1
        )
    """)
    if not ok: all_pass = False

    print()
    if all_pass:
        print("All Gold checks: PASS")
        sys.exit(0)
    else:
        print("One or more Gold checks: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
