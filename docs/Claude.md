# Claude.md — v1.0 · FROZEN · 2026-04-07

## Changelog

| Version | Date | Author | Change |
|---|---|---|---|
| v1.0 | 2026-04-07 | Aadhya | Greenfield — Initial · FROZEN |

---

## 1. System Intent

This system ingests daily credit card transaction and account CSV files, enforces
defined quality rules at each layer boundary (Bronze → Silver → Gold), and produces
Gold-layer aggregations that analysts can query via DuckDB CLI. It does not compute
risk scores, modify source files, resolve unresolvable records, support streaming,
or serve data via an API. Success means every Gold number is traceable back to a
quality-checked Silver record, which is traceable back to an immutable Bronze
partition, which is traceable back to a specific source CSV and pipeline run —
and running the pipeline twice on the same input produces identical output.

---

## 2. Hard Invariants

Every invariant below is active in every session. If a task prompt conflicts with
any invariant, the invariant wins. Flag the conflict immediately — never resolve
it silently.

INVARIANT INV-01: The watermark must advance by exactly one day between consecutive successful runs. This is never negotiable.

INVARIANT INV-02: The watermark must not advance if any layer (Bronze, Silver, or Gold) fails for that date. This is never negotiable.

INVARIANT INV-03: The watermark must always equal the latest date for which all layers have a SUCCESS status in the run log. This is never negotiable.

INVARIANT INV-04: The pipeline must never modify, delete, or write to any file in the source directory. This is never negotiable.

INVARIANT INV-05: All source fields must be written to Bronze exactly as they appear in the source CSV, without transformation. Only audit columns may be added. This is never negotiable.

INVARIANT INV-06: Amounts in Bronze must always be stored as positive values. This is never negotiable.

INVARIANT INV-07: A record must enter quarantine if and only if it violates one of the defined rejection rules. This is never negotiable.

INVARIANT INV-08: Every record that does not enter a Silver layer must appear in quarantine with a non-null rejection reason from the defined code list. This is never negotiable.

INVARIANT INV-09: For each date partition in Silver transactions: Bronze row count = Silver row count + Quarantine row count. This is never negotiable.

INVARIANT INV-10: Re-running a layer on the same input must not produce duplicate records. This is never negotiable.

INVARIANT INV-11: All records in Bronze, Silver, and Gold must have non-null audit columns. This is never negotiable.

INVARIANT INV-12: For any `_pipeline_run_id` present in a layer's records, a corresponding run log entry with status = SUCCESS must exist. This is never negotiable.

INVARIANT INV-13: `_signed_amount` in Silver must be derived exclusively from the `debit_credit_indicator` in the `transaction_codes` reference. This is never negotiable.

INVARIANT INV-14: `transaction_id` must be unique across all Silver partitions. This is never negotiable.

INVARIANT INV-15: The Gold layer must be computed exclusively from Silver data. No Gold model may reference any path under `data/bronze/`. This is never negotiable.

INVARIANT INV-16: A layer must not be marked as SUCCESS in the run log unless its output is fully and correctly written. This is never negotiable.

INVARIANT INV-17: Records in Silver with `_is_resolvable = false` must not be included in Gold. This is never negotiable.

INVARIANT INV-18: When a source file for a date is absent and that date is skipped, the watermark must not advance. This is never negotiable.

INVARIANT INV-19: At any point after a pipeline run completes, `silver/accounts/data.parquet` must contain exactly one record per `account_id`. This is never negotiable.

INVARIANT INV-20: Silver transactions promotion for a date must not begin unless Silver accounts has a SUCCESS entry in the run log for a run completed after the most recent bronze_accounts run for the same date. This is never negotiable.

---

## 3. Scope Boundary

### Files CC may create or modify

```
pipeline.py
Dockerfile
docker-compose.yml
.env.example
.gitignore
README.md
PROJECT_MANIFEST.md
dbt_project/dbt_project.yml
dbt_project/profiles.yml
dbt_project/models/silver/silver_transaction_codes.sql
dbt_project/models/silver/silver_accounts.sql
dbt_project/models/silver/silver_transactions.sql
dbt_project/models/silver/silver_quarantine.sql
dbt_project/models/gold/gold_daily_summary.sql
dbt_project/models/gold/gold_weekly_account_summary.sql
dbt_project/models/silver/schema.yml
dbt_project/models/gold/schema.yml
verification/bronze_checks.sql
verification/silver_accounts_checks.sql
verification/silver_transactions_checks.sql
verification/gold_checks.sql
verification/idempotency_checks.sql
verification/run_idempotency_test.sh
verification/run_all_checks.sh
verification/VERIFICATION_CHECKLIST.md
sessions/SESSION_LOG.md           (append only — one per session)
sessions/VERIFICATION_RECORD.md  (append only — one per session)
```

Any `.gitkeep` file in an empty directory listed in Task 1.1.

### Files CC must never create or modify

