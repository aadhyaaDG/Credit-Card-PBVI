#!/usr/bin/env python3
"""
verify_silver.py — Silver layer verification script.
Checks all Silver invariants across all processed date partitions.
Exits 0 if all checks pass, 1 if any fail.

Invariants checked:
  I-01  Conservation law: bronze == silver + quarantine per date
  I-10  No null _signed_amount in silver/transactions
  I-13  _is_resolvable correctly set (all records have true or false, never null)
  I-14  Audit column completeness (non-null _pipeline_run_id, _promoted_at, _source_file, _bronze_ingested_at)
  I-15  Rejection reason validity in quarantine
  I-11  Exactly one row per account_id in silver/accounts
"""

import sys
import duckdb

VALID_TX_REJECTION_REASONS = {
    'NULL_REQUIRED_FIELD',
    'INVALID_AMOUNT',
    'DUPLICATE_TRANSACTION_ID',
    'INVALID_TRANSACTION_CODE',
    'INVALID_CHANNEL',
}

BRONZE_TX_PATH = '/app/data/bronze/transactions/**/*.parquet'
SILVER_TX_PATH = '/app/data/silver/transactions/**/*.parquet'
QUARANTINE_PATH = '/app/data/silver/quarantine/**/*.parquet'
SILVER_ACCOUNTS_PATH = '/app/data/silver/accounts/data.parquet'


def check(name, condition, detail=''):
    if condition:
        print(f'  PASS  {name}')
    else:
        print(f'  FAIL  {name}{": " + detail if detail else ""}')
    return condition


def main():
    con = duckdb.connect()
    failures = []

    print('=== Silver Verification ===')
    print()

    # -------------------------------------------------------------------------
    # I-01: Conservation law per date
    # -------------------------------------------------------------------------
    print('--- I-01: Conservation law (bronze == silver + quarantine per date) ---')
    rows = con.execute(f"""
        SELECT
            b.processing_date,
            b.bronze_count,
            COALESCE(s.silver_count, 0) AS silver_count,
            COALESCE(q.quarantine_count, 0) AS quarantine_count,
            b.bronze_count - COALESCE(s.silver_count, 0) - COALESCE(q.quarantine_count, 0) AS delta
        FROM (
            SELECT regexp_extract(filename, 'date=([0-9-]+)', 1) AS processing_date,
                   COUNT(*) AS bronze_count
            FROM read_parquet('{BRONZE_TX_PATH}', filename=true)
            GROUP BY processing_date
        ) b
        LEFT JOIN (
            SELECT regexp_extract(filename, 'date=([0-9-]+)', 1) AS processing_date,
                   COUNT(*) AS silver_count
            FROM read_parquet('{SILVER_TX_PATH}', filename=true)
            GROUP BY processing_date
        ) s ON b.processing_date = s.processing_date
        LEFT JOIN (
            SELECT regexp_extract(filename, 'date=([0-9-]+)', 1) AS processing_date,
                   COUNT(*) AS quarantine_count
            FROM read_parquet('{QUARANTINE_PATH}', filename=true)
            GROUP BY processing_date
        ) q ON b.processing_date = q.processing_date
        ORDER BY b.processing_date
    """).fetchall()

    all_conservation_ok = True
    for row in rows:
        date, bronze, silver, quarantine, delta = row
        ok = delta == 0
        label = f'date={date} bronze={bronze} silver={silver} quarantine={quarantine} delta={delta}'
        if not check(label, ok):
            all_conservation_ok = False
    if not all_conservation_ok:
        failures.append('I-01')
    print()

    # -------------------------------------------------------------------------
    # I-10: No null _signed_amount
    # -------------------------------------------------------------------------
    print('--- I-10: No null _signed_amount ---')
    null_signed = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{SILVER_TX_PATH}')
        WHERE _signed_amount IS NULL
    """).fetchone()[0]
    if not check('null _signed_amount == 0', null_signed == 0, f'found {null_signed}'):
        failures.append('I-10')
    print()

    # -------------------------------------------------------------------------
    # I-13: _is_resolvable never null
    # -------------------------------------------------------------------------
    print('--- I-13: _is_resolvable never null ---')
    null_resolvable = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{SILVER_TX_PATH}')
        WHERE _is_resolvable IS NULL
    """).fetchone()[0]
    if not check('null _is_resolvable == 0', null_resolvable == 0, f'found {null_resolvable}'):
        failures.append('I-13')
    print()

    # -------------------------------------------------------------------------
    # I-14: Audit column completeness in silver/transactions
    # -------------------------------------------------------------------------
    print('--- I-14: Audit column completeness (silver/transactions) ---')
    null_audits = con.execute(f"""
        SELECT
            COUNT(*) FILTER (WHERE _pipeline_run_id IS NULL) AS null_run_id,
            COUNT(*) FILTER (WHERE _promoted_at IS NULL) AS null_promoted_at,
            COUNT(*) FILTER (WHERE _source_file IS NULL) AS null_source_file,
            COUNT(*) FILTER (WHERE _bronze_ingested_at IS NULL) AS null_bronze_ingested_at
        FROM read_parquet('{SILVER_TX_PATH}')
    """).fetchone()
    audit_ok = True
    for col, val in zip(['_pipeline_run_id', '_promoted_at', '_source_file', '_bronze_ingested_at'], null_audits):
        if not check(f'null {col} == 0', val == 0, f'found {val}'):
            audit_ok = False
    if not audit_ok:
        failures.append('I-14')
    print()

    # -------------------------------------------------------------------------
    # I-15: Rejection reason validity
    # -------------------------------------------------------------------------
    print('--- I-15: Rejection reason validity ---')
    reasons = con.execute(f"""
        SELECT DISTINCT _rejection_reason FROM read_parquet('{QUARANTINE_PATH}')
    """).fetchall()
    all_valid = True
    for (reason,) in reasons:
        ok = reason in VALID_TX_REJECTION_REASONS
        if not check(f'reason "{reason}" is valid', ok):
            all_valid = False
    null_reason = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{QUARANTINE_PATH}')
        WHERE _rejection_reason IS NULL
    """).fetchone()[0]
    if not check('null _rejection_reason == 0', null_reason == 0, f'found {null_reason}'):
        all_valid = False
    # UNRESOLVABLE_ACCOUNT_ID must never appear
    bad_reason = con.execute(f"""
        SELECT COUNT(*) FROM read_parquet('{QUARANTINE_PATH}')
        WHERE _rejection_reason = 'UNRESOLVABLE_ACCOUNT_ID'
    """).fetchone()[0]
    if not check('UNRESOLVABLE_ACCOUNT_ID not in quarantine', bad_reason == 0, f'found {bad_reason}'):
        all_valid = False
    if not all_valid:
        failures.append('I-15')
    print()

    # -------------------------------------------------------------------------
    # I-11: Exactly one row per account_id in silver/accounts
    # -------------------------------------------------------------------------
    print('--- I-11: One row per account_id in silver/accounts ---')
    dups = con.execute(f"""
        SELECT account_id, COUNT(*) AS cnt
        FROM read_parquet('{SILVER_ACCOUNTS_PATH}')
        GROUP BY account_id
        HAVING COUNT(*) > 1
    """).fetchall()
    if not check('no duplicate account_id in silver/accounts', len(dups) == 0,
                 f'{len(dups)} duplicates found'):
        failures.append('I-11')
    print()

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    if failures:
        print(f'RESULT: FAILED — invariants violated: {", ".join(failures)}')
        sys.exit(1)
    else:
        print('RESULT: PASSED — all Silver invariants hold')
        sys.exit(0)


if __name__ == '__main__':
    main()
