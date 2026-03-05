# Sync vs Async Extraction — Comparison Report

Generated: 2026-03-05 04:54:55 UTC

## Results

| Script | Elapsed Time (ms) |
|---|---|
| `extract_products_sync.py` | 5271.35 |
| `extract_products_async.py` | 1585.03 |

## Verdict

Async was faster by **3686.32 ms** (3.33× speedup over sync).

## Notes

- Both scripts extracted the same data: all DummyJSON products and all
  configured Mockaroo records.
- The sync script fetches one chunk at a time — DummyJSON first, then
  Mockaroo.
- The async script fetches all chunks from both sources concurrently,
  bounded by `CONCURRENCY_LIMIT`.
- Elapsed time is measured from script start to final log entry using
  `time.monotonic()` and reported in milliseconds.

