# INVARIANTS.md — Credit Card Transactions Lake

## Changelog

| Version | Date | Author | Change |
|---|---|---|---|
| v1.0 | 2026-04-07 | Aadhya | Greenfield — Initial |
| v1.1 | 2026-04-07 | Aadhya | Phase 4 Design Gate — Added INV-20 (Pipeline Ordering) |

---

## INV-01: Watermark Progression

**Condition:** The watermark must advance by exactly one day between consecutive successful runs.

**Category:** Operational

**Why this matters:** If the watermark skips a date, that date's files are never processed and the gap is invisible to analysts querying Gold. If the watermark advances by more than one day, files for intermediate dates are silently skipped.

**Enforcement points:**
- `pipeline.py` — incremental pipeline watermark advance logic
- `pipeline/control.parquet` — watermark write step

---

## INV-02: Watermark Failure Guard

**Condition:** The watermark must not advance if any layer (Bronze, Silver, or Gold) fails for that date.

**Category:** Operational

**Why this matters:** If the watermark advances past a failed date, that date cannot be re-processed by the incremental pipeline. The data loss is permanent without manual intervention.

**Enforcement points:**
- `pipeline.py` — watermark advance is gated on all three layers completing with SUCCESS status
- `pipeline/control.parquet` — watermark write step must only execute after full layer completion

---

## INV-03: Watermark Correctness

**Condition:** The watermark must always equal the latest date for which all layers have a SUCCESS status in the run log.

**Category:** Operational

**Why this matters:** If the watermark diverges from the run log, the incremental pipeline processes the wrong next date — either re-processing a completed date or skipping an incomplete one.

**Enforcement points:**
- `pipeline.py` — watermark initialisation (historical pipeline) and advance logic (incremental pipeline)
- `pipeline/run_log.parquet` — queried at watermark advance time to confirm SUCCESS status across all three layers

---

## INV-04: Source Immutability

**Condition:** The pipeline must never modify, delete, or write to any file in the source directory.

**Category:** Security

**Why this matters:** Source CSV files are the system's single point of truth for raw input. Any modification destroys the ability to verify Bronze fidelity or re-run the pipeline from source.

**Enforcement points:**
- `pipeline.py` — all file I/O to `source/` must be read-only
- Bronze loader — opens source CSVs in read mode only; no write operations permitted against `source/`

---

## INV-05: Bronze Fidelity

**Condition:** All source fields must be written to Bronze exactly as they appear in the source CSV, without transformation. Only audit columns may be added.

**Category:** Data correctness

**Why this matters:** Bronze is the immutable raw landing zone. If any source value is cast, coerced, or derived during Bronze ingestion, the pipeline loses the ability to trace Silver records back to their exact source values.

**Enforcement points:**
- Bronze loader — field mapping from CSV to Parquet must be direct; no type coercion, no derived fields in source columns
- Bronze Parquet schema — source column names and values must match source CSV exactly

---

## INV-06: Bronze Amount Constraint

**Condition:** Amounts in Bronze must always be stored as positive values.

**Category:** Data correctness

**Why this matters:** The brief states source amounts are always positive. A negative value in Bronze indicates either a source data error or a pipeline transformation that should not exist at this layer. Sign assignment is a Silver-layer operation only.

**Enforcement points:**
- Bronze loader — no sign logic applied during ingestion
- Silver transactions model — sign is applied here using `debit_credit_indicator`, not before

---

## INV-07: Quarantine Entry Condition

**Condition:** A record must enter quarantine if and only if it violates one of the defined rejection rules.

**Category:** Data correctness

**Why this matters:** Quarantine is the audit trail for data quality failures. Over-quarantining hides valid data; under-quarantining allows corrupt data into Silver. Both directions corrupt the audit trail.

**Enforcement points:**
- Silver transactions dbt model — rejection logic must map exactly to the defined rejection code list
- Silver accounts dbt model — rejection logic must map exactly to the defined rejection code list
- `silver/quarantine/date=YYYY-MM-DD/rejected.parquet` — `_rejection_reason` must be from the exhaustive code list

---

## INV-08: No Silent Drops

**Condition:** Every record that does not enter a Silver layer must appear in quarantine with a non-null rejection reason from the defined code list.

**Category:** Data correctness

