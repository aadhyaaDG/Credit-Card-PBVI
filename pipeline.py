"""
pipeline.py — Credit Card Transactions Lake
Entry point for historical and incremental pipeline runs.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import uuid
from datetime import date as date_cls, datetime, timedelta

import duckdb

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
SOURCE_DIR = os.environ.get("SOURCE_DIR", "/app/source")
DBT_PROFILES_DIR = os.environ.get("DBT_PROFILES_DIR", "/app/dbt_project")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Run ID
# ---------------------------------------------------------------------------

def generate_run_id() -> str:
    """Format: YYYYMMDD_<first-8-chars-of-uuid4>"""
    date_part = datetime.today().strftime("%Y%m%d")
    uuid_part = str(uuid.uuid4()).replace("-", "").lower()[:8]
    return f"{date_part}_{uuid_part}"


# ---------------------------------------------------------------------------
# Internal path helpers
# ---------------------------------------------------------------------------

def _run_log_path() -> str:
    return os.path.join(DATA_DIR, "pipeline", "run_log.parquet")


def _control_path() -> str:
    return os.path.join(DATA_DIR, "pipeline", "control.parquet")


def _row_to_dict(description, row) -> dict:
    """Convert a DuckDB result row to a dict, serialising date/datetime to ISO strings."""
    result = {}
    for (col, *_), val in zip(description, row):
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        result[col] = val
    return result


# ---------------------------------------------------------------------------
# Control table
# ---------------------------------------------------------------------------

def load_control_table() -> dict:
    """Return the single control table row as a dict, or None if file absent.

    Raises ValueError if the file contains more than one row.
    """
    path = _control_path()
    if not os.path.exists(path):
        return None

    con = duckdb.connect()
    try:
        result = con.execute(f"SELECT * FROM read_parquet('{path}')")
        description = result.description
        rows = result.fetchall()
    finally:
        con.close()

    if len(rows) > 1:
        raise ValueError(f"Control table has {len(rows)} rows — expected exactly 1")

    return _row_to_dict(description, rows[0]) if rows else None


def write_control_table(date: str, run_id: str) -> None:
    """Overwrite control.parquet with a single row for the given date and run_id.

    Raises ValueError if date is not a valid YYYY-MM-DD string.
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise ValueError(f"Invalid date format '{date}' — expected YYYY-MM-DD")

    path = _control_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    con = duckdb.connect()
    try:
        con.execute("""
            CREATE TEMP TABLE _ctrl AS
            SELECT
                ?::DATE      AS last_processed_date,
                NOW()        AS updated_at,
                ?            AS updated_by_run_id
        """, [date, run_id])
        con.execute(f"COPY (SELECT * FROM _ctrl) TO '{path}' (FORMAT PARQUET)")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Run log
# ---------------------------------------------------------------------------

_RUN_LOG_REQUIRED = frozenset([
    "run_id", "pipeline_type", "model_name", "layer",
    "started_at", "completed_at", "status",
])


def append_run_log(row: dict) -> None:
    """Append a single row to run_log.parquet (append-only).

    Raises ValueError if any required field is null.
    If the existing file is corrupt (Rule 5), logs a WARNING and starts fresh.
    """
    for field in _RUN_LOG_REQUIRED:
        if row.get(field) is None:
            raise ValueError(f"Required run log field '{field}' is null")

    path = _run_log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    con = duckdb.connect()
    try:
        con.execute("""
            CREATE TEMP TABLE _new_row AS
            SELECT
                ?        AS run_id,
                ?        AS pipeline_type,
                ?        AS model_name,
                ?        AS layer,
                ?::TIMESTAMP AS started_at,
                ?::TIMESTAMP AS completed_at,
                ?        AS status,
                ?::INTEGER   AS records_processed,
                ?::INTEGER   AS records_written,
                ?::INTEGER   AS records_rejected,
                ?        AS error_message
        """, [
            row["run_id"], row["pipeline_type"], row["model_name"], row["layer"],
            str(row["started_at"]), str(row["completed_at"]), row["status"],
            row.get("records_processed"), row.get("records_written"),
            row.get("records_rejected"), row.get("error_message"),
        ])

        if os.path.exists(path):
            try:
                con.execute(f"""
                    COPY (
                        SELECT * FROM read_parquet('{path}')
                        UNION ALL
                        SELECT * FROM _new_row
                    ) TO '{path}' (FORMAT PARQUET)
                """)
            except Exception as exc:
                logger.warning("run_log.parquet unreadable — starting fresh: %s", exc)
                os.remove(path)
                con.execute(f"COPY (SELECT * FROM _new_row) TO '{path}' (FORMAT PARQUET)")
        else:
            con.execute(f"COPY (SELECT * FROM _new_row) TO '{path}' (FORMAT PARQUET)")
    finally:
        con.close()


