# ARCHITECTURE.md — Credit Card Transactions Lake

## Changelog

| Version | Date | Author | Change |
|---|---|---|---|
| v1.0 | 2026-04-07 | Aadhya | Greenfield — Initial |

---

## 1. Problem Framing

### What This System Solves

A financial services client has data analysts and risk teams working directly off raw
CSV extract files. This produces three concrete problems: no quality control over what
analysts are querying, inconsistent results when different analysts work from different
file versions, and no audit trail tracing how raw data became the numbers being acted on.

This system sits between the raw CSV extracts and the analysts. It ingests daily
transaction and account files, enforces defined quality rules at each layer boundary,
and produces Gold-layer aggregations that analysts can query with confidence via DuckDB.

### What This System Explicitly Does Not Do

- Does not compute risk scores or make credit decisions
- Does not modify or write back to any source system
- Does not resolve `_is_resolvable = false` records — backfill is out of scope
- Does not support streaming or near-realtime ingestion
- Does not serve data via an API — Gold outputs are queried directly via DuckDB CLI
- Does not implement SCD Type 2 for account history
- Does not handle schema evolution — the CSV schema is fixed

### What Success Looks Like

Analysts can query Gold-layer aggregations via DuckDB and trust that every number
is traceable back to a quality-checked Silver record, which is traceable back to an
immutable Bronze partition, which is traceable back to a specific source CSV file and
pipeline run. Running the pipeline twice on the same input produces identical output.

---

## 2. Key Design Decisions

### Decision 1 — Architecture B: Run Log as Source of Truth

**What was decided:** The pipeline run log is the authoritative state record for all
three layers. Before executing any layer for a given date, the pipeline checks the run
log for a SUCCESS entry for that layer and date. If one exists, the layer is skipped.
If not, it is executed. The watermark in the control table is a secondary signal — it
only advances after all three layers complete successfully.

**Rationale:** This gives the cleanest partial re-run behaviour. A Silver failure does
not force Bronze to re-run. Each layer is independently resumable. The run log is
already required by the brief as an audit artifact — making it load-bearing adds no
new infrastructure.

**Alternatives rejected:**
- Architecture A (filesystem as source of truth): simpler but fragile across three
  layers — filesystem inspection cannot distinguish a complete write from a partial one
  without additional logic that duplicates what the run log already provides.
- Architecture C (dbt as source of truth): dbt incremental model behaviour against
  Parquet files at dbt-core 1.7.x is the least tested combination in the fixed stack.
  Risk would be validated during build rather than before it.

**Challenge:** The run log becomes load-bearing infrastructure. If it is corrupted or
inconsistent, the pipeline makes wrong skip decisions.
**Response:** Accepted for a training demo system. Gap 1 (run log vs reality divergence)
is acknowledged and accepted — see Section 5.

---

### Decision 2 — Bronze Idempotency: Partition Exists + Row Count Check

**What was decided:** Before loading a Bronze partition, the pipeline checks:
1. Does the partition directory exist?
2. If yes — does the row count in the existing Parquet file match the source CSV row count?

If both conditions are true → skip. If the partition exists but row counts do not match
→ the previous run crashed mid-write. Rewrite the partition from scratch.

**Rationale:** Row count mismatch is the partial write detector. Simpler than hashing,
more reliable than existence check alone. No atomic temp-rename required.

**Alternatives rejected:**
- Existence check only: cannot detect partial writes from crashed runs.
- Hash check: more robust but requires storing and managing hash state — unnecessary
  overhead for this exercise.
- Delete and rewrite always: violates the brief's constraint that Bronze partitions
  are never overwritten after initial write.

**Challenge:** A source CSV could be legitimately amended with a different row count
after Bronze was written. The pipeline would rewrite Bronze on the next run.
**Response:** The brief states source files are read-only and never modified. This
scenario cannot occur within the system's defined constraints.

---

### Decision 3 — dbt Materialisation: Table, Not Incremental

**What was decided:** All Silver and Gold dbt models use `table` materialisation.
Each model run produces a complete, correct output for the partition or file being
written. The run log controls whether the model runs — not dbt's incremental state.

