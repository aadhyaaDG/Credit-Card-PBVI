# Verification Checklist — Phase 8 Sign-Off

| Field | Value |
|---|---|
| Project | Credit-Card PBVI Pipeline |
| Session | S8 |
| Branch | session/s08_verification_signoff |
| Engineer | Aadhya Subhash |
| Date | 2026-04-09 |

Run `docker compose exec pipeline bash verification/run_all_checks.sh` before completing this checklist.
Record the result of each check as **PASS** or **FAIL**. Sign off only when every row shows PASS.

---

## Section 10.1 — Bronze Completeness

| Check ID | Invariant(s) | Description | Script Check | Result | Signed Off |
|---|---|---|---|---|---|
| B-01 | INV-05 | Bronze transactions row count = source CSV row count for all 7 partitions | `run_all_checks.sh` B-01 | PASS | ✓ |
| B-02 | INV-05 | Bronze accounts row count = source CSV row count for all 7 partitions | `run_all_checks.sh` B-02 | PASS | ✓ |
| B-03 | INV-05 | Bronze transaction_codes row count = source CSV row count | `run_all_checks.sh` B-03 | PASS | ✓ |
| B-04 | INV-11 | No null `_pipeline_run_id` in any Bronze file | `run_all_checks.sh` B-04 | PASS | ✓ |
| B-05 | INV-06 | No negative `amount` values in Bronze transactions | `run_all_checks.sh` B-05 | PASS | ✓ |

---

## Section 10.2 — Silver Transactions Quality

| Check ID | Invariant(s) | Description | Script Check | Result | Signed Off |
|---|---|---|---|---|---|
| ST-01 | INV-14 | No duplicate `transaction_id` across all Silver transaction partitions | `run_all_checks.sh` ST-01 | PASS | ✓ |
| ST-02 | INV-11, INV-13 | No null `_signed_amount` in Silver transactions | `run_all_checks.sh` ST-02 | PASS | ✓ |
| ST-03 | INV-11 | No null `_is_resolvable` in Silver transactions | `run_all_checks.sh` ST-03 | PASS | ✓ |
| ST-04 | INV-09 | Bronze = Silver + Quarantine for each of the 7 date partitions | `run_all_checks.sh` ST-04 | PASS | ✓ |
| ST-05 | INV-07, INV-08 | All quarantine `_rejection_reason` values are from the exhaustive code list | `run_all_checks.sh` ST-05 | PASS | ✓ |
| ST-06 | INV-08, INV-09 | No `transaction_id` appears in both Silver and Quarantine | `run_all_checks.sh` ST-06 | PASS | ✓ |
| ST-07 | INV-12 | Every Silver `_pipeline_run_id` has a corresponding SUCCESS entry in the run log | `run_all_checks.sh` ST-07 | PASS | ✓ |
| ST-08 | INV-13, INV-15 | Every Silver `transaction_code` resolves to a record in `silver_transaction_codes` | `run_all_checks.sh` ST-08 | PASS | ✓ |

---

## Section 10.3 — Silver Accounts Quality

| Check ID | Invariant(s) | Description | Script Check | Result | Signed Off |
|---|---|---|---|---|---|
| SA-01 | INV-19 | Exactly one record per `account_id` in `silver/accounts/data.parquet` | `run_all_checks.sh` SA-01 | PASS | ✓ |
| SA-02 | INV-11 | No null `_pipeline_run_id` in `silver/accounts/data.parquet` | `run_all_checks.sh` SA-02 | PASS | ✓ |
| SA-03 | INV-11 | No null `_record_valid_from` in `silver/accounts/data.parquet` | `run_all_checks.sh` SA-03 | PASS | ✓ |
| SA-04 | — | All `account_status` values are ACTIVE, SUSPENDED, or CLOSED | `run_all_checks.sh` SA-04 | PASS | ✓ |
| SA-05 | INV-08 | All account quarantine records have a non-null `_rejection_reason` | `run_all_checks.sh` SA-05 | PASS | ✓ |
| SA-06 | INV-07, INV-08 | Account quarantine `_rejection_reason` values from valid list | `run_all_checks.sh` SA-06 | PASS | ✓ |

---

## Section 10.4 — Gold Correctness

