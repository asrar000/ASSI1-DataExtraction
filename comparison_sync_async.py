"""
comparison_sync_async.py
-------------------------
Runs both extraction scripts sequentially, measures their elapsed time,
and writes a comparison report to comparison_sync_async.md.

Usage:
    python comparison_sync_async.py
"""

import sys
from datetime import datetime, timezone

import extract_products_sync
import extract_products_async
import path


# ---------------------------------------------------------------------------
# Run both scripts
# ---------------------------------------------------------------------------

def run_comparison():
    """Run sync then async extraction and return their elapsed times in ms."""
    print("Running synchronous extraction...")
    sync_elapsed = extract_products_sync.main()

    print("Running asynchronous extraction...")
    async_elapsed = extract_products_async.main()

    return sync_elapsed, async_elapsed


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def write_report(sync_elapsed, async_elapsed):
    """Write a Markdown comparison report to comparison_sync_async.md."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    diff_ms = round(sync_elapsed - async_elapsed, 2)
    if async_elapsed < sync_elapsed:
        faster = "Async"
        speedup = round(sync_elapsed / async_elapsed, 2)
        verdict = (
            f"Async was faster by **{diff_ms} ms** "
            f"({speedup}× speedup over sync)."
        )
    elif sync_elapsed < async_elapsed:
        faster = "Sync"
        speedup = round(async_elapsed / sync_elapsed, 2)
        verdict = (
            f"Sync was faster by **{abs(diff_ms)} ms** "
            f"({speedup}× speedup over async)."
        )
    else:
        faster = "Tie"
        verdict = "Both scripts completed in exactly the same time."

    report = f"""\
# Sync vs Async Extraction — Comparison Report

Generated: {now}

## Results

| Script | Elapsed Time (ms) |
|---|---|
| `extract_products_sync.py` | {sync_elapsed} |
| `extract_products_async.py` | {async_elapsed} |

## Verdict

{verdict}

## Notes

- Both scripts extracted the same data: all DummyJSON products and all
  configured Mockaroo records.
- The sync script fetches one chunk at a time — DummyJSON first, then
  Mockaroo.
- The async script fetches all chunks from both sources concurrently,
  bounded by `CONCURRENCY_LIMIT`.
- Elapsed time is measured from script start to final log entry using
  `time.monotonic()` and reported in milliseconds.

"""

    report_path = path.BASE_DIR / "comparison_sync_async.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport written to {report_path}")
    return report_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    sync_elapsed, async_elapsed = run_comparison()
    write_report(sync_elapsed, async_elapsed)

    print(f"\nSync:  {sync_elapsed} ms")
    print(f"Async: {async_elapsed} ms")


if __name__ == "__main__":
    main()