- Any file under `source/` — read-only at all times (INV-04)
- Any file under `data/` — written only by pipeline.py and dbt at runtime; never edited directly by CC
- `docs/ARCHITECTURE.md` — planning artifact, frozen after Phase 4
- `docs/INVARIANTS.md` — planning artifact, frozen after Phase 4
- `docs/EXECUTION_PLAN.md` — planning artifact, frozen after Phase 4
- `docs/Claude.md` — this file; frozen at creation; never edited during Phase 6
- Any file not listed above and not registered in `PROJECT_MANIFEST.md`

### Conflict rule

If a task prompt instructs CC to do something that would violate any invariant above:
the invariant wins. CC must flag the conflict explicitly and stop. CC never resolves
invariant conflicts silently.

---

## 4. Fixed Stack

| Concern | Choice |
|---|---|
| Python | 3.11 (python:3.11-slim base image) |
| dbt-core | 1.7.x |
| dbt-duckdb | 1.7.x |
| DuckDB Python package | version matching dbt-duckdb 1.7.x |
| Containerisation | Docker Compose — single service named `pipeline` |
| Storage format | Parquet on local filesystem — no database server |
| Query engine | DuckDB embedded — no server process |
| dbt materialisation | `table` for all Silver and Gold models — never `incremental` |
| Bronze ingestion | pipeline.py using DuckDB directly — dbt not used for Bronze |
| Package management | pip inside Dockerfile — no virtual environment |
| pandas | Not permitted — DuckDB only for all data operations |

**Environment variables** (read via python-dotenv from `.env`):

| Variable | Purpose |
|---|---|
| `DATA_DIR` | Absolute path to `data/` inside container — `/app/data` |
| `SOURCE_DIR` | Absolute path to `source/` inside container — `/app/source` |
| `DBT_PROFILES_DIR` | Path to dbt profiles directory — `/app/dbt_project` |

**`_pipeline_run_id` format:** `YYYYMMDD_<first-8-chars-of-uuid4>`
Example: `20240403_a3f8c2d1`

**Run log query pattern:** Always take the most recent row per model + date combination.
The run log is append-only — do not deduplicate at write time.

**Parquet paths — canonical forms:**

| Entity | Path |
|---|---|
| Bronze transactions | `{DATA_DIR}/bronze/transactions/date=YYYY-MM-DD/data.parquet` |
| Bronze accounts | `{DATA_DIR}/bronze/accounts/date=YYYY-MM-DD/data.parquet` |
| Bronze transaction codes | `{DATA_DIR}/bronze/transaction_codes/data.parquet` |
| Silver transactions | `{DATA_DIR}/silver/transactions/date=YYYY-MM-DD/data.parquet` |
| Silver accounts | `{DATA_DIR}/silver/accounts/data.parquet` |
| Silver transaction codes | `{DATA_DIR}/silver/transaction_codes/data.parquet` |
| Silver quarantine | `{DATA_DIR}/silver/quarantine/date=YYYY-MM-DD/rejected.parquet` |
| Gold daily summary | `{DATA_DIR}/gold/daily_summary/data.parquet` |
| Gold weekly account summary | `{DATA_DIR}/gold/weekly_account_summary/data.parquet` |
| Run log | `{DATA_DIR}/pipeline/run_log.parquet` |
| Control table | `{DATA_DIR}/pipeline/control.parquet` |

**Rejection reason codes — exhaustive list:**

```
NULL_REQUIRED_FIELD
INVALID_AMOUNT
DUPLICATE_TRANSACTION_ID
INVALID_TRANSACTION_CODE
INVALID_CHANNEL
NULL_REQUIRED_FIELD        (accounts)
INVALID_ACCOUNT_STATUS
```

Valid `account_status` values: `ACTIVE`, `SUSPENDED`, `CLOSED`
Valid `channel` values: `ONLINE`, `IN_STORE`
Valid `debit_credit_indicator` values: `DR` (debit — positive signed amount), `CR` (credit — negative signed amount)

---

## 5. Rules

**Rule 1:** All file references use full paths from repo root — never bare filenames.

**Rule 2:** All files inside any enhancement package carry their ENH-NNN prefix — no exceptions.

**Rule 3:** Any file not in the mandatory set for its directory and not registered in `PROJECT_MANIFEST.md` must not be read by CC as authoritative input. CC flags unregistered files and reports them to the engineer before proceeding.

**Rule 4 (Exception handling):** Every Bronze loader and `run_dbt_model` must wrap its
body in `try/finally`. The `finally` block writes a run log entry unconditionally —
SUCCESS if the operation completed without error, FAILED otherwise. A FAILED entry
must be written even if an exception is thrown before any data write begins.

**Rule 5 (Corrupt Parquet guard):** If reading an existing Parquet file raises an
exception, treat it as a row count mismatch — delete and rewrite. Never propagate
the read exception; log a WARNING and proceed.

**Rule 6 (No silent conflicts):** If a task prompt conflicts with an invariant,
the invariant wins. Flag explicitly. Never resolve silently.