def read_run_log() -> list:
    """Return all rows from run_log.parquet sorted by started_at ascending.

    Returns an empty list if the file does not exist.
    """
    path = _run_log_path()
    if not os.path.exists(path):
        return []

    con = duckdb.connect()
    try:
        result = con.execute(f"""
            SELECT * FROM read_parquet('{path}')
            ORDER BY started_at ASC
        """)
        description = result.description
        rows = result.fetchall()
    except Exception as exc:
        logger.warning("run_log.parquet unreadable — returning empty list: %s", exc)
        return []
    finally:
        con.close()

    return [_row_to_dict(description, r) for r in rows]


# ---------------------------------------------------------------------------
# Bronze loaders
# ---------------------------------------------------------------------------

def _bronze_load_csv(
    source_path: str,
    output_path: str,
    model_name: str,
    run_id: str,
    source_filename: str,
    check_missing: bool = True,
) -> None:
    """Shared implementation for all three Bronze CSV loaders.

    Enforces: INV-04 (never writes to source), INV-05 (source fields as-is),
    INV-10 (idempotency via row count check), INV-11 (audit columns non-null),
    Rule 4 (try/finally run log), Rule 5 (corrupt parquet guard).
    """
    started_at = datetime.utcnow().isoformat()
    status = "FAILED"
    error_message = None
    records_processed = None
    records_written = None

    try:
        # Missing source file — SKIPPED (INV-18 for date-partitioned loaders)
        if check_missing and not os.path.exists(source_path):
            logger.info("Source file absent — skipping: %s", source_path)
            status = "SKIPPED"
            return

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        con = duckdb.connect()

        # Source row count (INV-05 — read only, never modify)
        src_count = con.execute(
            f"SELECT COUNT(*) FROM read_csv_auto('{source_path}')"
        ).fetchone()[0]
        records_processed = src_count

        # Idempotency check (INV-10)
        if os.path.exists(output_path):
            try:
                existing_count = con.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{output_path}')"
                ).fetchone()[0]
            except Exception as exc:
                # Rule 5 — corrupt parquet: treat as mismatch, delete and rewrite
                logger.warning(
                    "Existing parquet unreadable at %s — will rewrite: %s",
                    output_path, exc,
                )
                os.remove(output_path)
                existing_count = -1

            if existing_count == src_count:
                logger.info(
                    "Bronze idempotent skip: %s (%d rows match)", output_path, existing_count
                )
                status = "SKIPPED"
                records_written = 0
                return

            # Row count mismatch — delete and rewrite
            logger.warning(
                "Row count mismatch at %s (expected %d, found %d) — rewriting",
                output_path, src_count, existing_count,
            )
            os.remove(output_path)

        # Write: source fields as-is + audit columns (INV-05, INV-11)
        con.execute("""
            CREATE OR REPLACE TEMP TABLE _bronze AS
            SELECT
                *,
                ?            AS _source_file,
                NOW()::TIMESTAMP AS _ingested_at,
                ?            AS _pipeline_run_id
            FROM read_csv_auto(?)
        """, [source_filename, run_id, source_path])
        con.execute(f"COPY (SELECT * FROM _bronze) TO '{output_path}' (FORMAT PARQUET)")
        con.close()

        records_written = src_count
        status = "SUCCESS"
        logger.info("Bronze written: %s (%d rows)", output_path, records_written)

    except Exception as exc:
        error_message = str(exc)
        logger.error("Bronze loader failed (%s): %s", model_name, exc)
        raise
    finally:
        # Rule 4 — write run log unconditionally, even on exception
        append_run_log({
            "run_id": run_id,
            "pipeline_type": "HISTORICAL",
            "model_name": model_name,
            "layer": "BRONZE",
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat(),
            "status": status,
            "records_processed": records_processed,
            "records_written": records_written,
            "records_rejected": None,
            "error_message": error_message,
        })


