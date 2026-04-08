# pbvi_de — Credit Card Transaction Data Pipeline

A Medallion architecture data pipeline (Bronze → Silver → Gold) that ingests daily credit card transaction CSV extracts, enforces data quality rules at each layer boundary, and produces Gold-layer aggregations queryable via DuckDB.

---

## Overview

The pipeline processes three entity types through three quality layers:

- **Bronze** — raw ingestion with audit columns; no quality filtering
- **Silver** — validation, deduplication, sign derivation, quarantine of rejected records
- **Gold** — aggregations over validated, resolvable Silver records only

All transformations are **fully idempotent** (safe to re-run), **air-gapped** (no outbound HTTP), and run as a **single command** via Docker Compose.

---

## Quick Start

```bash
# Historical load (first run, processes date range)
docker compose run pipeline python pipeline/pipeline_historical.py 2024-01-01 2024-01-07

# Incremental load (subsequent runs, processes next unprocessed date)
docker compose run pipeline python pipeline/pipeline_incremental.py
```

---

## Stack

| Concern | Choice |
|---|---|
| Container | Docker Compose |
| Base image | `python:3.11-slim` |
| Transformation | `dbt-core==1.7.*` + `dbt-duckdb==1.7.*` |
| Query engine | DuckDB (embedded, no server) |
| Storage format | Parquet on local filesystem |
| Source data | Read-only CSV files |

---

## Repository Structure

```
pbvi_de/
├── Dockerfile
├── docker-compose.yml
├── source/                          # Read-only CSV input files
│   ├── transaction_codes.csv        # Static reference data
│   ├── transactions_YYYY-MM-DD.csv  # Daily transaction files
│   └── accounts_YYYY-MM-DD.csv     # Daily account delta files
├── pipeline/
│   ├── pipeline_historical.py       # Entry point: full historical load
│   ├── pipeline_incremental.py      # Entry point: daily incremental load
│   ├── smoke_test.py
│   ├── verify_bronze.py / verify_silver.py / verify_gold.py
│   ├── verify_idempotency.py / verify_phase8.py
│   └── lib/
│       ├── bronze_loader.py         # Read-deduplicate-write Bronze ingestion
│       ├── run_log.py               # Parquet-backed run log
│       ├── watermark.py             # Control table management
│       ├── run_id.py                # UUID generation
│       └── paths.py                 # Path constants
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── silver/
│   │   │   ├── silver_transactions.sql
│   │   │   ├── silver_accounts.sql
│   │   │   ├── silver_transaction_codes.sql
│   │   │   └── silver_quarantine.sql
│   │   └── gold/
│   │       ├── gold_daily_summary.sql
│   │       └── gold_weekly_account_summary.sql
│   └── tests/
│       ├── test_conservation_law.sql
│       ├── test_gold_promotion_gate.sql
│       └── test_tx_codes_conservation.sql
├── data/                            # Generated output (gitignored)
└── docs/
    ├── ARCHITECTURE.md
    └── EXECUTION_PLAN.md
```

---

## Data Layer Paths

| Layer | Entity | Path |
|---|---|---|
| Bronze | Transactions | `data/bronze/transactions/date=YYYY-MM-DD/data.parquet` |
| Bronze | Accounts | `data/bronze/accounts/date=YYYY-MM-DD/data.parquet` |
| Bronze | Transaction Codes | `data/bronze/transaction_codes/data.parquet` |
| Silver | Transactions | `data/silver/transactions/date=YYYY-MM-DD/data.parquet` |
| Silver | Accounts | `data/silver/accounts/data.parquet` |
| Silver | Transaction Codes | `data/silver/transaction_codes/data.parquet` |
| Silver | Quarantine | `data/silver/quarantine/date=YYYY-MM-DD/rejected.parquet` |
| Gold | Daily Summary | `data/gold/daily_summary/data.parquet` |
| Gold | Weekly Account Summary | `data/gold/weekly_account_summary/data.parquet` |
| Pipeline | Control Table (watermark) | `data/pipeline/control.parquet` |
| Pipeline | Run Log | `data/pipeline/run_log.parquet` |

---

## Pipeline Flow

```
Source CSV
    │
    ▼
Bronze (Python + DuckDB)
  • Reads CSV, deduplicates on natural key, writes Parquet
  • Adds audit columns: _pipeline_run_id, _source_file, _ingested_at
    │
    ▼
Silver (dbt models)
  • Validates quality rules; rejects to quarantine with rejection codes
  • Derives _signed_amount via transaction_codes join (DR=positive, CR=negative)
  • Sets _is_resolvable flag via Silver accounts join
  • Conservation law test: Bronze count = Silver + Quarantine
    │
    ▼
Gold (dbt models)
  • Aggregates resolvable records only (WHERE _is_resolvable = true)
  • gold_daily_summary: one row per date
  • gold_weekly_account_summary: one row per (account_id, calendar week)
    │
    ▼
Watermark advances only if Bronze + Silver + Gold all succeed
```

---

## Quality Rules

### Transactions (Silver)

| Rejection Reason | Condition |
|---|---|
| `NULL_REQUIRED_FIELD` | Any required field is null |
| `INVALID_AMOUNT` | Amount ≤ 0 |
| `DUPLICATE_TRANSACTION_ID` | transaction_id already seen |
| `INVALID_TRANSACTION_CODE` | Code not found in transaction_codes |
| `INVALID_CHANNEL` | Channel not in allowed set |

### Accounts (Silver)

| Rejection Reason | Condition |
|---|---|
| `NULL_REQUIRED_FIELD` | Any required field is null |
| `INVALID_ACCOUNT_STATUS` | Status not ACTIVE, SUSPENDED, or CLOSED |

Transactions referencing an `account_id` not present in Silver accounts are **not** quarantined — they enter Silver with `_is_resolvable = false` and are excluded from Gold aggregations.

---

## Idempotency

Re-running the pipeline against the same input produces identical output at every layer:

- **Bronze**: existing records are deduplicated before write
- **Silver**: dbt incremental materialisation with `unique_key`
- **Gold**: full table recompute from Silver on every run
- **Run log**: deduplicated on `(run_id, model_name)`

---

## Key Invariants

The pipeline enforces 17 hard invariants. The most critical:

- **Conservation law (I-01)**: `COUNT(Bronze transactions) = COUNT(Silver transactions) + COUNT(Silver quarantine)` per date partition
- **Watermark gate (I-08)**: watermark advances only after all three layers succeed
- **Gold promotion gate (I-09)**: Gold models only run if conservation law passes for that date
- **Sign derivation (I-10)**: `_signed_amount` derived exclusively from `debit_credit_indicator` in the transaction_codes join
- **No unresolvable in Gold (I-17)**: `WHERE _is_resolvable = true` applied before all Gold aggregations

See `Claude.md` for the full invariant specification.

---

## Source Data

Seven days of sample data are included (`2024-01-01` through `2024-01-07`):

- `source/transaction_codes.csv` — static reference (loaded once, historical only)
- `source/transactions_YYYY-MM-DD.csv` — daily transaction files
- `source/accounts_YYYY-MM-DD.csv` — daily account state delta files

Source files are **read-only** and must never be modified by the pipeline.

---

## Development Notes

- All Silver and Gold transformation logic lives exclusively in dbt models
- Bronze ingestion uses Python + DuckDB directly (dbt not used for Bronze)
- No metadata database — run log and control table are Parquet files
- dbt database: `/app/data/pipeline/dbt.duckdb` (ephemeral, used as query engine only)
- See `docs/ARCHITECTURE.md` for design decisions and rationale
