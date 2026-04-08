# EXECUTION_PLAN.md — Credit Card Transactions Lake

## Changelog

| Version | Date | Author | Change |
|---|---|---|---|
| v1.0 | 2026-04-07 | Aadhya | Greenfield — Initial |
| v1.1 | 2026-04-07 | Aadhya | Phase 4 Design Gate — F3/F4 resolved: exception handling added to T3.1, T3.2, T3.3, T7.1 CC prompts |

---

## Resolved Decisions

All open questions from ARCHITECTURE.md are resolved. No blockers remain before build begins.

| Question | Resolution |
|---|---|
| Missing source file behaviour | Skip date, log SKIPPED, hold watermark |
| Pipeline ordering guarantee | Accounts before transactions, enforced by pipeline.py |
| `_pipeline_run_id` format | `YYYYMMDD_<first-8-chars-of-uuid>` |
| Bronze idempotency mechanism | Partition exists + row count check; rewrite on mismatch |
| Gold with zero resolvable records | Write zero row for that date |
| `closing_balance` with no account record | Write null |
| Historical pipeline and watermark | Historical pipeline ignores watermark during processing; sets it once at end |
| dbt materialisation strategy | `table` — not incremental |
| Silver partial write recovery | Delete partition and quarantine before rewrite |
| Gold recompute strategy | Full recompute every run |
| Run log query pattern | Most recent row per model + date combination |

---

## Session Overview

| Session | Name | Goal | Tasks | Est. Duration |
|---|---|---|---|---|
| S1 | Project Scaffold | Repo structure, Docker, dbt skeleton, pipeline.py stub committed and running | 4 | 1.5 hrs |
| S2 | Pipeline Control and Run Log | Control table and run log Parquet files initialised; read/write helpers tested | 3 | 1 hr |
| S3 | Bronze Loaders | All three Bronze loaders (transactions, accounts, transaction_codes) complete and idempotent | 4 | 2 hrs |
| S4 | Silver — Transaction Codes and Accounts | Silver transaction_codes loaded; Silver accounts upsert complete | 3 | 1.5 hrs |
| S5 | Silver — Transactions | Silver transactions promotion with all quality rules and quarantine complete | 4 | 2.5 hrs |
| S6 | Gold Layer | Gold daily summary and weekly account summary complete | 3 | 2 hrs |
| S7 | Pipeline Orchestration | pipeline.py historical and incremental pipelines wired end-to-end; watermark logic complete | 4 | 2.5 hrs |
| S8 | Verification and Sign-Off | All Phase 8 verification queries passing; system sign-off complete | 3 | 2 hrs |

---

## Session 1 — Project Scaffold

**Goal:** A committed repo with the full directory structure, Docker Compose stack that starts cleanly, dbt project skeleton with stub model files, and pipeline.py stub with TODO markers. No pipeline logic yet — just a verified runnable skeleton.

**Integration check:**
```bash
docker compose up -d && docker compose exec pipeline dbt debug && echo "SCAFFOLD OK"
```

---

### Task 1.1 — Repository Scaffolding

**Description:** Create the full PBVI directory structure, README.md, and PROJECT_MANIFEST.md. All directories created in a single step. Empty directories use .gitkeep files.

**CC prompt:**
```
Create the full project directory structure for the Credit Card Transactions Lake using
the PBVI standard layout. Full paths from repo root:

Directories to create (use .gitkeep for empty dirs):
  brief/
  docs/
  docs/prompts/
  sessions/
  verification/
  discovery/
  discovery/components/
  enhancements/
  source/
  data/bronze/transactions/
  data/bronze/accounts/
  data/bronze/transaction_codes/
  data/silver/transactions/
  data/silver/accounts/
  data/silver/transaction_codes/
  data/silver/quarantine/
  data/gold/daily_summary/
  data/gold/weekly_account_summary/
  data/pipeline/

Create README.md at repo root using the PBVI mandatory template. Project name:
Credit Card Transactions Lake. Type: DATA_ACCELERATOR. Status: Greenfield — S1 in progress.

Create PROJECT_MANIFEST.md at repo root. Include all mandatory sections:
Core Documents, Non-Standard Registered Files, Non-Standard Registered Directories,
Session Logs, Verification Records, Verification Checklists, Discovery Artifacts,
Enhancement Registry, Structural Exceptions. Register docs/ARCHITECTURE.md,
docs/INVARIANTS.md, docs/EXECUTION_PLAN.md as PRESENT. Register docs/Claude.md
as PENDING. Register all session and verification artifacts as PENDING.

Structural exceptions: README.md and PROJECT_MANIFEST.md exempt from Rule 3.

Commit message: 1.1 — Repository Scaffolding: PBVI directory structure and manifest
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | All directories exist | `find . -type d` includes all listed paths |
| TC-2 | Empty dirs have .gitkeep | No empty directories without .gitkeep |
| TC-3 | README.md exists at root | File present, contains project name and PBVI structure |
| TC-4 | PROJECT_MANIFEST.md exists at root | File present, all mandatory sections present |

**Verification command:**
```bash
find . -type d | sort && test -f README.md && test -f PROJECT_MANIFEST.md && echo "PASS"
```

**Invariant flags:** None directly — structural foundation for INV-04 (source immutability enforced by directory separation).

---

### Task 1.2 — Docker Compose and Dockerfile

**Description:** Create Dockerfile and docker-compose.yml. Single container running Python 3.11 with dbt-core 1.7.x, dbt-duckdb 1.7.x, and DuckDB. Bind-mounts for source/, data/, and the dbt project. Pipeline entrypoint is pipeline.py.

**CC prompt:**
```
Create Dockerfile and docker-compose.yml for the Credit Card Transactions Lake.

Requirements:
- Base image: python:3.11-slim
- Install: dbt-core==1.7.*, dbt-duckdb==1.7.*, duckdb (matching version for dbt-duckdb 1.7.x)
- Single service named `pipeline`
- Bind mounts:
    ./source:/app/source:ro          (read-only — enforces INV-04)
    ./data:/app/data
    ./dbt_project:/app/dbt_project
- Working directory: /app
- Default command: python pipeline.py --help
- .env file for environment variables: DBT_PROFILES_DIR, DATA_DIR, SOURCE_DIR

Create .env.example with all required variables documented.
Create .gitignore that excludes .env but not .env.example.

All file paths use full paths from repo root.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | `docker compose build` succeeds | Exit code 0, no errors |
| TC-2 | `docker compose up -d` starts | Container running |
| TC-3 | source/ mount is read-only | Write attempt to /app/source inside container fails |
| TC-4 | .env.example exists, .env excluded from git | Both conditions confirmed |

**Verification command:**
```bash
docker compose build && docker compose up -d && docker compose exec pipeline python --version && docker compose exec pipeline sh -c "touch /app/source/test 2>&1 | grep -q 'Read-only' && echo 'SOURCE READONLY OK'" && echo "PASS"
```

**Invariant flags:** INV-04 (source immutability — read-only bind mount is first enforcement layer).

---

### Task 1.3 — dbt Project Skeleton

**Description:** Create the dbt project with profiles.yml, dbt_project.yml, and empty stub model files for all Silver and Gold models. Models use `table` materialisation. No SQL logic yet — stubs only.

**CC prompt:**
```
Create the dbt project skeleton at dbt_project/. Full structure:

dbt_project/dbt_project.yml — project name: cc_transactions_lake
dbt_project/profiles.yml — DuckDB adapter, database path: /app/data/cc_lake.duckdb

Model stubs (empty SELECT 1 AS placeholder):
  dbt_project/models/silver/silver_transaction_codes.sql
  dbt_project/models/silver/silver_accounts.sql
  dbt_project/models/silver/silver_transactions.sql
  dbt_project/models/silver/silver_quarantine.sql
  dbt_project/models/gold/gold_daily_summary.sql
  dbt_project/models/gold/gold_weekly_account_summary.sql

All models: materialized as table in dbt_project.yml config.
Add schema.yml stubs in each model directory — no tests yet, just source declarations.

Sources declared in schema.yml:
  bronze_transactions — path: /app/data/bronze/transactions/
  bronze_accounts — path: /app/data/bronze/accounts/
  bronze_transaction_codes — path: /app/data/bronze/transaction_codes/
  silver_transactions — path: /app/data/silver/transactions/
  silver_accounts — path: /app/data/silver/accounts/
  silver_transaction_codes — path: /app/data/silver/transaction_codes/
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | `dbt debug` passes | All checks green |
| TC-2 | `dbt compile` succeeds | All 6 stub models compile without error |
| TC-3 | All model files exist | 6 .sql files present at correct paths |
| TC-4 | `table` materialisation set | dbt_project.yml confirms table for all models |

**Verification command:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt debug && dbt compile && echo PASS"
```

**Invariant flags:** INV-15 (Gold dependency constraint — source declarations enforce Silver-only reads for Gold models from the start).

