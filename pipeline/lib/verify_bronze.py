import os
import duckdb


def verify_source_to_bronze(entity: str, source_path: str, date: str) -> None:
    """
    Assert Bronze row count equals source CSV row count after each partition write.
    Raises AssertionError if counts do not match. Silent on success.
    Called by pipeline entry points after every Bronze load (I-16).
    """
    con = duckdb.connect()

    source_count = con.execute(
        f"SELECT COUNT(*) FROM read_csv_auto('{source_path}')"
    ).fetchone()[0]

    if entity == "transaction_codes":
        parquet_path = "data/bronze/transaction_codes/data.parquet"
    else:
        parquet_path = f"data/bronze/{entity}/date={date}/data.parquet"

    if not os.path.exists(parquet_path):
        raise AssertionError(
            f"Bronze completeness failure: {entity} {date}: "
            f"parquet file does not exist at {parquet_path}"
        )

    bronze_count = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
    ).fetchone()[0]

    con.close()

    assert bronze_count >= source_count, (
        f"Bronze completeness failure: {entity} {date}: "
        f"source={source_count}, bronze={bronze_count}"
    )
