"""
Watermark management for the pipeline control table.

The watermark is the last successfully processed date — the date for which
Bronze, Silver, and Gold all completed with status=SUCCESS.

advance_watermark() is the absolute last operation in any successful pipeline
run. It must never be called before all three layers complete successfully.
I-08: watermark advances if and only if all three layers succeed.
"""
import os
import duckdb
import pandas as pd
from datetime import date, datetime, timezone

CONTROL_PATH = "data/pipeline/control.parquet"


def read_watermark() -> date | None:
    """
    Read the current watermark from the control table.
    Returns the last_processed_date as a Python date, or None if no file exists.
    """
    if not os.path.exists(CONTROL_PATH):
        return None
    con = duckdb.connect()
    row = con.execute(
        f"SELECT last_processed_date FROM read_parquet('{CONTROL_PATH}')"
    ).fetchone()
    con.close()
    if not row:
        return None
    val = row[0]
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


def advance_watermark(new_date: date, run_id: str) -> None:
    """
    Advance the watermark to new_date.

    Raises ValueError if new_date is not strictly greater than the current
    watermark — prevents going backwards or double-advancing the same date.

    This function overwrites control.parquet with a single row reflecting the
    new watermark state. Parquet has no append semantics — full overwrite is
    the correct pattern for a single-row control table.
    """
    current = read_watermark()
    if current is not None and new_date <= current:
        raise ValueError(
            f"Cannot advance watermark: new_date {new_date} is not greater "
            f"than current watermark {current}."
        )

    os.makedirs(os.path.dirname(CONTROL_PATH), exist_ok=True)

    record = pd.DataFrame([{
        "last_processed_date": new_date,
        "updated_at":          datetime.now(timezone.utc).isoformat(),
        "updated_by_run_id":   run_id,
    }])

    con = duckdb.connect()
    con.execute(f"""
        COPY (SELECT * FROM record)
        TO '{CONTROL_PATH}' (FORMAT PARQUET)
    """)
    con.close()