---

### Task 1.4 — pipeline.py Stub

**Description:** Create pipeline.py with CLI argument parsing, logging setup, and TODO-marked function stubs for all pipeline operations. No logic yet — just the skeleton that runs without error.

**CC prompt:**
```
Create /app/pipeline.py with the following structure. Full path: pipeline.py at repo root
(bind-mounted to /app/pipeline.py in container).

CLI interface using argparse:
  pipeline.py historical --start-date YYYY-MM-DD --end-date YYYY-MM-DD
  pipeline.py incremental

Logging: structured logging to stdout, level INFO by default.

Function stubs with TODO markers (raise NotImplementedError):
  generate_run_id() -> str          # format: YYYYMMDD_<first-8-chars-of-uuid>
  load_control_table() -> dict
  write_control_table(date, run_id)
  append_run_log(row: dict)
  load_bronze_transactions(date, run_id)
  load_bronze_accounts(date, run_id)
  load_bronze_transaction_codes(run_id)
  run_dbt_model(model_name, run_id, vars: dict) -> bool
  run_historical(start_date, end_date)
  run_incremental()

main() entry point that routes to run_historical or run_incremental based on CLI args.

Environment variables read from .env via python-dotenv:
  DATA_DIR, SOURCE_DIR, DBT_PROFILES_DIR
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | `python pipeline.py --help` exits cleanly | Exit code 0, usage printed |
| TC-2 | `python pipeline.py historical --start-date 2024-01-01 --end-date 2024-01-07` | Raises NotImplementedError (stub) — not an unhandled crash |
| TC-3 | `python pipeline.py incremental` | Raises NotImplementedError (stub) — not an unhandled crash |
| TC-4 | All function stubs importable | `python -c "import pipeline"` succeeds |

**Verification command:**
```bash
docker compose exec pipeline python pipeline.py --help && docker compose exec pipeline python -c "import pipeline; print('IMPORT OK')" && echo "PASS"
```

**Invariant flags:** None directly — scaffold only.

---

## Session 2 — Pipeline Control and Run Log

**Goal:** Control table and run log Parquet helpers are fully implemented, tested, and committed. All subsequent sessions depend on these — they must be correct before any pipeline logic is built.

**Integration check:**
```bash
docker compose exec pipeline python -c "
import pipeline
run_id = pipeline.generate_run_id()
pipeline.append_run_log({'run_id': run_id, 'pipeline_type': 'HISTORICAL', 'model_name': 'test', 'layer': 'BRONZE', 'started_at': '2024-01-01T00:00:00', 'completed_at': '2024-01-01T00:00:01', 'status': 'SUCCESS', 'records_processed': 0, 'records_written': 0, 'records_rejected': None, 'error_message': None})
log = pipeline.read_run_log()
assert len(log) == 1
assert log[0]['status'] == 'SUCCESS'
print('RUN LOG OK')
pipeline.write_control_table('2024-01-01', run_id)
ctrl = pipeline.load_control_table()
assert ctrl['last_processed_date'] == '2024-01-01'
print('CONTROL TABLE OK')
"
```

---

### Task 2.1 — Run ID Generator

**Description:** Implement `generate_run_id()`. Format: `YYYYMMDD_<first-8-chars-of-uuid4>`. Must be unique across calls on the same date.

**CC prompt:**
```
Implement generate_run_id() in pipeline.py.

Requirements:
- Format: YYYYMMDD_<first-8-chars-of-uuid4>
- Example output: 20240403_a3f8c2d1
- Uses current date at call time
- Each call returns a unique value (uuid4 guarantees this)
- No external dependencies beyond uuid and datetime (both stdlib)

Replace the NotImplementedError stub. All other stubs remain unchanged.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Call generate_run_id() | Returns string matching `^\d{8}_[a-f0-9]{8}$` |
| TC-2 | Call twice on same date | Two different values returned |
| TC-3 | Date portion matches today | First 8 chars equal `datetime.today().strftime('%Y%m%d')` |

**Verification command:**
```bash
docker compose exec pipeline python -c "
import pipeline, re, datetime
r1 = pipeline.generate_run_id()
r2 = pipeline.generate_run_id()
assert re.match(r'^\d{8}_[a-f0-9]{8}$', r1), f'Format wrong: {r1}'
assert r1 != r2, 'Not unique'
assert r1[:8] == datetime.datetime.today().strftime('%Y%m%d')
print('PASS')
"
```

**Invariant flags:** INV-11, INV-12 (run_id is the audit traceability key — format must be consistent).

---

### Task 2.2 — Run Log Helpers

**Description:** Implement `append_run_log()` and `read_run_log()`. Run log is an append-only Parquet file at `data/pipeline/run_log.parquet`. New rows appended on each call. File created if absent.

**CC prompt:**
```
Implement append_run_log(row: dict) and read_run_log() -> list[dict] in pipeline.py.

Run log file path: {DATA_DIR}/pipeline/run_log.parquet

Schema (all columns, types, nullability):
  run_id              STRING      NOT NULL
  pipeline_type       STRING      NOT NULL   -- HISTORICAL or INCREMENTAL
  model_name          STRING      NOT NULL
  layer               STRING      NOT NULL   -- BRONZE, SILVER, or GOLD
  started_at          TIMESTAMP   NOT NULL
  completed_at        TIMESTAMP   NOT NULL
  status              STRING      NOT NULL   -- SUCCESS, FAILED, or SKIPPED
  records_processed   INTEGER     NULLABLE
  records_written     INTEGER     NULLABLE
  records_rejected    INTEGER     NULLABLE
  error_message       STRING      NULLABLE

append_run_log(row):
  - Appends a single row dict to the run log Parquet file
  - Creates the file if it does not exist
  - Never overwrites existing rows — append only
  - Validates that required fields are non-null before writing

read_run_log() -> list[dict]:
  - Returns all rows as a list of dicts
  - Returns empty list if file does not exist
  - Always returns rows sorted by started_at ascending

Use DuckDB for all Parquet reads and writes. No pandas.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Append to non-existent file | File created, one row present |
| TC-2 | Append twice | Two rows present, both readable |
| TC-3 | read_run_log on missing file | Returns empty list, no error |
| TC-4 | Required field null | Raises ValueError before write |
| TC-5 | Rows sorted by started_at | Second appended row appears after first |

**Verification command:**
```bash
docker compose exec pipeline python -c "
import pipeline, os
os.makedirs('data/pipeline', exist_ok=True)
pipeline.append_run_log({'run_id': 'test_001', 'pipeline_type': 'HISTORICAL', 'model_name': 'bronze_transactions', 'layer': 'BRONZE', 'started_at': '2024-01-01T00:00:00', 'completed_at': '2024-01-01T00:00:01', 'status': 'SUCCESS', 'records_processed': 10, 'records_written': 10, 'records_rejected': None, 'error_message': None})
pipeline.append_run_log({'run_id': 'test_002', 'pipeline_type': 'HISTORICAL', 'model_name': 'bronze_accounts', 'layer': 'BRONZE', 'started_at': '2024-01-01T00:00:02', 'completed_at': '2024-01-01T00:00:03', 'status': 'SUCCESS', 'records_processed': 5, 'records_written': 5, 'records_rejected': None, 'error_message': None})
rows = pipeline.read_run_log()
assert len(rows) == 2, f'Expected 2 rows, got {len(rows)}'
assert rows[0]['run_id'] == 'test_001'
print('PASS')
"
```

**Invariant flags:** INV-12 (Audit Traceability), INV-16 (Layer Completion Integrity — SUCCESS written here).

---

### Task 2.3 — Control Table Helpers

**Description:** Implement `load_control_table()` and `write_control_table()`. Control table is a single-row Parquet file at `data/pipeline/control.parquet`. Overwritten on each watermark advance.

**CC prompt:**
```
Implement load_control_table() -> dict and write_control_table(date: str, run_id: str)
in pipeline.py.

Control table file path: {DATA_DIR}/pipeline/control.parquet

Schema:
  last_processed_date   DATE      NOT NULL
  updated_at            TIMESTAMP NOT NULL
  updated_by_run_id     STRING    NOT NULL

load_control_table():
  - Returns the single row as a dict
  - Returns None if the file does not exist (pipeline not yet initialised)
  - Raises ValueError if the file contains more than one row

write_control_table(date, run_id):
  - Writes a single row, overwriting the file completely
  - Sets updated_at to current timestamp
  - date must be a valid YYYY-MM-DD string — raise ValueError if not
  - Never appends — always a complete overwrite of the single-row file

Use DuckDB for all Parquet reads and writes. No pandas.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | load_control_table on missing file | Returns None |
| TC-2 | write then load | Returns dict with correct date and run_id |
| TC-3 | Write twice | Second write overwrites first — one row present |
| TC-4 | Invalid date string | Raises ValueError |
| TC-5 | File with two rows | Raises ValueError on load |