def load_bronze_transaction_codes(run_id: str) -> None:
    """Load transaction_codes.csv into data/bronze/transaction_codes/data.parquet."""
    _bronze_load_csv(
        source_path=os.path.join(SOURCE_DIR, "transaction_codes.csv"),
        output_path=os.path.join(DATA_DIR, "bronze", "transaction_codes", "data.parquet"),
        model_name="bronze_transaction_codes",
        run_id=run_id,
        source_filename="transaction_codes.csv",
        check_missing=False,
    )


def load_bronze_accounts(date: str, run_id: str) -> None:
    """Load accounts_{date}.csv into data/bronze/accounts/date={date}/data.parquet."""
    _bronze_load_csv(
        source_path=os.path.join(SOURCE_DIR, f"accounts_{date}.csv"),
        output_path=os.path.join(DATA_DIR, "bronze", "accounts", f"date={date}", "data.parquet"),
        model_name="bronze_accounts",
        run_id=run_id,
        source_filename=f"accounts_{date}.csv",
        check_missing=True,
    )


def load_bronze_transactions(date: str, run_id: str) -> None:
    """Load transactions_{date}.csv into data/bronze/transactions/date={date}/data.parquet."""
    _bronze_load_csv(
        source_path=os.path.join(SOURCE_DIR, f"transactions_{date}.csv"),
        output_path=os.path.join(DATA_DIR, "bronze", "transactions", f"date={date}", "data.parquet"),
        model_name="bronze_transactions",
        run_id=run_id,
        source_filename=f"transactions_{date}.csv",
        check_missing=True,
    )


# ---------------------------------------------------------------------------
# dbt runner
# ---------------------------------------------------------------------------

def check_silver_accounts_ready(processing_date: str) -> bool:
    """Return True if silver_accounts has a SUCCESS run completed after the most
    recent bronze_accounts SUCCESS run (INV-20).

    Comparison is by completed_at timestamp, not by calendar date — the pipeline
    may process historical dates (e.g. 2024-01-01) on a different wall-clock date.
    Returns False if either SUCCESS entry is missing or silver_accounts predates
    bronze_accounts.
    """
    log = read_run_log()
    if not log:
        return False

    # Most recent silver_accounts SUCCESS
    silver_acc_successes = [
        r for r in log
        if r["model_name"] == "silver_accounts" and r["status"] == "SUCCESS"
    ]
    if not silver_acc_successes:
        return False
    latest_silver = max(silver_acc_successes, key=lambda r: r["completed_at"])

    # Most recent bronze_accounts SUCCESS or SKIPPED (idempotent) entry
    bronze_acc_successes = [
        r for r in log
        if r["model_name"] == "bronze_accounts" and r["status"] in ("SUCCESS", "SKIPPED")
    ]
    if not bronze_acc_successes:
        return False
    latest_bronze = max(bronze_acc_successes, key=lambda r: r["completed_at"])

    return latest_silver["completed_at"] >= latest_bronze["completed_at"]


def _sanitize_error_message(msg: str) -> str:
    """Strip filesystem paths from error text before writing to run log."""
    msg = re.sub(r'/\S+', '<path>', msg)
    msg = re.sub(r'[A-Za-z]:\\\S+', '<path>', msg)
    return msg[:500].strip()