**Why this matters:** A record that disappears between Bronze and Silver without a quarantine entry is undetectable data loss. The audit trail is broken and the row count reconciliation invariant cannot hold.

**Enforcement points:**
- Silver transactions dbt model — every Bronze record is either promoted to Silver or written to quarantine; no third path exists
- Silver accounts dbt model — same constraint applies
- `_rejection_reason` column — must be non-null for every quarantine record

---

## INV-09: Row Count Reconciliation

**Condition:** For each date partition in Silver transactions: Bronze row count = Silver row count + Quarantine row count.

**Category:** Data correctness

**Why this matters:** This is the primary arithmetic check that no records are silently created or destroyed during Silver promotion. A mismatch indicates either silent drops, phantom records, or a partial write.

**Enforcement points:**
- Silver transactions dbt model — every Bronze record for a given date must produce exactly one output row, either in Silver or in quarantine
- Verification query — must be run per date partition after Silver promotion completes

---

## INV-10: Re-run Idempotency

**Condition:** Re-running a layer on the same input must not produce duplicate records.

**Category:** Operational

**Why this matters:** The pipeline must be safe to re-run after any failure. Duplicate records in any layer corrupt aggregations, break row count reconciliation, and produce incorrect Gold output.

**Enforcement points:**
- Bronze loader — partition exists and row count check before write; rewrite on mismatch, skip on match
- Silver transactions dbt model — partition deleted before rewrite when no SUCCESS entry exists in run log; cross-partition `transaction_id` uniqueness check applied
- Silver accounts dbt model — upsert logic enforces one record per `account_id`
- Gold dbt models — full recompute on every run; output files overwritten completely

---

## INV-11: Audit Column Presence

**Condition:** All records in Bronze, Silver, and Gold must have non-null audit columns.

**Category:** Operational

**Why this matters:** Null audit columns break traceability. A record without `_pipeline_run_id` cannot be traced to a pipeline run; a record without `_ingested_at` has no temporal anchor.

**Enforcement points:**
- Bronze loader — `_source_file`, `_ingested_at`, `_pipeline_run_id` set at write time; none nullable
- Silver dbt models — audit columns carried forward from Bronze and supplemented with Silver-layer columns; none nullable
- Gold dbt models — `_computed_at` and `_pipeline_run_id` set at compute time; none nullable

---

## INV-12: Audit Traceability

**Condition:** For any `_pipeline_run_id` present in a layer's records, a corresponding run log entry with `status = SUCCESS` must exist.

**Category:** Operational

**Why this matters:** `_pipeline_run_id` is the connective tissue between layer records and the run log. If a run ID in a record has no matching SUCCESS entry, the audit trail is broken — the record cannot be traced to a verified pipeline execution.

**Enforcement points:**
- `pipeline/run_log.parquet` — run log entry with `status = SUCCESS` must be written before the pipeline run is considered complete
- Verification query — retrospective check: for all distinct `_pipeline_run_id` values in any layer, a SUCCESS entry must exist in the run log

---

## INV-13: Signed Amount Derivation

**Condition:** `_signed_amount` in Silver must be derived exclusively from the `debit_credit_indicator` in the `transaction_codes` reference.

**Category:** Data correctness

**Why this matters:** The transaction codes dimension is the authoritative source for sign assignment. Any pipeline logic that hard-codes sign rules bypasses this authority and will silently produce incorrect results if transaction code definitions change.

**Enforcement points:**
- Silver transactions dbt model — `_signed_amount` computed by joining to `silver/transaction_codes/data.parquet` and applying `debit_credit_indicator`; no sign logic elsewhere in the model

---

## INV-14: Transaction Uniqueness

**Condition:** `transaction_id` must be unique across all Silver partitions.

**Category:** Data correctness

**Why this matters:** A duplicate `transaction_id` in Silver means the same transaction has been counted twice. All Gold aggregations — counts, sums, averages — are incorrect for any date containing a duplicate.

**Enforcement points:**
- Silver transactions dbt model — cross-partition uniqueness check applied at promotion time; duplicate `transaction_id` rejected to quarantine with `DUPLICATE_TRANSACTION_ID` reason code
- Verification query — `SELECT transaction_id, COUNT(*) FROM silver/transactions/** GROUP BY 1 HAVING COUNT(*) > 1` must return zero rows