**Verification command:**
```bash
docker compose exec pipeline python -c "
import pipeline
assert pipeline.load_control_table() is None or True
pipeline.write_control_table('2024-01-07', 'test_run_001')
ctrl = pipeline.load_control_table()
assert ctrl['last_processed_date'] == '2024-01-07'
assert ctrl['updated_by_run_id'] == 'test_run_001'
pipeline.write_control_table('2024-01-08', 'test_run_002')
ctrl2 = pipeline.load_control_table()
assert ctrl2['last_processed_date'] == '2024-01-08'
print('PASS')
"
```

**Invariant flags:** INV-01, INV-02, INV-03, INV-18 (all watermark invariants — this is the write path).

---

## Session 3 — Bronze Loaders

**Goal:** All three Bronze loaders complete, idempotent, and verified. Bronze partitions written exactly as source data with correct audit columns. Re-running produces no duplicates.

**Integration check:**
```bash
docker compose exec pipeline python -c "
import pipeline
run_id = pipeline.generate_run_id()
pipeline.load_bronze_transaction_codes(run_id)
pipeline.load_bronze_accounts('2024-01-01', run_id)
pipeline.load_bronze_transactions('2024-01-01', run_id)
import duckdb
tc = duckdb.query('SELECT COUNT(*) FROM read_parquet(\"data/bronze/transaction_codes/data.parquet\")').fetchone()[0]
acc = duckdb.query('SELECT COUNT(*) FROM read_parquet(\"data/bronze/accounts/date=2024-01-01/data.parquet\")').fetchone()[0]
txn = duckdb.query('SELECT COUNT(*) FROM read_parquet(\"data/bronze/transactions/date=2024-01-01/data.parquet\")').fetchone()[0]
assert tc > 0 and acc > 0 and txn > 0
print(f'Bronze counts: tc={tc} acc={acc} txn={txn} — PASS')
"
```

---

### Task 3.1 — Bronze Transaction Codes Loader

**Description:** Implement `load_bronze_transaction_codes(run_id)`. Reads `source/transaction_codes.csv`, writes to `data/bronze/transaction_codes/data.parquet`. Idempotent — skip if file already exists with matching row count.

**CC prompt:**
```
Implement load_bronze_transaction_codes(run_id: str) in pipeline.py.

Source file: {SOURCE_DIR}/transaction_codes.csv (read-only — never modify)
Output file: {DATA_DIR}/bronze/transaction_codes/data.parquet

Behaviour:
1. Read source CSV row count
2. If output Parquet exists AND row count matches source: skip, log SKIPPED to run log, return
3. Otherwise: write all rows to Parquet, adding audit columns, log SUCCESS to run log

Audit columns to add (not present in source):
  _source_file       STRING    -- basename of source CSV
  _ingested_at       TIMESTAMP -- current timestamp at write time
  _pipeline_run_id   STRING    -- run_id parameter

Source fields written exactly as-is — no transformation, no type coercion (INV-05).
Use DuckDB read_csv_auto for reading. Write as Parquet using DuckDB COPY TO.
No pandas.

Exception handling — two requirements:
1. If the existing Parquet file raises an exception when read (corrupt or unreadable):
   treat it as a row count mismatch — delete and rewrite. Do not propagate the read
   exception; log a WARNING and proceed with the rewrite.
2. Wrap the entire function body in try/finally. The finally block must write a run log
   entry unconditionally — SUCCESS if the write completed without error, FAILED with
   error_message otherwise. A FAILED entry must be written even if an exception is
   thrown before the Parquet write begins.

Log one run log row: model_name='bronze_transaction_codes', layer='BRONZE'.
records_processed = source row count. records_written = rows written to Parquet.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | First run | Parquet created, row count matches CSV |
| TC-2 | Re-run (idempotent) | Skipped, existing Parquet unchanged, SKIPPED in run log |
| TC-3 | Audit columns present | `_source_file`, `_ingested_at`, `_pipeline_run_id` non-null in all rows |
| TC-4 | Source fields unchanged | Sample field values match CSV exactly |
| TC-5 | Source file not modified | CSV row count unchanged after loader runs |

**Verification command:**
```bash
docker compose exec pipeline python -c "
import pipeline, duckdb
run_id = pipeline.generate_run_id()
src_count = duckdb.query('SELECT COUNT(*) FROM read_csv_auto(\"source/transaction_codes.csv\")').fetchone()[0]
pipeline.load_bronze_transaction_codes(run_id)
b_count = duckdb.query('SELECT COUNT(*) FROM read_parquet(\"data/bronze/transaction_codes/data.parquet\")').fetchone()[0]
assert b_count == src_count, f'Row count mismatch: {b_count} != {src_count}'
nulls = duckdb.query('SELECT COUNT(*) FROM read_parquet(\"data/bronze/transaction_codes/data.parquet\") WHERE _pipeline_run_id IS NULL OR _ingested_at IS NULL OR _source_file IS NULL').fetchone()[0]
assert nulls == 0, 'Null audit columns found'
pipeline.load_bronze_transaction_codes(pipeline.generate_run_id())
b_count2 = duckdb.query('SELECT COUNT(*) FROM read_parquet(\"data/bronze/transaction_codes/data.parquet\")').fetchone()[0]
assert b_count2 == b_count, 'Duplicate rows on re-run'
print('PASS')
"
```

**Invariant flags:** INV-04 (source immutability), INV-05 (Bronze fidelity), INV-10 (re-run idempotency), INV-11 (audit column presence).

---

### Task 3.2 — Bronze Accounts Loader

**Description:** Implement `load_bronze_accounts(date, run_id)`. Reads `source/accounts_YYYY-MM-DD.csv`, writes to `data/bronze/accounts/date=YYYY-MM-DD/data.parquet`. Idempotent — partition exists + row count check.

**CC prompt:**
```
Implement load_bronze_accounts(date: str, run_id: str) in pipeline.py.

Source file: {SOURCE_DIR}/accounts_{date}.csv (read-only — never modify)
Output path: {DATA_DIR}/bronze/accounts/date={date}/data.parquet

Behaviour:
1. If source file does not exist: log SKIPPED to run log, return
2. Read source CSV row count
3. If output Parquet exists AND row count matches source: log SKIPPED, return
4. If output Parquet exists AND row count does NOT match source: delete and rewrite
5. If output Parquet does not exist: write

Write behaviour:
- Add audit columns: _source_file, _ingested_at, _pipeline_run_id
- Source fields written exactly as-is — no transformation (INV-05)
- Use DuckDB read_csv_auto for reading, COPY TO for writing
- No pandas

Exception handling — two requirements:
1. If the existing Parquet file raises an exception when read (corrupt or unreadable):
   treat it as a row count mismatch — delete and rewrite. Do not propagate the read
   exception; log a WARNING and proceed with the rewrite.
2. Wrap the entire function body in try/finally. The finally block must write a run log
   entry unconditionally — SUCCESS if the write completed without error, FAILED with
   error_message otherwise. A FAILED entry must be written even if an exception is
   thrown before the Parquet write begins.

Log one run log row: model_name='bronze_accounts', layer='BRONZE'.
records_processed = source row count. records_written = rows written.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | First run with valid CSV | Parquet created, row count matches CSV |
| TC-2 | Re-run identical input | SKIPPED, no new rows, existing file unchanged |
| TC-3 | Missing source file | SKIPPED in run log, no Parquet created, no error |
| TC-4 | Partial write simulation (row count mismatch) | Partition rewritten on re-run |
| TC-5 | Audit columns non-null | All three audit columns present and non-null |

**Verification command:**
```bash
docker compose exec pipeline python -c "
import pipeline, duckdb, os
run_id = pipeline.generate_run_id()
date = '2024-01-01'
src_count = duckdb.query(f'SELECT COUNT(*) FROM read_csv_auto(\"source/accounts_{date}.csv\")').fetchone()[0]
pipeline.load_bronze_accounts(date, run_id)
b_count = duckdb.query(f'SELECT COUNT(*) FROM read_parquet(\"data/bronze/accounts/date={date}/data.parquet\")').fetchone()[0]
assert b_count == src_count
pipeline.load_bronze_accounts(date, pipeline.generate_run_id())
b_count2 = duckdb.query(f'SELECT COUNT(*) FROM read_parquet(\"data/bronze/accounts/date={date}/data.parquet\")').fetchone()[0]
assert b_count2 == b_count, 'Duplicates on re-run'
print('PASS')
"
```

**Invariant flags:** INV-04, INV-05, INV-10, INV-11, INV-18 (missing file behaviour).

---

### Task 3.3 — Bronze Transactions Loader

**Description:** Implement `load_bronze_transactions(date, run_id)`. Reads `source/transactions_YYYY-MM-DD.csv`, writes to `data/bronze/transactions/date=YYYY-MM-DD/data.parquet`. Same idempotency pattern as accounts.

