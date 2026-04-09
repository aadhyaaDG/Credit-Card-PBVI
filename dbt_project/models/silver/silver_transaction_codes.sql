{{
    config(
        materialized='table',
        post_hook=[
            "COPY (SELECT * FROM {{ this }}) TO '/app/data/silver/transaction_codes/data.parquet' (FORMAT PARQUET)"
        ]
    )
}}

SELECT
    -- all source fields from Bronze, excluding Bronze-specific audit columns
    * EXCLUDE (_ingested_at, _pipeline_run_id),

    -- Bronze audit carried forward
    _ingested_at                AS _bronze_ingested_at,

    -- Silver audit (INV-11 — must be non-null)
    '{{ var("run_id") }}'       AS _pipeline_run_id

FROM read_parquet('/app/data/bronze/transaction_codes/data.parquet')
