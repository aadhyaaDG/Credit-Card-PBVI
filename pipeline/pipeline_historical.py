"""
Historical pipeline — full three-layer run (Bronze → Silver → Gold).
Processes all dates in [start_date, end_date] in ascending order.

Startup guard: errors and halts if a watermark already exists (Gap 1).
Watermark advances only after Bronze, Silver, and Gold all succeed (I-08).
Run log entry written for every model, on both success and failure (I-07).
SKIPPED entries written for models not reached after a failure (I-07).
Gold is never computed if any Silver model fails (I-09).
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

from pipeline.lib.bronze_loader import load_bronze_partition
from pipeline.lib.run_id import generate_run_id
from pipeline.lib.run_log import write_run_log_entry
from pipeline.lib.watermark import advance_watermark, read_watermark

CONTROL_PATH = "data/pipeline/control.parquet"
SOURCE_DIR = "source"
DBT_DIR = "/app/dbt"
DBT_PROFILES = "/app/dbt"


def check_no_watermark():
    wm = read_watermark()
    if wm is not None:
        print(
            f"ERROR: Historical pipeline cannot run: watermark already exists "
            f"at {wm}. Use the incremental pipeline or investigate whether "
            "this is a backfill case."
        )
        sys.exit(1)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _load_bronze(entity, source_path, date_str, dedup_key, model_name, run_id):
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = load_bronze_partition(
            entity=entity,
            source_path=source_path,
            date=date_str,
            dedup_key=dedup_key,
            run_id=run_id,
        )
        write_run_log_entry(dict(
            run_id=run_id, pipeline_type="HISTORICAL",
            model_name=model_name, layer="BRONZE",
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
            status="SUCCESS",
            records_processed=result["source_count"],
            records_written=result["records_written"],
            records_rejected=None, error_message=None,
        ))
        print(f"  {model_name}: {result['records_written']} rows")
    except Exception as exc:
        write_run_log_entry(dict(
            run_id=run_id, pipeline_type="HISTORICAL",
            model_name=model_name, layer="BRONZE",
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
            status="FAILED",
            records_processed=0, records_written=0,
            records_rejected=None, error_message=str(exc)[:500],
        ))
        print(f"  {model_name}: FAILED — {exc}")
        raise


def _run_dbt(select, vars_dict, model_name, layer, run_id,
             pipeline_type="HISTORICAL", is_test=False):
    """
    Invoke a dbt run or dbt test command. Writes a run log entry on completion.
    Returns True on success, False on failure.
    Raises RuntimeError on failure so the caller can write SKIPPED entries.
    """
    started = datetime.now(timezone.utc).isoformat()
    cmd = ["dbt", "test" if is_test else "run",
           "--project-dir", DBT_DIR,
           "--profiles-dir", DBT_PROFILES,
           "--select", select]
    if vars_dict:
        cmd += ["--vars", json.dumps(vars_dict)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    success = result.returncode == 0

    write_run_log_entry(dict(
        run_id=run_id, pipeline_type=pipeline_type,
        model_name=model_name, layer=layer,
        started_at=started,
        completed_at=datetime.now(timezone.utc).isoformat(),
        status="SUCCESS" if success else "FAILED",
        records_processed=None, records_written=None,
        records_rejected=None,
        error_message=None if success else result.stderr[:500],
    ))

    if not success:
        print(f"  {model_name}: FAILED")
        print(result.stdout[-1000:])
        raise RuntimeError(f"dbt {model_name} failed")

    print(f"  {model_name}: SUCCESS")
    return True


def _write_skipped(models, run_id, pipeline_type="HISTORICAL"):
    now = datetime.now(timezone.utc).isoformat()
    for model_name, layer in models:
        write_run_log_entry(dict(
            run_id=run_id, pipeline_type=pipeline_type,
            model_name=model_name, layer=layer,
            started_at=now, completed_at=now,
            status="SKIPPED",
            records_processed=None, records_written=None,
            records_rejected=None, error_message=None,
        ))
        print(f"  {model_name}: SKIPPED")


def run_historical(start_date: date, end_date: date):
    check_no_watermark()

    run_id = generate_run_id()
    print(f"Historical run: {run_id}  {start_date} → {end_date}")

    dates = list(daterange(start_date, end_date))

    # Pre-create Silver and Gold partition directories.
    # dbt-duckdb external materialization does not auto-create parent dirs.
    for d in dates:
        ds = d.strftime("%Y-%m-%d")
        os.makedirs(f"data/silver/transactions/date={ds}", exist_ok=True)
        os.makedirs(f"data/silver/quarantine/date={ds}", exist_ok=True)
    os.makedirs("data/silver/accounts", exist_ok=True)
    os.makedirs("data/silver/transaction_codes", exist_ok=True)
    os.makedirs("data/gold/daily_summary", exist_ok=True)
    os.makedirs("data/gold/weekly_account_summary", exist_ok=True)

    # ── BRONZE STAGE ────────────────────────────────────────────────────────
    print("\n[Bronze]")
    try:
        tx_codes_path = os.path.join(SOURCE_DIR, "transaction_codes.csv")
        _load_bronze("transaction_codes", tx_codes_path, None,
                     "transaction_code", "bronze_transaction_codes", run_id)

        for d in dates:
            ds = d.strftime("%Y-%m-%d")
            _load_bronze("accounts", os.path.join(SOURCE_DIR, f"accounts_{ds}.csv"),
                         ds, "account_id", f"bronze_accounts_{ds}", run_id)
            _load_bronze("transactions", os.path.join(SOURCE_DIR, f"transactions_{ds}.csv"),
                         ds, "transaction_id", f"bronze_transactions_{ds}", run_id)
    except Exception:
        # remaining Silver and Gold models are SKIPPED
        silver_models = (
            [("silver_transaction_codes", "SILVER")]
            + [(m, "SILVER") for d in dates for m in [
                f"silver_accounts_{d.strftime('%Y-%m-%d')}",
                f"silver_transactions_{d.strftime('%Y-%m-%d')}",
                f"silver_quarantine_{d.strftime('%Y-%m-%d')}",
                f"test_conservation_law_{d.strftime('%Y-%m-%d')}",
            ]]
            + [("gold_daily_summary", "GOLD"),
               ("gold_weekly_account_summary", "GOLD")]
        )
        _write_skipped(silver_models, run_id)
        sys.exit(1)

    # ── SILVER STAGE ────────────────────────────────────────────────────────
    print("\n[Silver]")
    try:
        vars_base = {"run_id": run_id}

        # Transaction codes — once, historical only (I-03)
        _run_dbt("silver_transaction_codes", vars_base,
                 "silver_transaction_codes", "SILVER", run_id)

        for d in dates:
            ds = d.strftime("%Y-%m-%d")
            vars_date = {"run_id": run_id, "processing_date": ds}

            _run_dbt("silver_accounts", vars_date,
                     f"silver_accounts_{ds}", "SILVER", run_id)
            _run_dbt("silver_transactions", vars_date,
                     f"silver_transactions_{ds}", "SILVER", run_id)
            _run_dbt("silver_quarantine", vars_date,
                     f"silver_quarantine_{ds}", "SILVER", run_id)

            # I-01 conservation law gate — blocks Gold if it fails
            _run_dbt("test_conservation_law", vars_date,
                     f"test_conservation_law_{ds}", "SILVER", run_id,
                     is_test=True)

    except RuntimeError:
        _write_skipped([
            ("gold_daily_summary", "GOLD"),
            ("gold_weekly_account_summary", "GOLD"),
        ], run_id)
        print("Watermark NOT advanced — Silver stage failed.")
        sys.exit(1)

    # ── GOLD STAGE ──────────────────────────────────────────────────────────
    print("\n[Gold]")
    try:
        vars_base = {"run_id": run_id}
        _run_dbt("gold_daily_summary", vars_base,
                 "gold_daily_summary", "GOLD", run_id)
        _run_dbt("gold_weekly_account_summary", vars_base,
                 "gold_weekly_account_summary", "GOLD", run_id)
    except RuntimeError:
        print("Watermark NOT advanced — Gold stage failed.")
        sys.exit(1)

    # ── WATERMARK — absolute last operation ─────────────────────────────────
    advance_watermark(end_date, run_id)
    print(f"\nWatermark advanced to {end_date}")
    print(f"Historical run complete: {run_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    args = parser.parse_args()
    run_historical(
        date.fromisoformat(args.start_date),
        date.fromisoformat(args.end_date),
    )
