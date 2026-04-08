"""
pipeline.py — Credit Card Transactions Lake
Entry point for historical and incremental pipeline runs.
"""

import argparse
import logging
import os

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
    raise NotImplementedError("TODO: S2 — generate_run_id")


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

def append_run_log(row: dict) -> None:
    """Append a single row to run_log.parquet (append-only)."""
    raise NotImplementedError("TODO: S2 — append_run_log")


def read_run_log() -> list:
    """Return all rows from run_log.parquet as a list of dicts."""
    raise NotImplementedError("TODO: S2 — read_run_log")


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