def run_dbt_model(model_name: str, run_id: str, vars: dict) -> bool:
    """Run a single dbt model via the dbt CLI.

    Returns True on success, False on failure.
    Writes a run log entry unconditionally (Rule 4).
    Enforces INV-20 guard when model_name == 'silver_transactions'.
    """
    started_at = datetime.utcnow().isoformat()
    status = "FAILED"
    error_message = None
    layer = "GOLD" if model_name.startswith("gold_") else "SILVER"

    try:
        # INV-20 — silver_accounts must be current before silver_transactions runs
        if model_name == "silver_transactions":
            processing_date = vars.get("processing_date")
            if not check_silver_accounts_ready(processing_date):
                error_message = (
                    f"silver_accounts not current for {processing_date} — run aborted"
                )
                logger.error(error_message)
                raise RuntimeError(error_message)

        # Ensure output directories exist before dbt runs (DuckDB COPY TO requires parent to exist)
        processing_date = vars.get("processing_date")
        if model_name == "silver_transaction_codes":
            os.makedirs(os.path.join(DATA_DIR, "silver", "transaction_codes"), exist_ok=True)
        elif processing_date and model_name in ("silver_transactions", "silver_accounts"):
            os.makedirs(
                os.path.join(DATA_DIR, "silver", "quarantine", f"date={processing_date}"),
                exist_ok=True,
            )
            if model_name == "silver_transactions":
                os.makedirs(
                    os.path.join(DATA_DIR, "silver", "transactions", f"date={processing_date}"),
                    exist_ok=True,
                )

        # Build dbt vars string: merge caller vars with run_id.
        # json.dumps produces valid JSON which dbt --vars accepts as YAML.
        all_vars = {**vars, "run_id": run_id}
        vars_str = json.dumps(all_vars)

        cmd = [
            "dbt", "run",
            "--select", model_name,
            "--vars", vars_str,
            "--profiles-dir", DBT_PROFILES_DIR,
            "--project-dir", DBT_PROFILES_DIR,
        ]
        logger.info("dbt run: model=%s vars=%s", model_name, vars_str)

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raw = (result.stderr or result.stdout or "dbt exited non-zero").strip()
            error_message = _sanitize_error_message(raw)
            logger.error("dbt model failed (%s): %s", model_name, error_message)
            return False

        status = "SUCCESS"
        logger.info("dbt model succeeded: %s", model_name)
        return True

    except Exception as exc:
        if error_message is None:
            error_message = _sanitize_error_message(str(exc))
        logger.error("run_dbt_model error (%s): %s", model_name, exc)
        raise
    finally:
        # Rule 4 — write run log unconditionally, even on exception
        append_run_log({
            "run_id": run_id,
            "pipeline_type": vars.get("pipeline_type", "INCREMENTAL"),
            "model_name": model_name,
            "layer": layer,
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat(),
            "status": status,
            "records_processed": None,
            "records_written": None,
            "records_rejected": None,
            "error_message": error_message,
        })


# ---------------------------------------------------------------------------
# Pipeline modes
# ---------------------------------------------------------------------------

