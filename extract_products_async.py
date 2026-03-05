"""
extract_products_async.py
--------------------------
Asynchronous script that extracts product data from two sources:
  - DummyJSON  (https://dummyjson.com/products)
  - Mockaroo   (https://api.mockaroo.com/api/generate.json)

Both sources are fetched concurrently using aiohttp with bounded
concurrency. Results are written to chunked JSON files under data/json/
and structured logs are written to logs/<date>/.

Mockaroo schema fields (mirrors DummyJSON product structure):
  id, title, description, category, price, discountPercentage,
  rating, stock, brand, sku, weight, warrantyInformation,
  shippingInformation, availabilityStatus, returnPolicy,
  minimumOrderQuantity, thumbnail

Fields intentionally excluded from the Mockaroo schema:
  tags, dimensions, reviews, meta, images
  These are either nested objects or arrays that Mockaroo cannot
  generate in a flat schema and are not required for this pipeline.
"""

import asyncio
import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone

import aiohttp

import config
import path

# ---------------------------------------------------------------------------
# Script identity
# ---------------------------------------------------------------------------

SCRIPT_NAME = "extract_products_async"


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def format_log_record(record):
    """Serialize a LogRecord to a single-line JSON string.

    The fixed fields (timestamp, level, logger, message) come first.
    Any extra fields attached via the ``extra=`` kwarg are appended,
    excluding Python's built-in LogRecord attributes.
    """
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    for key, value in record.__dict__.items():
        if key not in (
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "id", "levelname", "levelno", "lineno", "message",
            "module", "msecs", "msg", "name", "pathname", "process",
            "processName", "relativeCreated", "stack_info", "thread", "threadName",
        ) and not key.startswith("_"):
            payload[key] = value
    return json.dumps(payload)


