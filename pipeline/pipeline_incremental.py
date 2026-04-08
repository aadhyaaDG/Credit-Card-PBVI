"""
Incremental pipeline — full three-layer run for the next single date.
Reads watermark, derives next_date = watermark + 1 day.
Errors and halts if source files for next_date do not exist (Gap 2).
silver_transaction_codes is NOT run — historical only (I-03).
Watermark advances only after Bronze, Silver, and Gold all succeed (I-08).
Run log entry written for every model (I-07).
SKIPPED entries written for models not reached after a failure (I-07).
"""
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

from pipeline.lib.bronze_loader import load_bronze_partition
from pipeline.lib.run_id import generate_run_id
from pipeline.lib.run_log import write_run_log_entry
from pipeline.lib.watermark import advance_watermark, read_watermark

SOURCE_DIR = "source"
DBT_DIR = "/app/dbt"
DBT_PROFILES = "/app/dbt"


def _load_bronze(entity, source_path, date_str, dedup_key, model_name, run_id):
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = load_bronze_partition(
            entity=entity, source_path=source_path,
            date=date_str, dedup_key=dedup_key, run_id=run_id,
        )
        write_run_log_entry(dict(
            run_id=run_id, pipeline_type="INCREMENTAL",
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
            run_id=run_id, pipeline_type="INCREMENTAL",
            model_name=model_name, layer="BRONZE",
            started_at=started,
            completed_at=datetime.now(timezone.utc).isoformat(),
            status="FAILED",
            records_processed=0, records_written=0,
            records_rejected=None, error_message=str(exc)[:500],
        ))
        print(f"  {model_name}: FAILED — {exc}")
        raise


def _run_dbt(select, vars_dict, model_name, layer, run_id, is_test=False):
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
        run_id=run_id, pipeline_type="INCREMENTAL",
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


def _write_skipped(models, run_id):
    now = datetime.now(timezone.utc).isoformat()
    for model_name, layer in models:
        write_run_log_entry(dict(
            run_id=run_id, pipeline_type="INCREMENTAL",
            model_name=model_name, layer=layer,
            started_at=now, completed_at=now,
            status="SKIPPED",
            records_processed=None, records_written=None,
            records_rejected=None, error_message=None,
        ))
        print(f"  {model_name}: SKIPPED")


def run_incremental():
    watermark = read_watermark()
    if watermark is None:
        print("ERROR: No watermark found. Run the historical pipeline first.")
        sys.exit(1)

    next_date = watermark + timedelta(days=1)
    ds = next_date.strftime("%Y-%m-%d")

    acct_path = os.path.join(SOURCE_DIR, f"accounts_{ds}.csv")
    txn_path  = os.path.join(SOURCE_DIR, f"transactions_{ds}.csv")

    for path in [acct_path, txn_path]:
        if not os.path.exists(path):
            print(f"ERROR: Source files not found for {ds}. Expected: {path}")
            sys.exit(1)

    run_id = generate_run_id()
    print(f"Incremental run: {run_id}  processing {ds}")

    # Pre-create Silver partition directories for this date.
    # dbt-duckdb external materialization does not auto-create parent dirs.
    os.makedirs(f"data/silver/transactions/date={ds}", exist_ok=True)
    os.makedirs(f"data/silver/quarantine/date={ds}", exist_ok=True)

    # ── BRONZE STAGE ────────────────────────────────────────────────────────
    print("\n[Bronze]")
    try:
        _load_bronze("accounts", acct_path, ds,
                     "account_id", f"bronze_accounts_{ds}", run_id)
        _load_bronze("transactions", txn_path, ds,
                     "transaction_id", f"bronze_transactions_{ds}", run_id)
    except Exception:
        _write_skipped([
            (f"silver_accounts_{ds}", "SILVER"),
            (f"silver_transactions_{ds}", "SILVER"),
            (f"silver_quarantine_{ds}", "SILVER"),
            (f"test_conservation_law_{ds}", "SILVER"),
            ("gold_daily_summary", "GOLD"),
            ("gold_weekly_account_summary", "GOLD"),
        ], run_id)
        sys.exit(1)

    # ── SILVER STAGE ────────────────────────────────────────────────────────
    # silver_transaction_codes is NOT run on incremental (I-03)
    print("\n[Silver]")
    vars_date = {"run_id": run_id, "processing_date": ds}
    try:
        _run_dbt("silver_accounts", vars_date,
                 f"silver_accounts_{ds}", "SILVER", run_id)
        _run_dbt("silver_transactions", vars_date,
                 f"silver_transactions_{ds}", "SILVER", run_id)
        _run_dbt("silver_quarantine", vars_date,
                 f"silver_quarantine_{ds}", "SILVER", run_id)
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
    vars_base = {"run_id": run_id}
    try:
        _run_dbt("gold_daily_summary", vars_base,
                 "gold_daily_summary", "GOLD", run_id)
        _run_dbt("gold_weekly_account_summary", vars_base,
                 "gold_weekly_account_summary", "GOLD", run_id)
    except RuntimeError:
        print("Watermark NOT advanced — Gold stage failed.")
        sys.exit(1)

    # ── WATERMARK — absolute last operation ─────────────────────────────────
    advance_watermark(next_date, run_id)
    print(f"\nWatermark advanced to {next_date}")
    print(f"Incremental run complete: {run_id}")


if __name__ == "__main__":
    run_incremental()