**Rationale:** dbt-duckdb incremental models against Parquet files do not provide
database-style merge behaviour. They effectively perform a filtered read followed by a
full file write. Since the write is a full rewrite regardless, using `incremental`
materialisation adds complexity without benefit. `table` materialisation is simpler,
more predictable, and avoids edge cases at dbt-core 1.7.x.

**Alternatives rejected:**
- dbt incremental models: misleading abstraction against Parquet. The "incremental"
  logic lives in the SQL filter but the write is still a full file operation. Relying
  on dbt incremental state for idempotency would produce incorrect behaviour on partial
  re-runs without the run log checks.

**Challenge:** Full table rewrites on every run are less efficient than incremental
updates for large datasets.
**Response:** The brief fixes the dataset at 7 days of source data. Performance is
not a constraint for this exercise.

---

### Decision 4 — Silver Partial Write Recovery

**What was decided:** If the run log has no SUCCESS entry for `silver_transactions`
for a given date, the pipeline deletes `silver/transactions/date=YYYY-MM-DD/` before
rewriting it. The quarantine partition for the same date is also deleted and rewritten
at the same time.

**Rationale:** Without this, a partial Silver write followed by a re-run would cause
valid records from the partial write to be quarantined as `DUPLICATE_TRANSACTION_ID`
on the re-run. This is silent data loss — valid records end up in quarantine with no
obvious indication they should have passed.

Quarantine must be deleted alongside Silver transactions because the verification
invariant `Silver rows + quarantine rows = Bronze rows` must hold. If quarantine is
not cleared, duplicate quarantine records would break this invariant.

**Alternatives rejected:**
- Trust dbt to handle deduplication: dbt would correctly reject the already-written
  records as duplicates, but they would land in quarantine as `DUPLICATE_TRANSACTION_ID`
  — which is incorrect. They are not duplicates; they are valid records from a crashed run.

**Challenge:** Deleting a partition means data written in a previous partial run is
discarded and must be recomputed from Bronze.
**Response:** This is the correct behaviour. Bronze is immutable and always available
as the recompute source. The alternative — keeping partial Silver data — produces
incorrect quarantine records that cannot be distinguished from genuine duplicates.

---

### Decision 5 — Gold: Full Recompute on Every Run

**What was decided:** Gold daily summary and Gold weekly account summary are fully
recomputed from Silver on every pipeline run. Gold output files are overwritten
completely on each run.

**Rationale:** Gold is a single non-partitioned file containing aggregations for all
dates. Append-and-deduplicate logic against a non-partitioned file is complex and
error-prone. Full recompute from Silver is simple, always correct, and consistent
with `table` materialisation. Given the small dataset size, performance is not a concern.

**Alternatives rejected:**
- Append and deduplicate: requires Gold to track which dates have already been
  aggregated and manage deduplication across the full file on every run. Higher
  complexity for no benefit at this dataset size.

---

### Decision 6 — Pipeline Ordering Guarantee

**What was decided:** For every date processed, the execution order is fixed:
1. Transaction codes loaded to Silver (historical pipeline initialisation only)
2. Bronze accounts loaded
3. Bronze transactions loaded
4. Silver accounts promoted (upsert)
5. Silver transactions promoted (references Silver accounts)
6. Gold computed from Silver

This ordering is enforced by `pipeline.py` — not by dbt dependency resolution alone.

**Rationale:** Silver transactions references Silver accounts at promotion time for
`_is_resolvable` evaluation. If Silver accounts is not up to date before Silver
transactions runs, valid account references may be incorrectly flagged as unresolvable.
Transaction codes must exist in Silver before any transaction can be validated against
them.

---

### Decision 7 — Missing Source Files

**What was decided:** If a source file does not exist for the date being processed,
the pipeline skips that date, logs a SKIPPED entry in the run log, and holds the
watermark at its current value. The pipeline exits cleanly.

For the historical pipeline, missing files within a date range are skipped individually.
Processing continues for dates that do have files. A summary of skipped dates is
produced at the end of the run.

For accounts delta files specifically: an absent accounts delta file for a date is
not an error. By design, unchanged accounts are not included in delta files.