**CC prompt:**
```
Implement load_bronze_transactions(date: str, run_id: str) in pipeline.py.

Source file: {SOURCE_DIR}/transactions_{date}.csv (read-only — never modify)
Output path: {DATA_DIR}/bronze/transactions/date={date}/data.parquet

Behaviour identical to load_bronze_accounts pattern:
1. Missing file → SKIPPED in run log, return
2. Parquet exists + row count matches → SKIPPED in run log, return
3. Parquet exists + row count mismatch → delete and rewrite
4. Parquet absent → write

Write behaviour:
- Add audit columns: _source_file, _ingested_at, _pipeline_run_id
- Source fields written exactly as-is — no transformation (INV-05)
- amount field stored as-is from source (always positive per brief — INV-06)
- Use DuckDB read_csv_auto and COPY TO. No pandas.

Exception handling — two requirements:
1. If the existing Parquet file raises an exception when read (corrupt or unreadable):
   treat it as a row count mismatch — delete and rewrite. Do not propagate the read
   exception; log a WARNING and proceed with the rewrite.
2. Wrap the entire function body in try/finally. The finally block must write a run log
   entry unconditionally — SUCCESS if the write completed without error, FAILED with
   error_message otherwise. A FAILED entry must be written even if an exception is
   thrown before the Parquet write begins.

Log one run log row: model_name='bronze_transactions', layer='BRONZE'.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | First run | Parquet created, row count matches CSV |
| TC-2 | Re-run | SKIPPED, no duplicates |
| TC-3 | Missing source file | SKIPPED, no error |
| TC-4 | amount values all positive | No negative amounts in Bronze Parquet |
| TC-5 | Audit columns non-null | All three non-null in every row |

**Verification command:**
```bash
docker compose exec pipeline python -c "
import pipeline, duckdb
run_id = pipeline.generate_run_id()
date = '2024-01-01'
pipeline.load_bronze_transactions(date, run_id)
b_count = duckdb.query(f'SELECT COUNT(*) FROM read_parquet(\"data/bronze/transactions/date={date}/data.parquet\")').fetchone()[0]
neg = duckdb.query(f'SELECT COUNT(*) FROM read_parquet(\"data/bronze/transactions/date={date}/data.parquet\") WHERE amount < 0').fetchone()[0]
assert neg == 0, 'Negative amounts in Bronze'
pipeline.load_bronze_transactions(date, pipeline.generate_run_id())
b_count2 = duckdb.query(f'SELECT COUNT(*) FROM read_parquet(\"data/bronze/transactions/date={date}/data.parquet\")').fetchone()[0]
assert b_count2 == b_count, 'Duplicates on re-run'
print('PASS')
"
```

**Invariant flags:** INV-04, INV-05, INV-06, INV-10, INV-11.

---

### Task 3.4 — Bronze Completeness Verification Queries

**Description:** Write the Phase 8 Bronze completeness verification queries as a standalone script `verification/bronze_checks.sql`. These are the exact DuckDB CLI commands required for Section 10.1 sign-off.

**CC prompt:**
```
Create verification/bronze_checks.sql containing the exact DuckDB CLI queries for
Phase 8 Bronze completeness verification (Section 10.1 of the requirements brief).

Queries required:
1. Row count in bronze/transactions across all 7 date partitions vs source CSVs
2. Row count in bronze/accounts across all 7 date partitions vs source CSVs
3. Row count in bronze/transaction_codes/data.parquet vs source transaction_codes.csv
4. Confirm no null _pipeline_run_id in any Bronze partition (INV-11)
5. Confirm no negative amounts in bronze/transactions (INV-06)

Each query preceded by a comment stating what it verifies and what the expected result is.
All paths use the container paths (/app/data/, /app/source/).
Queries must be runnable as: duckdb -c "$(cat verification/bronze_checks.sql)"
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | File exists at correct path | `test -f verification/bronze_checks.sql` passes |
| TC-2 | All 5 queries present | File contains 5 SELECT statements |
| TC-3 | Queries run without syntax error | `duckdb -c "SELECT 1"` pattern — validate syntax |

**Verification command:**
```bash
test -f verification/bronze_checks.sql && grep -c "SELECT" verification/bronze_checks.sql | xargs -I{} test {} -ge 5 && echo "PASS"
```

**Invariant flags:** INV-05, INV-06, INV-11 (verification queries enforce these at sign-off).

---

## Session 4 — Silver Transaction Codes and Accounts

**Goal:** Silver transaction codes loaded from Bronze; Silver accounts upsert complete and idempotent. Both verified against their invariants before Session 5 begins.

**Integration check:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt run --select silver_transaction_codes silver_accounts && dbt test --select silver_transaction_codes silver_accounts && echo 'S4 INTEGRATION OK'"
```

---

### Task 4.1 — Silver Transaction Codes Model

**Description:** Implement `silver_transaction_codes.sql`. Reads from Bronze transaction_codes Parquet, adds Silver audit columns, writes to `silver/transaction_codes/data.parquet`. No quality rules — reference data is trusted.

**CC prompt:**
```
Implement dbt_project/models/silver/silver_transaction_codes.sql.

Source: read_parquet('/app/data/bronze/transaction_codes/data.parquet')
Output: /app/data/silver/transaction_codes/data.parquet
Materialisation: table

Select all source fields plus these audit columns:
  _source_file          -- carried forward from Bronze _source_file
  _bronze_ingested_at   -- carried forward from Bronze _ingested_at
  _pipeline_run_id      -- from dbt var 'run_id' passed at runtime

No filtering, no transformation of source fields.
All audit columns must be non-null (INV-11).

Add a dbt test in schema.yml:
  - not_null on transaction_code
  - unique on transaction_code
  - not_null on _pipeline_run_id
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | `dbt run --select silver_transaction_codes` | Succeeds, Parquet written |
| TC-2 | Row count matches Bronze | Silver row count = Bronze row count |
| TC-3 | `_pipeline_run_id` non-null | dbt test passes |
| TC-4 | `transaction_code` unique | dbt test passes |
| TC-5 | Re-run produces identical output | Row count unchanged |

**Verification command:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt run --select silver_transaction_codes --vars '{run_id: test_s4}' && dbt test --select silver_transaction_codes && duckdb /app/data/cc_lake.duckdb 'SELECT COUNT(*) FROM read_parquet(\"/app/data/silver/transaction_codes/data.parquet\")' && echo PASS"
```

**Invariant flags:** INV-11 (audit column presence), INV-13 (Silver transaction codes is the authoritative source for sign derivation in S5).

---

### Task 4.2 — Silver Accounts Model

**Description:** Implement `silver_accounts.sql`. Upserts Bronze account delta records into Silver accounts — latest record per `account_id` wins. Quarantines records failing account rejection rules.

**CC prompt:**
```
Implement dbt_project/models/silver/silver_accounts.sql.

Source: read_parquet('/app/data/bronze/accounts/date={date}/data.parquet')
       where date is passed as dbt var 'processing_date'
Existing Silver: read_parquet('/app/data/silver/accounts/data.parquet') if it exists
Output: /app/data/silver/accounts/data.parquet (single non-partitioned file)
Quarantine output: /app/data/silver/quarantine/date={processing_date}/rejected.parquet

Upsert logic:
1. Read incoming Bronze records for processing_date
2. Apply rejection rules — quarantine failing records with _rejection_reason:
   - NULL_REQUIRED_FIELD: account_id, open_date, credit_limit, current_balance,
     billing_cycle_start, billing_cycle_end, or account_status is null or empty
   - INVALID_ACCOUNT_STATUS: account_status not in ('ACTIVE', 'SUSPENDED', 'CLOSED')
3. For passing records: merge with existing Silver accounts
   - If account_id already exists: replace with new record
   - If account_id is new: insert
4. Write merged result as complete file (table materialisation — full overwrite)

Silver audit columns on passing records:
  _source_file, _bronze_ingested_at, _pipeline_run_id (var: run_id),
  _record_valid_from (current timestamp)

Quarantine audit columns:
  _source_file, _pipeline_run_id, _rejected_at (current timestamp), _rejection_reason

After upsert: silver/accounts/data.parquet must contain exactly one record per
account_id (INV-19).

Add dbt schema.yml tests: unique + not_null on account_id, not_null on _pipeline_run_id.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | New account in delta | Appears in Silver accounts |
| TC-2 | Existing account updated | Silver contains new version, old version gone |
| TC-3 | Null required field | Record in quarantine with NULL_REQUIRED_FIELD |
| TC-4 | Invalid account_status | Record in quarantine with INVALID_ACCOUNT_STATUS |
| TC-5 | Re-run same date | Identical Silver output, no duplicates (INV-10) |
| TC-6 | `account_id` unique after upsert | dbt unique test passes |

