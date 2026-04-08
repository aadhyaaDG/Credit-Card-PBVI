"""
Phase 8 sign-off script: verify source-to-Bronze row count completeness
for all 7 transaction partitions and all 7 accounts partitions.
Exits 1 if any row shows a mismatch.
"""
import os
import sys
import duckdb

SOURCE_DIR = "source"


def get_source_count(path: str) -> int:
    return duckdb.connect().execute(
        f"SELECT COUNT(*) FROM read_csv_auto('{path}')"
    ).fetchone()[0]


def get_bronze_count(glob: str) -> dict:
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT regexp_extract(filename, 'date=([0-9\\-]+)', 1) AS date_part,
               COUNT(*) AS cnt
        FROM read_parquet('{glob}', filename=true)
        GROUP BY date_part
        ORDER BY date_part
    """).fetchall()
    return {r[0]: r[1] for r in rows}


def main():
    all_pass = True
    print(f"{'entity':<15} {'date_part':<14} {'source':>8} {'bronze':>8} {'match':>6}")
    print("-" * 58)

    for entity, glob in [
        ("transactions", "data/bronze/transactions/**/*.parquet"),
        ("accounts",     "data/bronze/accounts/**/*.parquet"),
    ]:
        bronze_counts = get_bronze_count(glob)
        prefix = f"{entity}_"
        for filename in sorted(os.listdir(SOURCE_DIR)):
            if not filename.startswith(prefix):
                continue
            if not filename.endswith(".csv"):
                continue
            # extract date from filename pattern entity_YYYY-MM-DD.csv
            parts = filename.replace(".csv", "").split("_")
            date_part = parts[-1]
            source_path = os.path.join(SOURCE_DIR, filename)
            src = get_source_count(source_path)
            brz = bronze_counts.get(date_part, 0)
            match = src == brz
            if not match:
                all_pass = False
            print(f"{entity:<15} {date_part:<14} {src:>8} {brz:>8} {'OK' if match else 'FAIL':>6}")

    print()
    if all_pass:
        print("All Bronze partitions match source. PASS")
        sys.exit(0)
    else:
        print("One or more Bronze partitions do not match source. FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