**Rationale:** Consistent behaviour across both pipelines. Watermark integrity is
preserved — the watermark only advances when a date is fully processed.

---

### Decision 8 — Historical Pipeline and Watermark

**What was decided:** The historical pipeline never reads or writes the watermark
during processing. It uses only the run log for idempotency. The watermark is
initialised once at the end of a successful historical run — it is not used to
make any processing decisions during that run.

**Rationale:** The watermark is a signal for the incremental pipeline — it marks
the last successfully processed date. The historical pipeline processes a fixed
date range regardless of watermark state. Mixing these concerns would make re-runs
of the historical pipeline unpredictable.

---

### Decision 9 — `_pipeline_run_id` Format

**What was decided:** Format is `YYYYMMDD_<first-8-chars-of-uuid>`.
Example: `20250403_a3f8c2d1`.

**Rationale:** Human readable enough to scan in a log, unique enough to never
collide across runs on the same date.

---

### Decision 10 — Quality Rule Edge Cases

**What was decided:**
- `merchant_name` null on PURCHASE transactions: acceptable. No rejection rule. Not
  in the exhaustive rejection code list defined in the brief.
- `billing_cycle_start` / `billing_cycle_end` out of range (outside 1–28): acceptable.
  No rejection rule. Noted as a known production gap — the brief's rejection code list
  is exhaustive and adding a new code is out of scope.
- Negative amount in source: quarantine as `INVALID_AMOUNT`. The brief states source
  amounts are always positive — a negative value is a data error.

---

### Decision 11 — Gold Edge Cases

**What was decided:**
- Zero resolvable records for a date: Gold daily summary writes a zero row for that
  date with all counts = 0 and amounts = 0. A missing row would be indistinguishable
  from a date the pipeline did not process.
- `closing_balance` with no account record in Silver: write null. Excluding the account
  entirely would hide that transaction activity exists for it. Null is honest — it signals
  transaction activity exists but no balance snapshot is available.

---

### Decision 12 — Run Log Query Pattern

**What was decided:** When querying the run log for a SUCCESS entry, always take the
most recent row per model + date combination. The run log is append-only and may
accumulate multiple rows for the same model and date across re-runs.

**Rationale:** Append-only semantics are required to preserve full audit history.
Deduplication at query time is simpler than managing it at write time.

---

## 3. Key Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Run log and filesystem state diverge after manual intervention | Low | High | Accepted for training demo system — documented as Gap 1 |
| dbt `table` materialisation overwrites Gold mid-run if pipeline crashes | Low | Medium | Gold is always recomputable from Silver — no data loss, just a re-run |
| Silver partial write not detected correctly | Low | High | Explicit delete-before-rewrite logic enforced as an invariant |
| `_is_resolvable = false` records permanently excluded from Gold | Certain | Known | Backfill is out of scope — documented and accepted |
| Quarantine accumulates false duplicates from partial re-runs | Low | High | Quarantine partition deleted alongside Silver transactions partition on re-run |

---

## 4. Key Assumptions

- Source CSV files are never modified after they are written to the `source/` directory
- Transaction codes dimension does not change during the exercise
- The dataset is small enough that full Gold recompute on every run is not a
  performance concern
- Docker Compose provides a stable enough local environment that filesystem atomicity
  can be assumed for Parquet writes
- dbt-core 1.7.x with dbt-duckdb 1.7.x supports `table` materialisation against
  Parquet files reliably

---

## 5. Open Questions

All open questions from Phase 1 have been resolved. No open questions remain.

Resolved decisions are documented in Section 2. The following were explicitly
closed during Phase 1 interrogation:

| Question | Resolution |
|---|---|
| What happens when source file is missing? | Skip, hold watermark, log SKIPPED |
| Ordering guarantee between accounts and transactions? | Fixed in brief — accounts before transactions, enforced by pipeline.py |
| `_pipeline_run_id` format? | `YYYYMMDD_<first-8-chars-of-uuid>` |
| Bronze idempotency mechanism? | Partition exists + row count check |
| Gold with zero resolvable records? | Write zero row |
| `closing_balance` with no account record? | Write null |
| Historical pipeline missing files in range? | Skip and warn — continue processing |
| Historical pipeline and watermark interaction? | Historical pipeline ignores watermark during processing |
| `merchant_name` null on PURCHASE? | Acceptable — no rejection rule |
| `billing_cycle` out of range? | Acceptable — noted as production gap |
| dbt materialisation strategy? | `table` — not incremental |
| Silver partial write recovery? | Delete partition and quarantine before rewrite |
| Gold recompute strategy? | Full recompute every run |