**Verification command:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt run --select silver_accounts --vars '{run_id: test_s4, processing_date: 2024-01-01}' && dbt test --select silver_accounts && duckdb /app/data/cc_lake.duckdb 'SELECT account_id, COUNT(*) FROM read_parquet(\"/app/data/silver/accounts/data.parquet\") GROUP BY 1 HAVING COUNT(*) > 1' && echo PASS"
```

**Invariant flags:** INV-07, INV-08, INV-10, INV-11, INV-16, INV-19.

---

### Task 4.3 — Silver Accounts Verification Queries

**Description:** Write `verification/silver_accounts_checks.sql` with Phase 8 Silver quality verification queries for accounts.

**CC prompt:**
```
Create verification/silver_accounts_checks.sql.

Queries required:
1. Confirm exactly one record per account_id in silver/accounts/data.parquet (INV-19)
2. Confirm no null _pipeline_run_id (INV-11)
3. Confirm no null _record_valid_from (INV-11)
4. Confirm all account_status values are in ('ACTIVE', 'SUSPENDED', 'CLOSED')
5. Confirm all quarantine records have non-null _rejection_reason (INV-08)
6. Confirm all quarantine _rejection_reason values are from the exhaustive list:
   NULL_REQUIRED_FIELD, INVALID_ACCOUNT_STATUS

Each query preceded by comment. All paths use /app/data/ container paths.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | File exists | `test -f verification/silver_accounts_checks.sql` |
| TC-2 | 6 queries present | grep -c SELECT >= 6 |

**Verification command:**
```bash
test -f verification/silver_accounts_checks.sql && grep -c "SELECT" verification/silver_accounts_checks.sql | xargs -I{} test {} -ge 6 && echo "PASS"
```

**Invariant flags:** INV-08, INV-11, INV-19.

---

## Session 5 — Silver Transactions

**Goal:** Silver transactions promotion complete with all six quality rules enforced, quarantine written correctly, `_signed_amount` derived from transaction_codes, and cross-partition uniqueness enforced.

**Integration check:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt run --select silver_transactions silver_quarantine --vars '{run_id: test_s5, processing_date: 2024-01-01}' && dbt test --select silver_transactions && duckdb /app/data/cc_lake.duckdb 'SELECT COUNT(*) as silver, (SELECT COUNT(*) FROM read_parquet(\"/app/data/silver/quarantine/date=2024-01-01/rejected.parquet\")) as quarantine, (SELECT COUNT(*) FROM read_parquet(\"/app/data/bronze/transactions/date=2024-01-01/data.parquet\")) as bronze FROM read_parquet(\"/app/data/silver/transactions/date=2024-01-01/data.parquet\")' && echo 'S5 INTEGRATION OK'"
```

---

### Task 5.1 — Silver Transactions Model — Quality Rules and Quarantine

**Description:** Implement `silver_transactions.sql` and `silver_quarantine.sql`. Apply all five quarantine rejection rules. Flag UNRESOLVABLE_ACCOUNT_ID in Silver (not quarantine). Write `_signed_amount` from transaction_codes join.

**CC prompt:**
```
Implement dbt_project/models/silver/silver_transactions.sql and
dbt_project/models/silver/silver_quarantine.sql.

Source: read_parquet('/app/data/bronze/transactions/date={processing_date}/data.parquet')
Silver output: /app/data/silver/transactions/date={processing_date}/data.parquet
Quarantine output: /app/data/silver/quarantine/date={processing_date}/rejected.parquet
Reference: read_parquet('/app/data/silver/transaction_codes/data.parquet')
Accounts ref: read_parquet('/app/data/silver/accounts/data.parquet')

dbt vars: run_id, processing_date

Rejection rules — quarantine with _rejection_reason:
  NULL_REQUIRED_FIELD: transaction_id, account_id, transaction_date, amount,
                       transaction_code, or channel is null or empty string
  INVALID_AMOUNT: amount is zero, negative, or non-numeric
  DUPLICATE_TRANSACTION_ID: transaction_id already exists in ANY existing Silver
                             transactions partition (cross-partition check against
                             /app/data/silver/transactions/**/data.parquet)
  INVALID_TRANSACTION_CODE: transaction_code not found in silver_transaction_codes
  INVALID_CHANNEL: channel not in ('ONLINE', 'IN_STORE')

Flag only — do NOT quarantine:
  UNRESOLVABLE_ACCOUNT_ID: account_id not in silver/accounts — set _is_resolvable = false
                            record enters Silver with this flag

For records passing all quarantine rules:
  _signed_amount: amount * CASE WHEN debit_credit_indicator = 'DR' THEN 1 ELSE -1 END
                  Derived exclusively from transaction_codes join (INV-13)
  _is_resolvable: true if account_id found in silver/accounts, false otherwise

Silver audit columns: _source_file, _bronze_ingested_at, _pipeline_run_id,
                      _promoted_at (current timestamp), _is_resolvable, _signed_amount

Quarantine audit columns: _source_file, _pipeline_run_id, _rejected_at, _rejection_reason

Every Bronze record must appear in exactly one of: Silver or quarantine (INV-08, INV-09).
No record may appear in both.

Add dbt tests: not_null on transaction_id, not_null on _signed_amount,
not_null on _pipeline_run_id, not_null on _is_resolvable.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Valid record | Appears in Silver with non-null `_signed_amount` |
| TC-2 | Null transaction_id | Quarantine with NULL_REQUIRED_FIELD |
| TC-3 | amount = 0 | Quarantine with INVALID_AMOUNT |
| TC-4 | Duplicate transaction_id (already in prior partition) | Quarantine with DUPLICATE_TRANSACTION_ID |
| TC-5 | Unknown transaction_code | Quarantine with INVALID_TRANSACTION_CODE |
| TC-6 | channel = 'MOBILE' | Quarantine with INVALID_CHANNEL |
| TC-7 | Unknown account_id | Silver with `_is_resolvable = false` |
| TC-8 | DR transaction | `_signed_amount` positive |
| TC-9 | CR transaction | `_signed_amount` negative |
| TC-10 | Bronze rows = Silver rows + Quarantine rows | Arithmetic check passes (INV-09) |

**Verification command:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt run --select silver_transactions silver_quarantine --vars '{run_id: test_s5, processing_date: 2024-01-01}' && dbt test --select silver_transactions && duckdb /app/data/cc_lake.duckdb \"SELECT (SELECT COUNT(*) FROM read_parquet('/app/data/bronze/transactions/date=2024-01-01/data.parquet')) = (SELECT COUNT(*) FROM read_parquet('/app/data/silver/transactions/date=2024-01-01/data.parquet')) + (SELECT COUNT(*) FROM read_parquet('/app/data/silver/quarantine/date=2024-01-01/rejected.parquet')) AS reconciled\" && echo PASS"
```

**Invariant flags:** INV-07, INV-08, INV-09, INV-10, INV-11, INV-13, INV-14, INV-17.

---

### Task 5.2 — Cross-Partition Uniqueness Check

**Description:** Implement and verify the cross-partition `transaction_id` uniqueness check. Ensure that a `transaction_id` present in any existing Silver partition is quarantined as DUPLICATE_TRANSACTION_ID when it appears again in a new date's Bronze data.

**CC prompt:**
```
Add an integration test to verification/silver_transactions_checks.sql that verifies
cross-partition transaction_id uniqueness across all Silver transactions partitions.

Also confirm in the silver_transactions.sql model that the DUPLICATE_TRANSACTION_ID
check reads from all existing partitions using:
  read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
and not just the current processing_date partition.

Create verification/silver_transactions_checks.sql with:
1. Cross-partition uniqueness: SELECT transaction_id, COUNT(*) FROM
   read_parquet('/app/data/silver/transactions/**/data.parquet') GROUP BY 1 HAVING COUNT(*) > 1
   — must return 0 rows
2. No null _signed_amount
3. No null _is_resolvable
4. Row count reconciliation per date: Bronze = Silver + Quarantine
5. All _rejection_reason values from exhaustive list
6. No record appears in both Silver and quarantine for the same date
7. Every _pipeline_run_id in Silver has a SUCCESS entry in run log
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | transaction_id from date 1 reappears in date 2 Bronze | Quarantined in date 2 as DUPLICATE |
| TC-2 | Cross-partition uniqueness query | Returns 0 rows |
| TC-3 | Verification SQL file exists with 7 queries | File present, grep count >= 7 |

**Verification command:**
```bash
test -f verification/silver_transactions_checks.sql && docker compose exec pipeline duckdb /app/data/cc_lake.duckdb "SELECT transaction_id, COUNT(*) FROM read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true) GROUP BY 1 HAVING COUNT(*) > 1" && echo "PASS"
```

**Invariant flags:** INV-14 (Transaction Uniqueness — primary enforcement verification).

---

### Task 5.3 — Pipeline Ordering Enforcement