def run_historical(start_date: str, end_date: str) -> None:
    """Run the historical pipeline over [start_date, end_date] inclusive.

    Execution order (enforced):
      Before first date: bronze + silver transaction_codes (idempotent skip if
      run log already has SUCCESS for silver_transaction_codes).

      Per date:
        1. load_bronze_accounts      (internal idempotency — row count check)
        2. load_bronze_transactions  (internal idempotency — row count check)
        3. run_dbt_model silver_accounts
        4. run_dbt_model silver_transactions  (INV-20 guard enforced inside)
        5. run_dbt_model silver_quarantine

      Dates where Bronze transactions partition is absent are skipped (INV-18).
      Dates where Silver transactions partition already exists are skipped (INV-10).
      If any Silver layer fails for a date: log, continue to next date, set failure flag.

      After all dates (only if no Silver failures):
        6. run_dbt_model gold_daily_summary
        7. run_dbt_model gold_weekly_account_summary

    Watermark advances to end_date only after Gold completes successfully and no
    Silver failures were recorded (INV-02, INV-03).
    Missing source file skips are not failures (INV-18).
    """
    run_id = generate_run_id()
    logger.info("Historical run %s: %s → %s", run_id, start_date, end_date)

    pipeline_vars = {"pipeline_type": "HISTORICAL"}
    any_silver_failure = False

    # ------------------------------------------------------------------
    # Transaction codes — once before any date (idempotent)
    # ------------------------------------------------------------------
    tc_already_ok = any(
        r["model_name"] == "silver_transaction_codes" and r["status"] == "SUCCESS"
        for r in read_run_log()
    )
    if tc_already_ok:
        logger.info("silver_transaction_codes already succeeded — skipping")
    else:
        load_bronze_transaction_codes(run_id)
        if not run_dbt_model("silver_transaction_codes", run_id, pipeline_vars):
            logger.error("silver_transaction_codes failed — aborting historical run")
            return

    # ------------------------------------------------------------------
    # Per-date loop
    # ------------------------------------------------------------------
    current = date_cls.fromisoformat(start_date)
    end = date_cls.fromisoformat(end_date)

    while current <= end:
        processing_date = current.isoformat()
        current += timedelta(days=1)

        logger.info("Processing date: %s", processing_date)
        date_vars = {**pipeline_vars, "processing_date": processing_date}

        # Bronze (internal idempotency via row count check)
        load_bronze_accounts(processing_date, run_id)
        load_bronze_transactions(processing_date, run_id)

        # If Bronze transactions partition is absent, source file was missing — skip (INV-18)
        bronze_txn_path = os.path.join(
            DATA_DIR, "bronze", "transactions", f"date={processing_date}", "data.parquet"
        )
        if not os.path.exists(bronze_txn_path):
            logger.info(
                "Bronze transactions absent for %s — skipping date (INV-18)", processing_date
            )
            continue

        # Silver transactions partition already exists — date fully processed, skip (INV-10)
        silver_txn_path = os.path.join(
            DATA_DIR, "silver", "transactions", f"date={processing_date}", "data.parquet"
        )
        if os.path.exists(silver_txn_path):
            logger.info(
                "Silver transactions partition exists for %s — skipping (idempotent)",
                processing_date,
            )
            continue

        # Silver accounts (must precede silver_transactions — INV-20)
        if not run_dbt_model("silver_accounts", run_id, date_vars):
            logger.error("silver_accounts failed for %s", processing_date)
            any_silver_failure = True
            continue

        # Silver transactions
        if not run_dbt_model("silver_transactions", run_id, date_vars):
            logger.error("silver_transactions failed for %s", processing_date)
            any_silver_failure = True
            continue

        # Silver quarantine — non-critical; failure logged but does not block watermark
        run_dbt_model("silver_quarantine", run_id, date_vars)

    # ------------------------------------------------------------------
    # Gold — only after all dates complete without Silver failures
    # ------------------------------------------------------------------
    if any_silver_failure:
        logger.warning(
            "Silver failures detected — skipping Gold and watermark advance (INV-02)"
        )
        return

    gold_ok = run_dbt_model("gold_daily_summary", run_id, pipeline_vars) and \
              run_dbt_model("gold_weekly_account_summary", run_id, pipeline_vars)

    if gold_ok:
        write_control_table(end_date, run_id)
        logger.info("Watermark advanced to %s", end_date)
    else:
        logger.error("Gold layer failed — watermark not advanced (INV-02)")


