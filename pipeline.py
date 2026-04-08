"""
pipeline.py — Credit Card Transactions Lake
Entry point for historical and incremental pipeline runs.
"""

import argparse
import logging
import os
import re
import uuid
from datetime import datetime

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
    """Read control.parquet and return its contents as a dict."""
    raise NotImplementedError("TODO: S2 — load_control_table")


def write_control_table(date: str, run_id: str) -> None:
    """Write (overwrite) control.parquet with the given date and run_id."""
    raise NotImplementedError("TODO: S2 — write_control_table")


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

def load_bronze_transactions(date: str, run_id: str) -> None:
    """Load transactions CSV for the given date into Bronze."""
    raise NotImplementedError("TODO: S3 — load_bronze_transactions")


def load_bronze_accounts(date: str, run_id: str) -> None:
    """Load accounts CSV for the given date into Bronze."""
    raise NotImplementedError("TODO: S3 — load_bronze_accounts")


def load_bronze_transaction_codes(run_id: str) -> None:
    """Load transaction_codes CSV into Bronze."""
    raise NotImplementedError("TODO: S3 — load_bronze_transaction_codes")


# ---------------------------------------------------------------------------
# dbt runner
# ---------------------------------------------------------------------------

def run_dbt_model(model_name: str, run_id: str, vars: dict) -> bool:
    """Run a single dbt model. Returns True on success, False on failure."""
    raise NotImplementedError("TODO: S4/S5/S6 — run_dbt_model")


# ---------------------------------------------------------------------------
# Pipeline modes
# ---------------------------------------------------------------------------

def run_historical(start_date: str, end_date: str) -> None:
    """Run the historical pipeline over the given date range."""
    raise NotImplementedError("TODO: S7 — run_historical")


def run_incremental() -> None:
    """Run the incremental pipeline for the next unprocessed date."""
    raise NotImplementedError("TODO: S7 — run_incremental")


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
