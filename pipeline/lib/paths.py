import os

BASE = "/app"

BRONZE_TRANSACTIONS = "data/bronze/transactions"
BRONZE_ACCOUNTS     = "data/bronze/accounts"
BRONZE_TX_CODES     = "data/bronze/transaction_codes"
SILVER_TRANSACTIONS = "data/silver/transactions"
SILVER_ACCOUNTS     = "data/silver/accounts"
SILVER_TX_CODES     = "data/silver/transaction_codes"
SILVER_QUARANTINE   = "data/silver/quarantine"
GOLD_DAILY          = "data/gold/daily_summary"
GOLD_WEEKLY         = "data/gold/weekly_account_summary"
PIPELINE_DIR        = "data/pipeline"
SOURCE_DIR          = "source"

_ALL_DATA_DIRS = [
    BRONZE_TRANSACTIONS,
    BRONZE_ACCOUNTS,
    BRONZE_TX_CODES,
    SILVER_TRANSACTIONS,
    SILVER_ACCOUNTS,
    SILVER_TX_CODES,
    SILVER_QUARANTINE,
    GOLD_DAILY,
    GOLD_WEEKLY,
    PIPELINE_DIR,
]


def ensure_dirs() -> None:
    for d in _ALL_DATA_DIRS:
        os.makedirs(d, exist_ok=True)


def bronze_partition_path(entity: str, date: str) -> str:
    mapping = {
        "transactions":    BRONZE_TRANSACTIONS,
        "accounts":        BRONZE_ACCOUNTS,
        "transaction_codes": BRONZE_TX_CODES,
    }
    if entity not in mapping:
        raise ValueError(f"Unknown entity: {entity}")
    if entity == "transaction_codes":
        return f"{BRONZE_TX_CODES}/data.parquet"
    return f"{mapping[entity]}/date={date}/data.parquet"