---

## 6. Future Enhancements (Parking Lot)

These are conscious deferrals with rationale. They are not in scope for this exercise.

| Enhancement | Rationale for Deferral |
|---|---|
| Backfill pipeline for `_is_resolvable = false` records | Requires dedicated pipeline with watermark guard logic — explicitly out of scope in brief |
| SCD Type 2 for Accounts | Silver maintains latest record only — full history costs significant complexity for no benefit in this exercise |
| Gap 1 fix — run log vs filesystem cross-check | Unnecessary risk for a training demo system |
| `billing_cycle` range validation | Would require a new rejection code — brief states the list is exhaustive |
| `merchant_name` null on PURCHASE validation | Not in the brief's rejection code list — adding it would exceed scope |
| Schema evolution support | CSV schema is fixed for this exercise |
| Serving API layer | Gold outputs queried directly via DuckDB CLI |
| Streaming or near-realtime ingestion | Batch pipeline only |

---

## 7. Data Model

### Source Entities (read-only CSV)

**transactions** (daily, append-only fact)
Fields: `transaction_id`, `account_id`, `transaction_date`, `amount` (always positive),
`transaction_code`, `merchant_name` (nullable), `channel`

**accounts** (daily delta — new and changed records only)
Fields: `account_id`, `open_date`, `credit_limit`, `current_balance`,
`billing_cycle_start`, `billing_cycle_end`, `account_status`

**transaction_codes** (static reference, loaded once)
Fields: `transaction_code`, `transaction_type`, `description`,
`debit_credit_indicator`, `affects_balance`

---

### Bronze Layer (immutable raw landing)

`bronze/transactions/date=YYYY-MM-DD/data.parquet` — date-partitioned
`bronze/accounts/date=YYYY-MM-DD/data.parquet` — date-partitioned
`bronze/transaction_codes/data.parquet` — single reference file, not partitioned

All Bronze files carry audit columns: `_source_file`, `_ingested_at`, `_pipeline_run_id`

---

### Silver Layer (clean, validated, conformed)

`silver/transactions/date=YYYY-MM-DD/data.parquet` — date-partitioned
Adds: `_signed_amount` (sign applied from transaction_codes), `_is_resolvable` (account validation flag)

`silver/accounts/data.parquet` — single file, latest record per account_id
Upserted on each run. No history retained.

`silver/transaction_codes/data.parquet` — single reference file
Loaded once during historical initialisation.

`silver/quarantine/date=YYYY-MM-DD/rejected.parquet` — date-partitioned
Contains rejected records with `_rejection_reason` from the exhaustive code list.

---

### Gold Layer (analyst-facing aggregations)

`gold/daily_summary/data.parquet` — single file, one row per transaction_date
`gold/weekly_account_summary/data.parquet` — single file, one row per account per calendar week

Both files fully recomputed from Silver on every run. Only `_is_resolvable = true`
records from Silver transactions feed Gold.

---

### Pipeline Control

`pipeline/control.parquet` — watermark tracking for incremental pipeline
`pipeline/run_log.parquet` — append-only execution record, one row per model per run

---

## 8. Stack

| Concern | Choice |
|---|---|
| Containerisation | Docker Compose — single-command startup |
| Transformation | dbt-core 1.7.x with dbt-duckdb 1.7.x adapter |
| Query engine | DuckDB — embedded, no server process |
| Storage format | Parquet on local filesystem |
| Pipeline runner | pipeline.py — Python 3.11 |
| Bronze ingestion | Python + DuckDB directly — dbt not used for raw loading |
| Silver and Gold models | dbt models exclusively — `table` materialisation |
| dbt materialisation | `table` — not `incremental` |
| Metadata | Parquet files — no metadata database |