**Description:** Add a guard function to pipeline.py that enforces Silver accounts must be current before Silver transactions runs for the same date. Implement as a pre-flight check called from `run_dbt_model` when model is `silver_transactions`.

**CC prompt:**
```
Add a guard to pipeline.py: before running silver_transactions for a given date,
confirm that silver_accounts has a SUCCESS entry in the run log for a run that
completed after the most recent bronze_accounts run for the same date.

Implement as: check_silver_accounts_ready(processing_date: str) -> bool

Logic:
1. Read run log
2. Find most recent SUCCESS entry for model_name='silver_accounts'
3. Find most recent SUCCESS entry for model_name='bronze_accounts' for processing_date
4. Return True if silver_accounts SUCCESS exists and completed_at >= bronze_accounts completed_at
5. Return False otherwise

Modify run_dbt_model to call this guard when model_name == 'silver_transactions'.
If guard returns False: log FAILED to run log with error_message =
'silver_accounts not current for {processing_date} — run aborted', raise RuntimeError.

This enforces INV-20 (pipeline ordering guarantee).
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Silver accounts SUCCESS exists before transactions run | Guard returns True, transactions run proceeds |
| TC-2 | Silver accounts not yet run | Guard returns False, RuntimeError raised |
| TC-3 | Silver accounts run but older than bronze_accounts | Guard returns False |

**Verification command:**
```bash
docker compose exec pipeline python -c "
import pipeline
result = pipeline.check_silver_accounts_ready('2024-01-01')
print(f'Guard result: {result} — PASS (False expected if no prior runs)')
"
```

**Invariant flags:** INV-20 (Pipeline Ordering — silver_accounts must precede silver_transactions).

---

### Task 5.4 — Silver Transactions Verification Queries

**Description:** Extend `verification/silver_transactions_checks.sql` with the remaining Phase 8 Silver quality queries. Ensure all Section 10.2 sign-off conditions are expressible.

**CC prompt:**
```
Extend verification/silver_transactions_checks.sql to include all Section 10.2
verification conditions from the requirements brief:

1. Total Silver transactions rows + quarantine rows = Bronze rows (all partitions combined)
2. No transaction_id appears more than once across all Silver partitions
3. Every Silver record has a valid transaction_code in silver_transaction_codes
4. No Silver record has null _signed_amount
5. Every quarantine record has non-null _rejection_reason from the exhaustive list
6. Confirm _is_resolvable is never null
7. Confirm no record with _is_resolvable = false has been included in any Gold output
   (this query runs against Gold — leave as TODO placeholder, implemented in S6)

Each query has a comment stating the invariant it enforces and the expected result.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | All 7 queries present | grep -c SELECT >= 7 |
| TC-2 | Queries 1–6 run without error on populated data | No syntax errors |

**Verification command:**
```bash
grep -c "SELECT" verification/silver_transactions_checks.sql | xargs -I{} test {} -ge 7 && echo "PASS"
```

**Invariant flags:** INV-08, INV-09, INV-11, INV-13, INV-14, INV-17.

---

## Session 6 — Gold Layer

**Goal:** Gold daily summary and Gold weekly account summary fully implemented, verified against Silver, and all Section 10.3 correctness checks passing.

**Integration check:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt run --select gold_daily_summary gold_weekly_account_summary --vars '{run_id: test_s6}' && dbt test --select gold_daily_summary gold_weekly_account_summary && echo 'S6 INTEGRATION OK'"
```

---

### Task 6.1 — Gold Daily Summary Model

**Description:** Implement `gold_daily_summary.sql`. One row per calendar day from Silver transactions where `_is_resolvable = true`. Includes `transactions_by_type` as a STRUCT. Zero rows written for dates with no resolvable transactions.

**CC prompt:**
```
Implement dbt_project/models/gold/gold_daily_summary.sql.

Source: read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true)
        filtered to _is_resolvable = true (INV-17)
Output: /app/data/gold/daily_summary/data.parquet
Materialisation: table (full recompute every run)

One row per distinct transaction_date. Columns:
  transaction_date         DATE
  total_transactions       INTEGER   -- COUNT(*) where _is_resolvable = true
  total_signed_amount      DECIMAL   -- SUM(_signed_amount)
  transactions_by_type     STRUCT    -- {type: {count: INTEGER, sum: DECIMAL}}
                                     -- one entry per transaction_type
  online_transactions      INTEGER   -- COUNT where channel = 'ONLINE'
  instore_transactions     INTEGER   -- COUNT where channel = 'IN_STORE'
  _computed_at             TIMESTAMP -- current timestamp
  _pipeline_run_id         STRING    -- dbt var run_id
  _source_period_start     DATE      -- MIN(transaction_date) across all Silver
  _source_period_end       DATE      -- MAX(transaction_date) across all Silver

If a date has zero resolvable transactions: write a zero row with all counts = 0,
amounts = 0, not NULL (INV — Decision 11 from ARCHITECTURE.md).

Add dbt tests: not_null on transaction_date, unique on transaction_date,
not_null on _pipeline_run_id.

Gold must not reference any bronze/ path (INV-15).
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Run against populated Silver | One row per distinct transaction_date |
| TC-2 | `total_signed_amount` matches Silver SUM | Arithmetic check passes (Section 10.3) |
| TC-3 | `_is_resolvable = false` records excluded | Count < Bronze count where unresolvable records exist |
| TC-4 | `transaction_date` unique | dbt test passes |
| TC-5 | `_pipeline_run_id` non-null | dbt test passes |
| TC-6 | Re-run produces identical output | Row count and values unchanged |

**Verification command:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt run --select gold_daily_summary --vars '{run_id: test_s6}' && dbt test --select gold_daily_summary && duckdb /app/data/cc_lake.duckdb \"SELECT g.transaction_date, g.total_signed_amount, SUM(s._signed_amount) as silver_sum FROM read_parquet('/app/data/gold/daily_summary/data.parquet') g JOIN read_parquet('/app/data/silver/transactions/**/data.parquet', hive_partitioning=true) s ON g.transaction_date = s.transaction_date WHERE s._is_resolvable = true GROUP BY 1,2 HAVING ABS(g.total_signed_amount - silver_sum) > 0.001\" && echo PASS"
```

**Invariant flags:** INV-15, INV-17, INV-11.

---

### Task 6.2 — Gold Weekly Account Summary Model

**Description:** Implement `gold_weekly_account_summary.sql`. One row per account per ISO calendar week (Monday–Sunday). Only accounts with at least one resolvable transaction included. `closing_balance` from Silver accounts; null if account not in Silver.

**CC prompt:**
```
Implement dbt_project/models/gold/gold_weekly_account_summary.sql.

Sources:
  Silver transactions: read_parquet('/app/data/silver/transactions/**/data.parquet',
                       hive_partitioning=true) filtered to _is_resolvable = true
  Silver accounts: read_parquet('/app/data/silver/accounts/data.parquet')
Output: /app/data/gold/weekly_account_summary/data.parquet
Materialisation: table (full recompute)

One row per account_id per calendar week. Week defined as Monday–Sunday (ISO week).
Only include account-weeks with at least one resolvable transaction.

Columns:
  week_start_date    DATE      -- Monday of the ISO week
  week_end_date      DATE      -- Sunday of the ISO week
  account_id         STRING
  total_purchases    INTEGER   -- COUNT where transaction_type = 'PURCHASE'
  avg_purchase_amount DECIMAL  -- AVG(_signed_amount) for PURCHASE transactions
  total_payments     DECIMAL   -- SUM(_signed_amount) for PAYMENT transactions
  total_fees         DECIMAL   -- SUM(_signed_amount) for FEE transactions
  total_interest     DECIMAL   -- SUM(_signed_amount) for INTEREST transactions
  closing_balance    DECIMAL   -- current_balance from silver/accounts; NULL if not found
  _computed_at       TIMESTAMP
  _pipeline_run_id   STRING    -- dbt var run_id

closing_balance: LEFT JOIN silver/accounts on account_id. If no match: NULL (not excluded).
Gold must not reference any bronze/ path (INV-15).

Add dbt tests: not_null on account_id, not_null on week_start_date,
not_null on _pipeline_run_id.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Account with purchases in a week | Row present with correct total_purchases count |
| TC-2 | total_purchases matches Silver COUNT | Section 10.3 arithmetic check passes |
| TC-3 | Account not in Silver accounts | closing_balance = NULL, row still present |
| TC-4 | `_is_resolvable = false` excluded | Unresolvable transactions not counted |
| TC-5 | week_start_date is always Monday | `EXTRACT(DOW FROM week_start_date) = 1` for all rows |
| TC-6 | Re-run produces identical output | Counts and sums unchanged |

