import os
import duckdb
from datetime import datetime, timezone
from pipeline.lib.paths import bronze_partition_path, BRONZE_TX_CODES


def load_bronze_partition(
    entity: str,
    source_path: str,
    date: str,
    dedup_key: str,
    run_id: str,
) -> dict:
    """
    Read-deduplicate-write pattern for Bronze ingestion (ARCHITECTURE.md Decision 1).

    For transaction_codes, date must be None.
    Existing records win over incoming on re-run — incoming rows that already
    exist (by dedup_key) are dropped, not replaced.

    Row order from source CSV is preserved in the output Parquet file.
    This is required for within-file account_id tie-breaking in Silver (Gap 3).

    Returns: {'records_written': int, 'source_count': int}
    """
    con = duckdb.connect()

    source_count = con.execute(
        f"SELECT COUNT(*) FROM read_csv_auto('{source_path}')"
    ).fetchone()[0]

    source_file = os.path.basename(source_path)
    ingested_at = datetime.now(timezone.utc).isoformat()

    # Read source preserving row order via rowid
    incoming = con.execute(f"""
        SELECT *,
               '{source_file}'  AS _source_file,
               '{ingested_at}'  AS _ingested_at,
               '{run_id}'       AS _pipeline_run_id
        FROM read_csv_auto('{source_path}')
    """).fetchdf()

    if entity == "transaction_codes":
        output_path = f"{BRONZE_TX_CODES}/data.parquet"
    else:
        output_path = bronze_partition_path(entity, date)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if os.path.exists(output_path):
        existing = con.execute(
            f"SELECT * FROM read_parquet('{output_path}')"
        ).fetchdf()

        # Existing records win: keep existing, append only new incoming rows
        existing_keys = set(existing[dedup_key].tolist())
        new_rows = incoming[~incoming[dedup_key].isin(existing_keys)]

        import pandas as pd
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = incoming

    # Write preserving row order — do not sort
    con.execute(f"""
        COPY (SELECT * FROM combined)
        TO '{output_path}' (FORMAT PARQUET)
    """)

    final_count = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{output_path}')"
    ).fetchone()[0]

    assert final_count >= source_count, (
        f"Bronze completeness failure: {entity} {date}: "
        f"source={source_count}, bronze={final_count}"
    )

    con.close()
    return {"records_written": final_count, "source_count": source_count}
