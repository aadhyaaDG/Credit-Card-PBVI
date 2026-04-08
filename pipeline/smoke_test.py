import duckdb
import os
import sys

TEST_PATH = "data/bronze/transactions/date=2024-01-01/data.parquet"

def run():
    con = duckdb.connect()

    os.makedirs(os.path.dirname(TEST_PATH), exist_ok=True)

    con.execute(f"""
        COPY (SELECT 1 AS id, 'alpha' AS value
              UNION ALL SELECT 2, 'beta'
              UNION ALL SELECT 3, 'gamma')
        TO '{TEST_PATH}' (FORMAT PARQUET)
    """)

    result_a = con.execute(f"""
        SELECT date, COUNT(*) AS cnt
        FROM read_parquet('data/bronze/transactions/**/*.parquet',
                          hive_partitioning=true)
        GROUP BY date
    """).fetchall()

    result_b = con.execute(f"""
        SELECT regexp_extract(filename, 'date=([0-9\\-]+)', 1) AS date_part,
               COUNT(*) AS cnt
        FROM read_parquet('data/bronze/transactions/**/*.parquet', filename=true)
        GROUP BY date_part
    """).fetchall()

    print(f"hive_partitioning result:  {result_a}")
    print(f"regexp_extract result:     {result_b}")

    ok = True
    if not result_a:
        print("FAIL: hive_partitioning returned no rows")
        ok = False
    else:
        date_val = str(result_a[0][0])
        cnt_val = result_a[0][1]
        if date_val != "2024-01-01":
            print(f"FAIL: hive_partitioning date mismatch — got {date_val}")
            ok = False
        if cnt_val != 3:
            print(f"FAIL: hive_partitioning count mismatch — got {cnt_val}")
            ok = False

    if not result_b:
        print("FAIL: regexp_extract returned no rows")
        ok = False
    else:
        date_part = result_b[0][0]
        cnt_b = result_b[0][1]
        if date_part != "2024-01-01":
            print(f"FAIL: regexp_extract date mismatch — got {date_part}")
            ok = False
        if cnt_b != 3:
            print(f"FAIL: regexp_extract count mismatch — got {cnt_b}")
            ok = False

    con.close()

    if os.path.exists(TEST_PATH):
        os.remove(TEST_PATH)
        parent = os.path.dirname(TEST_PATH)
        if not os.listdir(parent):
            os.rmdir(parent)

    if ok:
        print("PASS")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run()