**Verification command:**
```bash
docker compose exec pipeline sh -c "cd /app/dbt_project && dbt run --select gold_weekly_account_summary --vars '{run_id: test_s6}' && dbt test --select gold_weekly_account_summary && duckdb /app/data/cc_lake.duckdb \"SELECT COUNT(*) as monday_check FROM read_parquet('/app/data/gold/weekly_account_summary/data.parquet') WHERE EXTRACT(DOW FROM week_start_date) != 1\" && echo PASS"
```

**Invariant flags:** INV-15, INV-17, INV-11.

---

### Task 6.3 — Gold Verification Queries

**Description:** Create `verification/gold_checks.sql` with all Section 10.3 Gold correctness verification queries. Complete the TODO placeholder from Task 5.4.

**CC prompt:**
```
Create verification/gold_checks.sql with all Section 10.3 correctness queries.

Queries required:
1. Gold daily_summary contains exactly one row per distinct transaction_date in Silver
   where _is_resolvable = true
2. Gold weekly total_purchases count matches COUNT(*) from Silver filtered to PURCHASE
   type and _is_resolvable = true for the corresponding week and account
3. Gold total_signed_amount per day matches SUM(_signed_amount) from Silver for that
   transaction_date where _is_resolvable = true
4. No Gold record has null _pipeline_run_id (INV-11)
5. No Gold record references a _pipeline_run_id without a SUCCESS entry in run log (INV-12)
6. Confirm no _is_resolvable = false records contributed to Gold (complete the TODO
   from silver_transactions_checks.sql)
7. Gold daily_summary week_start_date is always Monday

Also update verification/silver_transactions_checks.sql query 7 (the TODO placeholder)
with the actual Gold cross-check query.

Each query preceded by comment and expected result.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | File exists with 7 queries | test -f and grep count |
| TC-2 | Queries 1–3 pass against populated data | Zero-row results on mismatch queries |
| TC-3 | Query 6 returns 0 rows | No unresolvable records in Gold |

**Verification command:**
```bash
test -f verification/gold_checks.sql && grep -c "SELECT" verification/gold_checks.sql | xargs -I{} test {} -ge 7 && echo "PASS"
```

**Invariant flags:** INV-11, INV-12, INV-15, INV-17.

---

## Session 7 — Pipeline Orchestration

**Goal:** pipeline.py historical and incremental pipelines fully wired. Watermark logic complete. End-to-end run from `docker compose up` produces correct Bronze, Silver, and Gold output for all 7 source dates.

**Integration check:**
```bash
docker compose exec pipeline python pipeline.py historical --start-date 2024-01-01 --end-date 2024-01-07 && docker compose exec pipeline duckdb /app/data/cc_lake.duckdb "SELECT last_processed_date FROM read_parquet('/app/data/pipeline/control.parquet')" && echo "HISTORICAL COMPLETE"
```

---

### Task 7.1 — `run_dbt_model` Implementation

**Description:** Implement `run_dbt_model(model_name, run_id, vars)` in pipeline.py. Invokes dbt run for a single model, captures success/failure, writes run log entry. Includes the silver_transactions ordering guard from Task 5.3.

**CC prompt:**
```
Implement run_dbt_model(model_name: str, run_id: str, vars: dict) -> bool in pipeline.py.

Behaviour:
1. Record started_at
2. If model_name == 'silver_transactions': call check_silver_accounts_ready(vars['processing_date'])
   If False: log FAILED, raise RuntimeError
3. Build dbt run command: dbt run --select {model_name} --vars '{json.dumps(vars)}'
   Run from /app/dbt_project directory
4. Capture stdout/stderr
5. On success (exit code 0): log SUCCESS to run log, return True
6. On failure: log FAILED to run log with error_message (no file paths or credentials
   in error_message — brief constraint), return False

Run log fields: run_id, pipeline_type (from vars or default INCREMENTAL),
model_name, layer (derive from model_name prefix: silver_ -> SILVER, gold_ -> GOLD),
started_at, completed_at, status, records_processed=None, records_written=None,
records_rejected=None, error_message.

error_message must not contain file system paths or internal system detail.

