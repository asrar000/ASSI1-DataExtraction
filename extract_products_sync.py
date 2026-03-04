"""
extract_products_sync.py
------------------------
Synchronous script that extracts product data from two sources:
  - DummyJSON  (https://dummyjson.com/products)
  - Mockaroo   (https://api.mockaroo.com/api/generate.json)

Each source is fetched sequentially in chunks. Results are written to
chunked JSON files under data/json/ and structured logs are written
to logs/<date>/.

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

import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

# ---------------------------------------------------------------------------
# Script identity
# ---------------------------------------------------------------------------

SCRIPT_NAME = "extract_products_sync"


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record):
        """Serialize a LogRecord to a JSON string."""
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
                "processName", "relativeCreated", "stack_info", "thread",
                "threadName",
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

    log_dir = Path(config.LOG_DIR) / date_str
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{script_name}_{date_str}_{time_str}.json"

    logger = logging.getLogger(script_name)
    logger.setLevel(logging.DEBUG)

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(JsonFormatter())
    logger.addHandler(console)

    return logger


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def build_session(api_key=None):
    """Build a requests Session and attach an Authorization header if an API key is provided.

    Application-level retries are handled manually so that exponential
    backoff and logging can be applied to every attempt.
    """
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=Retry(total=0, raise_on_status=False))
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    if api_key:
        session.headers.update({"Authorization": f"Bearer {api_key}"})

    return session


# ---------------------------------------------------------------------------
# DummyJSON fetch
# ---------------------------------------------------------------------------

def fetch_dummyjson_chunk(session, logger, limit, skip):
    """Fetch one page of products from DummyJSON using limit/skip pagination.

    Retries on HTTP 429 and 5xx responses using exponential backoff.
    Raises RuntimeError if all retry attempts are exhausted.
    """
    url = config.DUMMYJSON_BASE_URL
    params = {"limit": limit, "skip": skip}
    request_id = f"req-{uuid.uuid4().int >> 64}"

    for attempt in range(config.RETRY_LIMIT + 1):
        try:
            start = time.monotonic()
            response = session.get(url, params=params, timeout=30)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            log_extra = {
                "source": "dummyjson",
                "request_id": request_id,
                "url": response.url,
                "method": "GET",
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "attempt": attempt + 1,
            }

            if response.status_code == 200:
                records = response.json().get("products", [])
                logger.info("Parsed JSON successfully", extra=log_extra)
                return records

            if response.status_code == 429 or response.status_code >= 500:
                wait = min(config.RETRY_BACKOFF_BASE ** attempt, config.RETRY_BACKOFF_MAX)
                logger.warning(
                    f"Retryable error – sleeping {wait:.1f}s before retry",
                    extra={**log_extra, "wait_seconds": wait},
                )
                if attempt < config.RETRY_LIMIT:
                    time.sleep(wait)
                    continue

            # 4xx (non-429) — the request itself is wrong, retrying will never succeed
            logger.error(f"Non-retryable HTTP error {response.status_code}", extra=log_extra)
            raise RuntimeError(f"DummyJSON: non-retryable HTTP {response.status_code} for skip={skip}")

        except RuntimeError:
            raise

        except requests.RequestException as exc:
            wait = min(config.RETRY_BACKOFF_BASE ** attempt, config.RETRY_BACKOFF_MAX)
            logger.error(
                f"Request exception: {exc} – sleeping {wait:.1f}s",
                extra={
                    "source": "dummyjson",
                    "request_id": request_id,
                    "url": url,
                    "method": "GET",
                    "attempt": attempt + 1,
                    "wait_seconds": wait,
                },
            )
            if attempt < config.RETRY_LIMIT:
                time.sleep(wait)
                continue

    raise RuntimeError(f"DummyJSON: all {config.RETRY_LIMIT} retries exhausted for skip={skip}")


# ---------------------------------------------------------------------------
# Mockaroo fetch
# ---------------------------------------------------------------------------

def fetch_mockaroo_chunk(session, logger, count, chunk_index):
    """Fetch one chunk of records from Mockaroo.

    Mockaroo generates fresh data per request. The count parameter controls
    how many records are returned. The schema key is embedded in the URL path
    and the API key is passed as a query parameter. The full URL including
    the API key is never written to logs — only the base URL is recorded.

    Retries on HTTP 429 and 5xx responses using exponential backoff.
    Raises RuntimeError immediately on 4xx errors — these indicate a bad
    request that retrying will never fix.
    Raises RuntimeError if all retry attempts are exhausted.
    """
    url = config.MOCKAROO_BASE_URL
    params = {"count": count, "key": config.MOCKAROO_API_KEY}
    request_id = f"req-{uuid.uuid4().int >> 64}"

    for attempt in range(config.RETRY_LIMIT + 1):
        try:
            start = time.monotonic()
            response = session.get(url, params=params, timeout=30)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            log_extra = {
                "source": "mockaroo",
                "request_id": request_id,
                "url": config.MOCKAROO_BASE_URL,
                "method": "GET",
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "attempt": attempt + 1,
                "chunk_index": chunk_index,
            }

            if response.status_code == 200:
                records = response.json()
                logger.info("Parsed JSON successfully", extra=log_extra)
                return records

            if response.status_code == 429 or response.status_code >= 500:
                wait = min(config.RETRY_BACKOFF_BASE ** attempt, config.RETRY_BACKOFF_MAX)
                logger.warning(
                    f"Retryable error – sleeping {wait:.1f}s before retry",
                    extra={**log_extra, "wait_seconds": wait},
                )
                if attempt < config.RETRY_LIMIT:
                    time.sleep(wait)
                    continue

            # 4xx (non-429) — the request itself is wrong, retrying will never succeed
            logger.error(f"Non-retryable HTTP error {response.status_code}", extra=log_extra)
            raise RuntimeError(f"Mockaroo: non-retryable HTTP {response.status_code} for chunk={chunk_index}")

        except RuntimeError:
            raise

        except requests.RequestException as exc:
            wait = min(config.RETRY_BACKOFF_BASE ** attempt, config.RETRY_BACKOFF_MAX)
            logger.error(
                f"Request exception: {exc} – sleeping {wait:.1f}s",
                extra={
                    "source": "mockaroo",
                    "request_id": request_id,
                    "url": url,
                    "method": "GET",
                    "attempt": attempt + 1,
                    "wait_seconds": wait,
                },
            )
            if attempt < config.RETRY_LIMIT:
                time.sleep(wait)
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
    out_dir = Path(config.DATA_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{source}_{chunk_number}_{date_str}_{time_str}.json"
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    return file_path


# ---------------------------------------------------------------------------
# Source orchestrators
# ---------------------------------------------------------------------------

def extract_dummyjson(session, logger, date_str, time_str):
    """Run the full DummyJSON extraction loop.

    Fetches all products in chunks using limit/skip pagination, validates
    each chunk, writes each chunk to disk, and returns the total record count.
    """
    total = config.DUMMYJSON_TOTAL_PRODUCTS
    chunk_size = config.CHUNK_SIZE
    num_chunks = math.ceil(total / chunk_size)
    records_extracted = 0

    logger.info(
        f"Starting DummyJSON extraction: {total} products, "
        f"{chunk_size} per chunk, {num_chunks} chunks expected",
        extra={"source": "dummyjson", "total": total, "chunk_size": chunk_size, "num_chunks": num_chunks},
    )

    for chunk_index in range(num_chunks):
        skip = chunk_index * chunk_size
        limit = min(chunk_size, total - skip)

        logger.info(
            f"Fetching DummyJSON chunk {chunk_index + 1}/{num_chunks} (skip={skip}, limit={limit})",
            extra={"source": "dummyjson", "chunk": chunk_index + 1, "skip": skip, "limit": limit},
        )

        records = fetch_dummyjson_chunk(session, logger, limit=limit, skip=skip)

        if len(records) != limit:
            logger.warning(
                f"Expected {limit} records in chunk {chunk_index + 1}, got {len(records)}",
                extra={"source": "dummyjson", "chunk": chunk_index + 1, "expected": limit, "received": len(records)},
            )
        else:
            logger.info(
                f"Chunk {chunk_index + 1} validated: {len(records)} records",
                extra={"source": "dummyjson", "chunk": chunk_index + 1, "count": len(records)},
            )

        file_path = write_chunk(records, "dummyjson", chunk_index + 1, date_str, time_str)
        records_extracted += len(records)

        logger.info(
            f"DummyJSON chunk {chunk_index + 1} written to {file_path}",
            extra={"source": "dummyjson", "chunk": chunk_index + 1, "file": str(file_path)},
        )

    return records_extracted


def extract_mockaroo(session, logger, date_str, time_str):
    """Run the full Mockaroo extraction loop.

    Mockaroo generates data on demand — each request returns a fresh batch.
    Fetches all records in chunks, validates each chunk, writes each chunk
    to disk, and returns the total record count.
    """
    total = config.MOCKAROO_TOTAL_RECORDS
    chunk_size = config.CHUNK_SIZE
    num_chunks = math.ceil(total / chunk_size)
    records_extracted = 0

    logger.info(
        f"Starting Mockaroo extraction: {total} records, "
        f"{chunk_size} per chunk, {num_chunks} chunks expected",
        extra={"source": "mockaroo", "total": total, "chunk_size": chunk_size, "num_chunks": num_chunks},
    )

    for chunk_index in range(num_chunks):
        count = min(chunk_size, total - chunk_index * chunk_size)

        logger.info(
            f"Fetching Mockaroo chunk {chunk_index + 1}/{num_chunks} (count={count})",
            extra={"source": "mockaroo", "chunk": chunk_index + 1, "count": count},
        )

        records = fetch_mockaroo_chunk(session, logger, count=count, chunk_index=chunk_index)

        if len(records) != count:
            logger.warning(
                f"Expected {count} records in chunk {chunk_index + 1}, got {len(records)}",
                extra={"source": "mockaroo", "chunk": chunk_index + 1, "expected": count, "received": len(records)},
            )
        else:
            logger.info(
                f"Chunk {chunk_index + 1} validated: {len(records)} records",
                extra={"source": "mockaroo", "chunk": chunk_index + 1, "count": len(records)},
            )

        file_path = write_chunk(records, "mockaroo", chunk_index + 1, date_str, time_str)
        records_extracted += len(records)

        logger.info(
            f"Mockaroo chunk {chunk_index + 1} written to {file_path}",
            extra={"source": "mockaroo", "chunk": chunk_index + 1, "file": str(file_path)},
        )

    return records_extracted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Entry point: run DummyJSON and Mockaroo extractions sequentially."""
    script_start = time.monotonic()
    logger = build_logger(SCRIPT_NAME)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%y%m%d")
    time_str = now.strftime("%H%M%S")

    logger.info("Synchronous extraction started", extra={"script": SCRIPT_NAME})

    dummyjson_session = build_session(api_key=config.DUMMYJSON_API_KEY)
    mockaroo_session = build_session()

    dummyjson_total = extract_dummyjson(dummyjson_session, logger, date_str, time_str)
    mockaroo_total = extract_mockaroo(mockaroo_session, logger, date_str, time_str)

    total_elapsed = round((time.monotonic() - script_start) * 1000, 2)
    logger.info(
        f"All extractions complete in {total_elapsed} ms — "
        f"DummyJSON: {dummyjson_total} records, Mockaroo: {mockaroo_total} records",
        extra={
            "total_elapsed_ms": total_elapsed,
            "dummyjson_records": dummyjson_total,
            "mockaroo_records": mockaroo_total,
        },
    )


if __name__ == "__main__":
    main()