---

## INV-15: Gold Dependency Constraint

**Condition:** The Gold layer must be computed exclusively from Silver data.

**Category:** Data correctness

**Why this matters:** Gold is the analyst-facing layer. If Gold reads Bronze directly, it bypasses all quality rules and produces aggregations from unvalidated, potentially corrupt data.

**Enforcement points:**
- Gold dbt models — source references point only to `silver/` paths; no `bronze/` path references permitted in any Gold model

---

## INV-16: Layer Completion Integrity

**Condition:** A layer must not be marked as SUCCESS in the run log unless its output is fully and correctly written.

**Category:** Operational

**Why this matters:** The run log SUCCESS entry is the signal that controls skip decisions on re-runs and watermark advancement. A premature SUCCESS entry causes the pipeline to skip a layer that was not fully written, propagating incomplete data forward.

**Enforcement points:**
- `pipeline.py` — run log SUCCESS entry written only after the layer's dbt model or Bronze loader completes without error
- Error handling — any exception during a layer write must result in a FAILED run log entry, not SUCCESS

---

## INV-17: Gold Eligibility Constraint

**Condition:** Records in Silver with `_is_resolvable = false` must not be included in Gold.

**Category:** Data correctness

**Why this matters:** Unresolvable records reference account IDs that do not exist in Silver accounts at promotion time. Including them in Gold aggregations produces counts and sums attributed to unknown accounts, corrupting analyst-facing outputs.

**Enforcement points:**
- Gold daily summary dbt model — filtered to `_is_resolvable = true` before aggregation
- Gold weekly account summary dbt model — filtered to `_is_resolvable = true` before aggregation

---

## INV-18: Missing File Watermark Guard

**Condition:** When a source file for a date is absent and that date is skipped, the watermark must not advance.

**Category:** Operational

**Why this matters:** A skipped date is not a successfully processed date. Advancing the watermark past a skipped date causes the incremental pipeline to move on permanently — the missing file's data is never ingested.

**Enforcement points:**
- `pipeline.py` — missing file detection sets run log status to SKIPPED; watermark advance logic must not treat SKIPPED as SUCCESS
- `pipeline/control.parquet` — watermark write step gated on SUCCESS status only, not SKIPPED

---

## INV-19: Silver Accounts Uniqueness

**Condition:** At any point after a pipeline run completes, `silver/accounts/data.parquet` must contain exactly one record per `account_id`.

**Category:** Data correctness

**Why this matters:** Silver accounts is the reference used to evaluate `_is_resolvable` for every transaction. Duplicate account records produce non-deterministic join results, corrupting the `_is_resolvable` flag and all downstream Gold output that depends on it.

**Enforcement points:**
- Silver accounts dbt model — upsert logic replaces existing record for `account_id` if a newer version arrives; append is not permitted
- Verification query — `SELECT account_id, COUNT(*) FROM silver/accounts/data.parquet GROUP BY 1 HAVING COUNT(*) > 1` must return zero rows after every run

---

## INV-20: Pipeline Ordering

**Condition:** Silver transactions promotion for a date must not begin unless Silver accounts has a SUCCESS entry in the run log for a run completed after the most recent bronze_accounts run for the same date.

**Category:** Operational

**Why this matters:** Silver transactions uses Silver accounts as a reference to evaluate `_is_resolvable`. If Silver accounts has not been updated for the current date's delta before Silver transactions runs, transactions may be incorrectly flagged as unresolvable — or correctly resolvable records may be excluded from Gold permanently, since backfill is out of scope.

**Enforcement points:**
- `pipeline.py` — `check_silver_accounts_ready(processing_date)` guard called before `run_dbt_model('silver_transactions', ...)` for every date
- Run log — guard reads the most recent SUCCESS entry for `silver_accounts` and compares `completed_at` against the most recent SUCCESS entry for `bronze_accounts` for the same date; if the condition is not met, the run is aborted and logged as FAILED

---

## Engineer Sign-Off

I confirm this invariant set is complete, accurately reflects the architectural decisions in ARCHITECTURE.md, and covers all enforcement points I am aware of before Phase 3 begins.

**Signature:** ___________________________
**Date:** ___________________________