def build_logger(script_name):
    """Create and configure a JSON file logger for the given script name.

    The log file is placed at logs/<YYMMDD>/<script_name>_<YYMMDD>_<HHMMSS>.json.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%y%m%d")
    time_str = now.strftime("%H%M%S")

    log_dir = path.LOG_DIR / date_str
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{script_name}_{date_str}_{time_str}.json"

    logger = logging.getLogger(script_name)
    logger.setLevel(logging.DEBUG)

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter())
    handler.formatter.format = format_log_record
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter())
    console.formatter.format = format_log_record
    logger.addHandler(console)

    return logger


# ---------------------------------------------------------------------------
# DummyJSON async fetch
# ---------------------------------------------------------------------------

async def fetch_dummyjson_chunk(session, logger, semaphore, limit, skip, chunk_index):
    """Fetch one page of products from DummyJSON asynchronously.

    Uses limit/skip pagination. Retries on HTTP 429 and 5xx with
    exponential backoff. Returns a tuple of (chunk_index, records).
    Raises RuntimeError if all retry attempts are exhausted.
    """
    url = config.DUMMYJSON_BASE_URL
    params = {"limit": limit, "skip": skip}
    request_id = f"req-{uuid.uuid4().int >> 64}"

    for attempt in range(config.RETRY_LIMIT + 1):
        async with semaphore:
            try:
                start = time.monotonic()
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

                    log_extra = {
                        "source": "dummyjson",
                        "request_id": request_id,
                        "url": str(response.url),
                        "method": "GET",
                        "status_code": response.status,
                        "elapsed_ms": elapsed_ms,
                        "attempt": attempt + 1,
                        "chunk_index": chunk_index,
                    }

                    if response.status == 200:
                        records = (await response.json()).get("products", [])
                        logger.info("Parsed JSON successfully", extra=log_extra)
                        return chunk_index, records

                    if response.status == 429 or response.status >= 500:
                        wait = min(config.RETRY_BACKOFF_BASE ** attempt, config.RETRY_BACKOFF_MAX)
                        logger.warning(
                            f"Retryable error – sleeping {wait:.1f}s before retry",
                            extra={**log_extra, "wait_seconds": wait},
                        )
                        if attempt < config.RETRY_LIMIT:
                            await asyncio.sleep(wait)
                            continue

                    # 4xx (non-429) — the request itself is wrong, retrying will never succeed
                    logger.error(f"Non-retryable HTTP error {response.status}", extra=log_extra)
                    raise RuntimeError(f"DummyJSON: non-retryable HTTP {response.status} for chunk={chunk_index}")

            except RuntimeError:
                raise

            except aiohttp.ClientError as exc:
                wait = min(config.RETRY_BACKOFF_BASE ** attempt, config.RETRY_BACKOFF_MAX)
                logger.error(
                    f"Client exception: {exc} – sleeping {wait:.1f}s",
                    extra={
                        "source": "dummyjson",
                        "request_id": request_id,
                        "url": url,
                        "method": "GET",
                        "attempt": attempt + 1,
                        "chunk_index": chunk_index,
                        "wait_seconds": wait,
                    },
                )
                if attempt < config.RETRY_LIMIT:
                    await asyncio.sleep(wait)
                    continue

    raise RuntimeError(f"DummyJSON: all {config.RETRY_LIMIT} retries exhausted for chunk={chunk_index}")


# ---------------------------------------------------------------------------
# Mockaroo async fetch
# ---------------------------------------------------------------------------

async def fetch_mockaroo_chunk(session, logger, semaphore, count, chunk_index):
    """Fetch one chunk of records from Mockaroo asynchronously.

    Mockaroo generates data on demand per request. The schema key is embedded
    in the URL path and the API key is passed as a query parameter. The full
    URL including the API key is never written to logs — only the base URL
    is recorded.

    Retries on HTTP 429 and 5xx with exponential backoff.
    Raises RuntimeError immediately on 4xx errors.
    Returns a tuple of (chunk_index, records).
    Raises RuntimeError if all retry attempts are exhausted.
    """
    url = config.MOCKAROO_BASE_URL
    params = {"count": count, "key": config.MOCKAROO_API_KEY}
    request_id = f"req-{uuid.uuid4().int >> 64}"

    for attempt in range(config.RETRY_LIMIT + 1):
        async with semaphore:
            try:
                start = time.monotonic()
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

                    log_extra = {
                        "source": "mockaroo",
                        "request_id": request_id,
                        "url": config.MOCKAROO_BASE_URL,
                        "method": "GET",
                        "status_code": response.status,
                        "elapsed_ms": elapsed_ms,
                        "attempt": attempt + 1,
                        "chunk_index": chunk_index,
                    }

                    if response.status == 200:
                        raw = await response.text()
                        try:
                            import json as _json
                            records = _json.loads(raw)
                        except ValueError:
                            # Mockaroo returns 200 with a plain-text error message when
                            # the daily row limit is exceeded or the schema is misconfigured.
                            logger.error(
                                f"Mockaroo returned 200 but body is not JSON: {raw!r}",
                                extra={**log_extra, "response_body": raw},
                            )
                            raise RuntimeError(f"Mockaroo: non-JSON response for chunk={chunk_index}: {raw!r}")
                        logger.info("Parsed JSON successfully", extra=log_extra)
                        return chunk_index, records

                    if response.status == 429 or response.status >= 500:
                        wait = min(config.RETRY_BACKOFF_BASE ** attempt, config.RETRY_BACKOFF_MAX)
                        logger.warning(
                            f"Retryable error – sleeping {wait:.1f}s before retry",
                            extra={**log_extra, "wait_seconds": wait},
                        )
                        if attempt < config.RETRY_LIMIT:
                            await asyncio.sleep(wait)
                            continue

                    # 4xx (non-429) — the request itself is wrong, retrying will never succeed
                    raw_err = await response.text()
                    logger.error(
                        f"Non-retryable HTTP error {response.status}: {raw_err!r}",
                        extra={**log_extra, "response_body": raw_err},
                    )
                    raise RuntimeError(f"Mockaroo: non-retryable HTTP {response.status} for chunk={chunk_index}")

            except RuntimeError:
                raise

            except aiohttp.ClientError as exc:
                wait = min(config.RETRY_BACKOFF_BASE ** attempt, config.RETRY_BACKOFF_MAX)
                logger.error(
                    f"Client exception: {exc} – sleeping {wait:.1f}s",
                    extra={
                        "source": "mockaroo",
                        "request_id": request_id,
                        "url": url,
                        "method": "GET",
                        "attempt": attempt + 1,
                        "chunk_index": chunk_index,
                        "wait_seconds": wait,
                    },
                )
                if attempt < config.RETRY_LIMIT:
                    await asyncio.sleep(wait)
                    continue

    raise RuntimeError(f"Mockaroo: all {config.RETRY_LIMIT} retries exhausted for chunk={chunk_index}")


# ---------------------------------------------------------------------------
# Output helper
# ---------------------------------------------------------------------------

def write_chunk(records, source, chunk_number, date_str, time_str):
    """Write a list of records to a JSON file under data/json/.

    The filename format is: <source>_<chunk_number>_<date>_<time>.json
    where source is either 'dummyjson' or 'mockaroo'.
    """
    out_dir = path.DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{source}_{chunk_number}_{date_str}_{time_str}.json"
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    return file_path


# ---------------------------------------------------------------------------
# Main async orchestrator
# ---------------------------------------------------------------------------

async def run():
    """Build all tasks for both sources and run them concurrently.

    DummyJSON and Mockaroo tasks share the same semaphore so the total
    number of concurrent requests across both sources never exceeds
    CONCURRENCY_LIMIT. Results are sorted by chunk_index before being
    written to disk to guarantee correct file ordering.
    """
    script_start = time.monotonic()
    logger = build_logger(SCRIPT_NAME)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%y%m%d")
    time_str = now.strftime("%H%M%S")

    dj_total = config.DUMMYJSON_TOTAL_PRODUCTS
    dj_chunk_size = config.DUMMYJSON_CHUNK_SIZE
    mk_total = config.MOCKAROO_TOTAL_RECORDS
    mk_chunk_size = config.MOCKAROO_CHUNK_SIZE
    concurrency = config.CONCURRENCY_LIMIT

    dj_num_chunks = math.ceil(dj_total / dj_chunk_size)
    mk_num_chunks = math.ceil(mk_total / mk_chunk_size)

    logger.info(
        f"Async extraction started — "
        f"DummyJSON: {dj_total} products in {dj_num_chunks} chunks, "
        f"Mockaroo: {mk_total} records in {mk_num_chunks} chunks, "
        f"concurrency={concurrency}",
        extra={
            "dummyjson_total": dj_total,
            "dummyjson_chunks": dj_num_chunks,
            "mockaroo_total": mk_total,
            "mockaroo_chunks": mk_num_chunks,
            "concurrency_limit": concurrency,
        },
    )

    semaphore = asyncio.Semaphore(concurrency)

    dj_headers = {}
    if config.DUMMYJSON_API_KEY:
        dj_headers["Authorization"] = f"Bearer {config.DUMMYJSON_API_KEY}"

    async with aiohttp.ClientSession(headers=dj_headers) as dj_session, \
               aiohttp.ClientSession() as mk_session:

        dj_tasks = [
            fetch_dummyjson_chunk(
                dj_session, logger, semaphore,
                limit=min(dj_chunk_size, dj_total - i * dj_chunk_size),
                skip=i * dj_chunk_size,
                chunk_index=i,
            )
            for i in range(dj_num_chunks)
        ]

        mk_tasks = [
            fetch_mockaroo_chunk(
                mk_session, logger, semaphore,
                count=min(mk_chunk_size, mk_total - i * mk_chunk_size),
                chunk_index=i,
            )
            for i in range(mk_num_chunks)
        ]

        dj_results, mk_results = await asyncio.gather(
            asyncio.gather(*dj_tasks, return_exceptions=True),
            asyncio.gather(*mk_tasks, return_exceptions=True),
        )

    # ---------------------------------------------------------------------------
    # Process and write DummyJSON results
    # ---------------------------------------------------------------------------

    dj_ordered = []
    for result in dj_results:
        if isinstance(result, Exception):
            logger.error(f"DummyJSON chunk failed: {result}", extra={"source": "dummyjson"})
        else:
            dj_ordered.append(result)

    dj_ordered.sort(key=lambda x: x[0])
    dj_extracted = 0

    for chunk_index, records in dj_ordered:
        skip = chunk_index * dj_chunk_size
        expected = min(dj_chunk_size, dj_total - skip)

        if len(records) != expected:
            logger.warning(
                f"Expected {expected} records in DummyJSON chunk {chunk_index + 1}, got {len(records)}",
                extra={"source": "dummyjson", "chunk": chunk_index + 1, "expected": expected, "received": len(records)},
            )
        else:
            logger.info(
                f"DummyJSON chunk {chunk_index + 1} validated: {len(records)} records",
                extra={"source": "dummyjson", "chunk": chunk_index + 1, "count": len(records)},
            )

        file_path = write_chunk(records, "dummyjson", chunk_index + 1, date_str, time_str)
        dj_extracted += len(records)

        logger.info(
            f"DummyJSON chunk {chunk_index + 1} written to {file_path}",
            extra={"source": "dummyjson", "chunk": chunk_index + 1, "file": str(file_path)},
        )

    # ---------------------------------------------------------------------------
    # Process and write Mockaroo results
    # ---------------------------------------------------------------------------

    mk_ordered = []
    for result in mk_results:
        if isinstance(result, Exception):
            logger.error(f"Mockaroo chunk failed: {result}", extra={"source": "mockaroo"})
        else:
            mk_ordered.append(result)

    mk_ordered.sort(key=lambda x: x[0])
    mk_extracted = 0

    for chunk_index, records in mk_ordered:
        expected = min(mk_chunk_size, mk_total - chunk_index * mk_chunk_size)

        if len(records) != expected:
            logger.warning(
                f"Expected {expected} records in Mockaroo chunk {chunk_index + 1}, got {len(records)}",
                extra={"source": "mockaroo", "chunk": chunk_index + 1, "expected": expected, "received": len(records)},
            )
        else:
            logger.info(
                f"Mockaroo chunk {chunk_index + 1} validated: {len(records)} records",
                extra={"source": "mockaroo", "chunk": chunk_index + 1, "count": len(records)},
            )

        file_path = write_chunk(records, "mockaroo", chunk_index + 1, date_str, time_str)
        mk_extracted += len(records)

        logger.info(
            f"Mockaroo chunk {chunk_index + 1} written to {file_path}",
            extra={"source": "mockaroo", "chunk": chunk_index + 1, "file": str(file_path)},
        )

    # ---------------------------------------------------------------------------
    # Final timing log
    # ---------------------------------------------------------------------------

    total_elapsed = round((time.monotonic() - script_start) * 1000, 2)
    logger.info(
        f"All extractions complete in {total_elapsed} ms — "
        f"DummyJSON: {dj_extracted} records, Mockaroo: {mk_extracted} records",
        extra={
            "total_elapsed_ms": total_elapsed,
            "dummyjson_records": dj_extracted,
            "mockaroo_records": mk_extracted,
        },
    )
    return total_elapsed


def main():
    """Entry point: run the async extraction coroutine."""
    return asyncio.run(run())


if __name__ == "__main__":
    main()