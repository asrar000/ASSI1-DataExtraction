"""
extract_products_async.py
--------------------------
Asynchronous script that extracts all products from the DummyJSON API using
aiohttp with bounded concurrency.  Results are written to chunked JSON files
under data/json/ and structured logs are written to logs/<date>/.
"""

import asyncio
import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

SCRIPT_NAME = "extract_products_async"


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
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


def build_logger(script_name) :
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
# Core async fetch helper
# ---------------------------------------------------------------------------

async def fetch_chunk(session,logger,semaphore,limit,skip,chunk_index) :
    """Fetch a single page of products asynchronously with exponential backoff.

    Args:
        session:     Active aiohttp ClientSession.
        logger:      Configured JSON logger.
        semaphore:   Semaphore limiting concurrent requests.
        limit:       Number of products to request (CHUNK_SIZE or remainder).
        skip:        Offset into the product catalogue.
        chunk_index: 0-based chunk index (used to order results).

    Returns:
        Tuple of (chunk_index, list of product dicts).

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    url = config.API_BASE_URL
    params = {"limit": limit, "skip": skip}
    request_id = f"req-{uuid.uuid4().int >> 64}"

    for attempt in range(config.RETRY_LIMIT + 1):
        async with semaphore:
            try:
                start = time.monotonic()
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    elapsed_ms = round((time.monotonic() - start) * 1000, 2)

                    log_extra = {
                        "request_id": request_id,
                        "url": str(response.url),
                        "method": "GET",
                        "status_code": response.status,
                        "elapsed_ms": elapsed_ms,
                        "attempt": attempt + 1,
                        "chunk_index": chunk_index,
                    }

                    if response.status == 200:
                        data = await response.json()
                        products = data.get("products", [])
                        logger.info("Parsed JSON successfully", extra=log_extra)
                        return chunk_index, products

                    if response.status == 429 or response.status >= 500:
                        wait = min(
                            config.RETRY_BACKOFF_BASE ** attempt,
                            config.RETRY_BACKOFF_MAX,
                        )
                        logger.warning(
                            f"Retryable error – sleeping {wait:.1f}s before retry",
                            extra={**log_extra, "wait_seconds": wait},
                        )
                        if attempt < config.RETRY_LIMIT:
                            await asyncio.sleep(wait)
                            continue

                    # 4xx (non-429) – do not retry
                    logger.error(
                        f"Non-retryable HTTP error {response.status}",
                        extra=log_extra,
                    )
                    response.raise_for_status()

            except aiohttp.ClientError as exc:
                wait = min(
                    config.RETRY_BACKOFF_BASE ** attempt,
                    config.RETRY_BACKOFF_MAX,
                )
                logger.error(
                    f"Client exception: {exc} – sleeping {wait:.1f}s",
                    extra={
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

    raise RuntimeError(
        f"All {config.RETRY_LIMIT} retries exhausted for skip={skip}"
    )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def write_chunk(products,chunk_number,date_str,time_str) :
    """Persist a list of products to a JSON file.

    Args:
        products:     List of product dicts to serialize.
        chunk_number: 1-based chunk index used in the filename.
        date_str:     Date stamp (YYMMDD) for the filename.
        time_str:     Time stamp (HHMMSS) for the filename.

    Returns:
        Path of the written file.
    """
    out_dir = Path(config.DATA_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"products_{chunk_number}_{date_str}_{time_str}.json"
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(products, fh, indent=2, ensure_ascii=False)
    return file_path


# ---------------------------------------------------------------------------
# Main async orchestrator
# ---------------------------------------------------------------------------

async def run() :
    """Orchestrate asynchronous extraction of all products."""
    script_start = time.monotonic()
    logger = build_logger(SCRIPT_NAME)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%y%m%d")
    time_str = now.strftime("%H%M%S")

    total = config.TOTAL_PRODUCTS
    chunk_size = config.CHUNK_SIZE
    num_chunks = math.ceil(total / chunk_size)
    concurrency = config.CONCURRENCY_LIMIT

    logger.info(
        f"Starting async extraction: {total} products, "
        f"{chunk_size} per chunk, {num_chunks} chunks, "
        f"concurrency={concurrency}",
        extra={
            "total_products": total,
            "chunk_size": chunk_size,
            "num_chunks": num_chunks,
            "concurrency_limit": concurrency,
        },
    )

    semaphore = asyncio.Semaphore(concurrency)
    headers: dict[str, str] = {}
    if config.API_KEY:
        headers["Authorization"] = f"Bearer {config.API_KEY}"

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = []
        for chunk_index in range(num_chunks):
            skip = chunk_index * chunk_size
            limit = min(chunk_size, total - skip)
            tasks.append(
                fetch_chunk(session, logger, semaphore, limit=limit, skip=skip, chunk_index=chunk_index)
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Sort by chunk_index to maintain order
    ordered: list[tuple[int, list[dict]]] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"A chunk failed: {result}")
        else:
            ordered.append(result)

    ordered.sort(key=lambda x: x[0])

    products_extracted = 0
    for chunk_index, products in ordered:
        skip = chunk_index * chunk_size
        expected = min(chunk_size, total - skip)

        if len(products) != expected:
            logger.warning(
                f"Expected {expected} products in chunk {chunk_index + 1}, "
                f"got {len(products)}",
                extra={"chunk": chunk_index + 1, "expected": expected, "received": len(products)},
            )
        else:
            logger.info(
                f"Chunk {chunk_index + 1} validated: {len(products)} products",
                extra={"chunk": chunk_index + 1, "count": len(products)},
            )

        file_path = write_chunk(products, chunk_index + 1, date_str, time_str)
        products_extracted += len(products)

        logger.info(
            f"Chunk {chunk_index + 1} written → {file_path}",
            extra={"chunk": chunk_index + 1, "file": str(file_path)},
        )

    total_elapsed = round((time.monotonic() - script_start) * 1000, 2)
    logger.info(
        f"Extraction complete: {products_extracted} products across "
        f"{num_chunks} chunks in {total_elapsed} ms",
        extra={
            "total_products_extracted": products_extracted,
            "total_chunks": num_chunks,
            "total_elapsed_ms": total_elapsed,
        },
    )
def main():
    """Entry point: run the async extraction coroutine."""
    asyncio.run(run())
if __name__ == "__main__":
    main()