| Check ID | Invariant(s) | Description | Script Check | Result | Signed Off |
|---|---|---|---|---|---|
| G-01 | INV-17 | Gold date spine matches distinct `transaction_date` values in Silver | `run_all_checks.sh` G-01 | PASS | ✓ |
| G-02 | INV-17 | `gold_daily_summary.total_transactions` = resolvable Silver count per date | `run_all_checks.sh` G-02 | PASS | ✓ |
| G-03 | INV-17 | `gold_daily_summary.total_signed_amount` = SUM of resolvable Silver `_signed_amount` | `run_all_checks.sh` G-03 | PASS | ✓ |
| G-04 | INV-17 | `gold_weekly_account_summary.total_purchases` = resolvable PURCHASE count per account/week | `run_all_checks.sh` G-04 | PASS | ✓ |
| G-05 | — | `week_start_date` is always Monday in `gold_weekly_account_summary` | `run_all_checks.sh` G-05 | PASS | ✓ |
| G-06 | — | `week_end_date` = `week_start_date` + 6 days in `gold_weekly_account_summary` | `run_all_checks.sh` G-06 | PASS | ✓ |
| G-07 | INV-11 | No null `_pipeline_run_id` in either Gold output file | `run_all_checks.sh` G-07 | PASS | ✓ |

---

## Section 10.5 — Idempotency

| Check ID | Invariant(s) | Description | Script Check | Result | Signed Off |
|---|---|---|---|---|---|
| I-01 | INV-10 | Two consecutive pipeline runs over the same date range produce identical layer row counts and Gold sums | `run_all_checks.sh` I-01 | PASS | ✓ |

---

## Section 10.6 — Audit Trail

| Check ID | Invariant(s) | Description | Script Check | Result | Signed Off |
|---|---|---|---|---|---|
| AT-01 | INV-01, INV-03 | Watermark = `2024-01-07` after full historical run | `run_all_checks.sh` AT-01 | PASS | ✓ |
| AT-02 | INV-12 | Every Bronze `_pipeline_run_id` maps to a SUCCESS entry in the run log | `run_all_checks.sh` AT-02 | PASS | ✓ |
| AT-03 | INV-12, INV-16 | Every Gold `_pipeline_run_id` maps to a SUCCESS entry in the run log | `run_all_checks.sh` AT-03 | PASS | ✓ |

---

## Invariant Coverage Summary

| Invariant | Description (abbreviated) | Covered By |
|---|---|---|
| INV-01 | Watermark advances by exactly one day per successful run | AT-01 |
| INV-02 | Watermark must not advance on any layer failure | Pipeline design (enforced in code) |
| INV-03 | Watermark = latest date with all-layer SUCCESS | AT-01 |
| INV-04 | Pipeline never modifies source directory | Pipeline design (enforced in code) |
| INV-05 | All source fields written to Bronze exactly as-is | B-01, B-02, B-03 |
| INV-06 | Bronze amounts are always positive | B-05 |
| INV-07 | Record enters quarantine if and only if it violates a rejection rule | ST-05, SA-06 |
| INV-08 | Every rejected record in quarantine has a non-null reason from the code list | ST-05, ST-06, SA-05, SA-06 |
| INV-09 | Bronze = Silver + Quarantine per date partition | ST-04 |
| INV-10 | Re-running on the same input produces no duplicates | I-01 |
| INV-11 | All records in all layers have non-null audit columns | B-04, ST-02, ST-03, SA-02, SA-03, G-07 |
| INV-12 | Every `_pipeline_run_id` in any layer has a SUCCESS run log entry | ST-07, AT-02, AT-03 |
| INV-13 | `_signed_amount` derived exclusively from `debit_credit_indicator` in transaction_codes | ST-02, ST-08 |
| INV-14 | `transaction_id` is unique across all Silver partitions | ST-01 |
| INV-15 | Gold computed exclusively from Silver data | G-01, G-02, G-03, G-04 |
| INV-16 | Layer not marked SUCCESS unless output is fully written | AT-02, AT-03 |
| INV-17 | `_is_resolvable = false` records excluded from Gold | G-02, G-03, G-04 |
| INV-18 | Watermark does not advance when source file is absent | Pipeline design (enforced in code) |
| INV-19 | `silver/accounts/data.parquet` has exactly one record per `account_id` | SA-01 |

---

## Final Sign-Off

> Complete this section only after all checks above show **PASS**.

| Condition | Status |
|---|---|
| All script checks PASS (`run_all_checks.sh` exits 0) | PASS — 30/30 |
| All 19 invariants confirmed covered (see table above) | PASS — INV-01–INV-19 |
| No open items or deferred fixes | PASS |

**Engineer sign-off:** AADHYA SUBHASH  **Date:** 2026-04-09
