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
import os
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


def build_logger(script_name: str) -> logging.Logger:
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

async def fetch_chunk(
    session: aiohttp.ClientSession,
    logger: logging.Logger,
    semaphore: asyncio.Semaphore,
    limit: int,
    skip: int,
    chunk_index: int,
) -> tuple[int, list[dict]]:
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

def main():
    pass
if __name__ == "__main__":
    main()