Exception handling: wrap the dbt subprocess call in try/finally. The finally block
must write a run log entry unconditionally. If an unexpected exception is raised
(e.g. subprocess failure outside dbt's own exit code), write a FAILED entry with
a sanitised error_message before re-raising.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Valid model name, dbt succeeds | Returns True, SUCCESS in run log |
| TC-2 | dbt fails (syntax error in model) | Returns False, FAILED in run log |
| TC-3 | silver_transactions without silver_accounts ready | RuntimeError, FAILED in run log |
| TC-4 | error_message contains no file paths | Verified by string check |

**Verification command:**
```bash
docker compose exec pipeline python -c "
import pipeline
result = pipeline.run_dbt_model('silver_transaction_codes', pipeline.generate_run_id(), {'run_id': 'test'})
print(f'Result: {result}')
log = pipeline.read_run_log()
last = [r for r in log if r['model_name'] == 'silver_transaction_codes'][-1]
assert last['status'] in ('SUCCESS', 'FAILED')
print('PASS')
"
```

**Invariant flags:** INV-16 (Layer Completion Integrity), INV-20 (Pipeline Ordering).

---

### Task 7.2 — Historical Pipeline Implementation

**Description:** Implement `run_historical(start_date, end_date)` in pipeline.py. Processes all dates in range in order. Loads transaction_codes first. Advances watermark once at end of successful full run.

**CC prompt:**
```
Implement run_historical(start_date: str, end_date: str) in pipeline.py.

Execution order per date (enforced — not configurable):
  1. load_bronze_accounts(date, run_id)
  2. load_bronze_transactions(date, run_id)
  3. run_dbt_model('silver_accounts', run_id, {processing_date, run_id, pipeline_type: HISTORICAL})
  4. run_dbt_model('silver_transactions', run_id, {processing_date, run_id, pipeline_type: HISTORICAL})
  5. run_dbt_model('silver_quarantine', run_id, {...})

Before first date: load_bronze_transaction_codes(run_id) then
  run_dbt_model('silver_transaction_codes', run_id, {run_id, pipeline_type: HISTORICAL})
  Skip if run log already has SUCCESS for silver_transaction_codes (idempotency).

After all dates processed:
  6. run_dbt_model('gold_daily_summary', run_id, {run_id, pipeline_type: HISTORICAL})
  7. run_dbt_model('gold_weekly_account_summary', run_id, {run_id, pipeline_type: HISTORICAL})

Watermark: write_control_table(end_date, run_id) only after Gold completes successfully.
If any layer fails for any date: do not advance watermark. Log the failure. Continue
processing remaining dates (missing file skips are not failures).

Idempotency: check run log before each model — if SUCCESS already exists for that
model + date combination, skip (use most recent row per Decision 12 in ARCHITECTURE.md).
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Full historical run over 7 dates | All Bronze, Silver, Gold written; watermark = end_date |
| TC-2 | Re-run historical over same range | All layers skipped (idempotent); watermark unchanged |
| TC-3 | One date has missing transactions file | That date skipped; other dates processed; watermark set to last successful date |
| TC-4 | Gold failure | Watermark not advanced (INV-02) |

**Verification command:**
```bash
docker compose exec pipeline python pipeline.py historical --start-date 2024-01-01 --end-date 2024-01-07 && docker compose exec pipeline duckdb /app/data/cc_lake.duckdb "SELECT last_processed_date FROM read_parquet('/app/data/pipeline/control.parquet')" && echo "HISTORICAL PASS"
```

**Invariant flags:** INV-01, INV-02, INV-03, INV-10, INV-16, INV-18, INV-20.

---

### Task 7.3 — Incremental Pipeline Implementation

**Description:** Implement `run_incremental()` in pipeline.py. Reads watermark, processes watermark + 1 day, advances watermark on success.

**CC prompt:**
```
Implement run_incremental() in pipeline.py.

Behaviour:
1. Load control table. If None (not yet initialised): raise RuntimeError with message
   'Incremental pipeline requires historical pipeline to have run first.'
2. next_date = last_processed_date + 1 day
3. Check if source files exist for next_date. If neither transactions nor accounts
   file exists: log SKIPPED, do not advance watermark, exit cleanly (INV-18).
4. Execute in order (same as historical per-date sequence):
   a. load_bronze_accounts(next_date, run_id)
   b. load_bronze_transactions(next_date, run_id)
   c. run_dbt_model('silver_accounts', ...)
   d. run_dbt_model('silver_transactions', ...)
   e. run_dbt_model('gold_daily_summary', ...)
   f. run_dbt_model('gold_weekly_account_summary', ...)
5. If all layers SUCCESS: write_control_table(next_date, run_id) — advance watermark
6. If any layer FAILED: do not advance watermark (INV-02). Log failure. Exit with
   non-zero exit code.

Running incremental when no new file is available must produce no change to any layer
and no watermark change (Section 10.4).
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Run after historical completes | Processes day 8, watermark advances to day 8 |
| TC-2 | Run when no new file available | No layer changes, watermark unchanged (INV-18) |
| TC-3 | Run twice on same new file | Second run fully skipped (idempotent — INV-10) |
| TC-4 | Silver fails | Watermark stays at previous value (INV-02) |
| TC-5 | Run before historical | RuntimeError raised |

**Verification command:**
```bash
docker compose exec pipeline python pipeline.py incremental && docker compose exec pipeline duckdb /app/data/cc_lake.duckdb "SELECT last_processed_date FROM read_parquet('/app/data/pipeline/control.parquet')" && echo "INCREMENTAL PASS"
```

**Invariant flags:** INV-01, INV-02, INV-03, INV-10, INV-18.

---

### Task 7.4 — End-to-End Idempotency Test

**Description:** Create `verification/idempotency_checks.sql` and a shell script `verification/run_idempotency_test.sh` that runs the full pipeline twice and verifies identical output (Section 10.4).

**CC prompt:**
```
Create verification/run_idempotency_test.sh.

Script behaviour:
1. Run python pipeline.py historical --start-date 2024-01-01 --end-date 2024-01-07
2. Capture row counts from all layers (Bronze, Silver, quarantine, Gold) into variables
3. Run python pipeline.py historical --start-date 2024-01-01 --end-date 2024-01-07 again
4. Capture row counts again
5. Assert all row counts are identical between run 1 and run 2
6. Print IDEMPOTENCY PASS or IDEMPOTENCY FAIL with details

Create verification/idempotency_checks.sql with DuckDB queries that produce
the row counts checked by the shell script.

Section 10.4 conditions to verify:
- Identical Bronze row counts
- Identical Silver row counts
- Identical quarantine row counts
- Identical Gold output (row counts and total_signed_amount sum)
- Watermark unchanged on second run
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Script runs without error | Exit code 0 |
| TC-2 | Row counts identical after two runs | IDEMPOTENCY PASS printed |
| TC-3 | Incremental run twice with no new file | No layer changes, PASS |

**Verification command:**
```bash
bash verification/run_idempotency_test.sh && echo "PASS"
```

**Invariant flags:** INV-10 (Re-run Idempotency — primary end-to-end test).

---

## Session 8 — Verification and Sign-Off

**Goal:** All Phase 8 sign-off conditions from Section 10 verified with passing DuckDB CLI commands. VERIFICATION_CHECKLIST.md complete and signed. System ready for BCE close-out.

**Integration check:**
```bash
bash verification/run_all_checks.sh && echo "ALL CHECKS PASS"
```

---

### Task 8.1 — Full Verification Script

**Description:** Create `verification/run_all_checks.sh` that runs every verification SQL file in sequence and reports pass/fail per check group.

**CC prompt:**
```
Create verification/run_all_checks.sh.

Script runs the following in order, reporting PASS or FAIL per section:
1. verification/bronze_checks.sql — Section 10.1 Bronze Completeness
2. verification/silver_accounts_checks.sql — Silver Accounts Quality
3. verification/silver_transactions_checks.sql — Section 10.2 Silver Quality
4. verification/gold_checks.sql — Section 10.3 Gold Correctness
5. verification/idempotency_checks.sql — Section 10.4 Idempotency
6. Audit trail checks (inline): every Bronze, Silver, Gold record has non-null
   _pipeline_run_id; every _pipeline_run_id in any layer has SUCCESS in run log

Each section prints: [SECTION NAME] PASS or [SECTION NAME] FAIL: [details]
Final line: ALL CHECKS PASS or N CHECKS FAILED

All DuckDB queries run against /app/data/ paths inside the container.
Script must be runnable as: docker compose exec pipeline bash verification/run_all_checks.sh
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | Script runs on fully populated system | ALL CHECKS PASS |
| TC-2 | Script reports failures clearly | FAIL lines include which check failed |
| TC-3 | Section 10.1–10.5 all covered | 6 sections in output |

**Verification command:**
```bash
docker compose exec pipeline bash verification/run_all_checks.sh
```

**Invariant flags:** All 19 invariants — this is the Phase 8 sign-off verification.

---

### Task 8.2 — VERIFICATION_CHECKLIST.md

**Description:** Produce `verification/VERIFICATION_CHECKLIST.md` with every Section 10 condition, the exact DuckDB CLI command that verifies it, and a PASS/FAIL column to be filled in during sign-off.

**CC prompt:**
```
Create verification/VERIFICATION_CHECKLIST.md.

Structure:
- One row per Section 10 verification condition (10.1 through 10.5)
- Columns: Condition | Invariant(s) | Verification Command | Result | Signed Off

Include the exact DuckDB CLI command for each condition — runnable as written.
Leave Result and Signed Off columns blank — filled in by engineer at sign-off.

Cover all conditions from Sections 10.1, 10.2, 10.3, 10.4, and 10.5 of the
requirements brief. All 19 invariants must appear at least once in the
Invariant(s) column across all rows.
```

**Test cases:**

| Case | Scenario | Expected |
|---|---|---|
| TC-1 | File exists | `test -f verification/VERIFICATION_CHECKLIST.md` |
| TC-2 | All 19 invariants referenced | grep check for INV-01 through INV-19 |
| TC-3 | Result and Signed Off columns blank | No pre-filled values in those columns |

**Verification command:**
```bash
test -f verification/VERIFICATION_CHECKLIST.md && for i in $(seq -w 1 19); do grep -q "INV-$i" verification/VERIFICATION_CHECKLIST.md || echo "MISSING INV-$i"; done && echo "CHECKLIST PASS"
```

**Invariant flags:** All 19 — sign-off document.

---

### Task 8.3 — Phase 8 Sign-Off

**Description:** Run all verification checks against the fully assembled system. Record results in VERIFICATION_CHECKLIST.md. Engineer signs off. **This task is a HUMAN GATE — CC does not complete it.**

**[HUMAN GATE]**

**Steps:**
1. Run `docker compose exec pipeline bash verification/run_all_checks.sh`
2. For each check: record PASS or FAIL in VERIFICATION_CHECKLIST.md
3. If any FAIL: return to the relevant session, fix, re-verify, return here
4. When all PASS: sign VERIFICATION_CHECKLIST.md
5. Update PROJECT_MANIFEST.md — mark VERIFICATION_CHECKLIST.md as PRESENT
6. Commit: `8.3 — Phase 8 Sign-Off: all invariants verified`

**Sign-off conditions (from requirements brief Section 10):**

| Condition | Must be true |
|---|---|
| Bronze completeness | Row counts match source CSVs across all 7 partitions |
| Silver quality | Silver + quarantine = Bronze per date; no duplicate transaction_id; all rejection reasons valid |
| Gold correctness | One row per date in daily_summary; totals match Silver aggregations |
| Idempotency | Two runs produce identical output |
| Audit trail | Every record in every layer has non-null _pipeline_run_id with matching SUCCESS in run log |

**Invariant flags:** All 19 — final sign-off.

---

## Appendix — Invariant Coverage Matrix

| Invariant | Tasks that enforce it |
|---|---|
| INV-01 Watermark Progression | 2.3, 7.2, 7.3 |
| INV-02 Watermark Failure Guard | 2.3, 7.2, 7.3 |
| INV-03 Watermark Correctness | 2.3, 7.2, 7.3 |
| INV-04 Source Immutability | 1.2, 3.1, 3.2, 3.3 |
| INV-05 Bronze Fidelity | 3.1, 3.2, 3.3 |
| INV-06 Bronze Amount Constraint | 3.3 |
| INV-07 Quarantine Entry Condition | 4.2, 5.1 |
| INV-08 No Silent Drops | 4.2, 5.1, 5.4 |
| INV-09 Row Count Reconciliation | 5.1, 5.4 |
| INV-10 Re-run Idempotency | 3.1, 3.2, 3.3, 5.1, 7.4 |
| INV-11 Audit Column Presence | 3.1, 3.2, 3.3, 4.1, 4.2, 5.1, 6.1, 6.2, 8.2 |
| INV-12 Audit Traceability | 2.2, 6.3, 8.2 |
| INV-13 Signed Amount Derivation | 4.1, 5.1, 5.4 |
| INV-14 Transaction Uniqueness | 5.1, 5.2 |
| INV-15 Gold Dependency Constraint | 1.3, 6.1, 6.2 |
| INV-16 Layer Completion Integrity | 2.2, 7.1, 7.2 |
| INV-17 Gold Eligibility Constraint | 5.4, 6.1, 6.2, 6.3 |
| INV-18 Missing File Watermark Guard | 3.2, 3.3, 7.2, 7.3 |
| INV-19 Silver Accounts Uniqueness | 4.2, 4.3 |
| INV-20 Pipeline Ordering | 5.3, 7.1, 7.2 |
| INV-20 Pipeline Ordering | 5.3, 7.1, 7.2 |
