import os
import duckdb
import pandas as pd
from datetime import datetime, timezone

RUN_LOG_PATH = "data/pipeline/run_log.parquet"
VALID_STATUSES = {"SUCCESS", "FAILED", "SKIPPED"}


def write_run_log_entry(entry: dict) -> None:
    """
    Append one row to the pipeline run log using read-deduplicate-write.
    Dedup key: (run_id, model_name) — existing row wins on re-run.
    error_message is truncated to 500 chars and must never contain file paths
    or credentials.
    """
    status = entry.get("status")
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}"
        )

    if entry.get("error_message"):
        entry["error_message"] = str(entry["error_message"])[:500]

    new_row = pd.DataFrame([entry])

    os.makedirs(os.path.dirname(RUN_LOG_PATH), exist_ok=True)

    con = duckdb.connect()

    if os.path.exists(RUN_LOG_PATH):
        existing = con.execute(
            f"SELECT * FROM read_parquet('{RUN_LOG_PATH}')"
        ).fetchdf()

        existing_keys = set(
            zip(existing["run_id"].tolist(), existing["model_name"].tolist())
        )
        new_key = (entry["run_id"], entry["model_name"])

        if new_key not in existing_keys:
            combined = pd.concat([existing, new_row], ignore_index=True)
        else:
            combined = existing
    else:
        combined = new_row

    con.execute(f"""
        COPY (SELECT * FROM combined)
        TO '{RUN_LOG_PATH}' (FORMAT PARQUET)
    """)

    con.close()