def run_incremental() -> None:
    """Run the incremental pipeline for the next unprocessed date.

    Reads the watermark from the control table and processes watermark + 1 day.

    Behaviour:
      - If control table absent (historical never run): raises RuntimeError (TC-5).
      - If neither source CSV exists for next_date: exits cleanly, no watermark
        change (INV-18).
      - If Silver transactions partition already exists for next_date: skips all
        layers and returns (idempotency — INV-10).
      - Execution order:
          1. load_bronze_accounts
          2. load_bronze_transactions
          3. silver_accounts   (INV-20 guard enforced inside run_dbt_model)
          4. silver_transactions
          5. silver_quarantine (non-critical)
          6. gold_daily_summary
          7. gold_weekly_account_summary
      - Any Silver or Gold failure: logs error, exits with code 1 without advancing
        watermark (INV-02).
      - On full success: write_control_table(next_date) — watermark advances by
        exactly one day (INV-01).
    """
    run_id = generate_run_id()
    logger.info("Incremental run %s", run_id)

    # Require historical to have run first (TC-5)
    ctrl = load_control_table()
    if ctrl is None:
        raise RuntimeError(
            "Incremental pipeline requires historical pipeline to have run first."
        )

    last_date = date_cls.fromisoformat(str(ctrl["last_processed_date"])[:10])
    next_date = (last_date + timedelta(days=1)).isoformat()
    logger.info("Next date to process: %s", next_date)

    pipeline_vars = {"pipeline_type": "INCREMENTAL"}
    date_vars = {**pipeline_vars, "processing_date": next_date}

    # If neither source file exists, nothing to do — exit cleanly (INV-18)
    txn_source = os.path.join(SOURCE_DIR, f"transactions_{next_date}.csv")
    acc_source = os.path.join(SOURCE_DIR, f"accounts_{next_date}.csv")
    if not os.path.exists(txn_source) and not os.path.exists(acc_source):
        logger.info("No source files for %s — nothing to process (INV-18)", next_date)
        return

    # Silver transactions partition already exists — date already processed (INV-10)
    silver_txn_path = os.path.join(
        DATA_DIR, "silver", "transactions", f"date={next_date}", "data.parquet"
    )
    if os.path.exists(silver_txn_path):
        logger.info(
            "Silver transactions partition already exists for %s — skipping (INV-10)",
            next_date,
        )
        return

    # Bronze (internal idempotency via row count check)
    load_bronze_accounts(next_date, run_id)
    load_bronze_transactions(next_date, run_id)

    # Silver accounts (must precede silver_transactions — INV-20)
    if not run_dbt_model("silver_accounts", run_id, date_vars):
        logger.error(
            "silver_accounts failed for %s — watermark not advanced (INV-02)", next_date
        )
        sys.exit(1)

    # Silver transactions
    if not run_dbt_model("silver_transactions", run_id, date_vars):
        logger.error(
            "silver_transactions failed for %s — watermark not advanced (INV-02)", next_date
        )
        sys.exit(1)

    # Silver quarantine (non-critical — failure does not block watermark)
    run_dbt_model("silver_quarantine", run_id, date_vars)

    # Gold
    gold_ok = (
        run_dbt_model("gold_daily_summary", run_id, pipeline_vars)
        and run_dbt_model("gold_weekly_account_summary", run_id, pipeline_vars)
    )
    if not gold_ok:
        logger.error(
            "Gold layer failed for %s — watermark not advanced (INV-02)", next_date
        )
        sys.exit(1)

    # Advance watermark by exactly one day (INV-01, INV-02, INV-03)
    write_control_table(next_date, run_id)
    logger.info("Watermark advanced to %s", next_date)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Credit Card Transactions Lake pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    hist = subparsers.add_parser("historical", help="Run historical pipeline")
    hist.add_argument("--start-date", required=True, metavar="YYYY-MM-DD")
    hist.add_argument("--end-date", required=True, metavar="YYYY-MM-DD")

    subparsers.add_parser("incremental", help="Run incremental pipeline")

    args = parser.parse_args()

    if args.command == "historical":
        logger.info("Starting historical run: %s → %s", args.start_date, args.end_date)
        run_historical(args.start_date, args.end_date)
    elif args.command == "incremental":
        logger.info("Starting incremental run")
        run_incremental()


if __name__ == "__main__":
    main()
