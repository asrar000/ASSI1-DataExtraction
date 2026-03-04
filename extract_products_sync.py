"""
extract_products_sync.py
------------------------
Synchronous script that extracts all products from the DummyJSON API using
the requests library.  Results are written to chunked JSON files under
data/json/ and structured logs are written to logs/<date>/.
"""

import json
import logging
import math
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------



SCRIPT_NAME = "extract_products_sync"


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
        # Merge any extra fields attached to the record
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

    # Also echo to stdout for convenience
    console = logging.StreamHandler()
    console.setFormatter(JsonFormatter())
    logger.addHandler(console)

    return logger

# ---------------------------------------------------------------------------
# HTTP session with built-in retry transport (network-level retries only)
# ---------------------------------------------------------------------------

def build_session():
    """Build a requests Session with a transport-level retry adapter.

    Application-level retries (4xx / 5xx / 429) are handled separately so
    that exponential back-off and logging can be applied.
    """
    session = requests.Session()
    adapter = HTTPAdapter(
        max_retries=Retry(total=0, raise_on_status=False)
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    if config.API_KEY:
        session.headers.update({"Authorization": f"Bearer {config.API_KEY}"})
    return session


# ---------------------------------------------------------------------------
# Core fetch helper
# ---------------------------------------------------------------------------

def fetch_chunk(session: requests.Session,logger: logging.Logger,limit: int,skip: int) :
    """Fetch a single page of products from the API with exponential backoff.

    Args:
        session: Active requests Session.
        logger:  Configured JSON logger.
        limit:   Number of products to request (CHUNK_SIZE).
        skip:    Offset into the product catalogue.

    Returns:
        List of product dicts for this chunk.

    Raises:
        RuntimeError: If all retry attempts are exhausted.
    """
    url = config.API_BASE_URL
    params = {"limit": limit, "skip": skip}
    request_id = f"req-{uuid.uuid4().int >> 64}"

    for attempt in range(config.RETRY_LIMIT + 1):
        try:
            start = time.monotonic()
            response = session.get(url, params=params, timeout=30)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)

            log_extra = {
                "request_id": request_id,
                "url": response.url,
                "method": "GET",
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
                "attempt": attempt + 1,
            }

            if response.status_code == 200:
                data = response.json()
                products = data.get("products", [])
                logger.info("Parsed JSON successfully", extra=log_extra)
                return products

            if response.status_code == 429 or response.status_code >= 500:
                wait = min(
                    config.RETRY_BACKOFF_BASE ** attempt,
                    config.RETRY_BACKOFF_MAX,
                )
                logger.warning(
                    f"Retryable error – sleeping {wait:.1f}s before retry",
                    extra={**log_extra, "wait_seconds": wait},
                )
                if attempt < config.RETRY_LIMIT:
                    time.sleep(wait)
                    continue

            # 4xx (non-429) – do not retry
            logger.error(
                f"Non-retryable HTTP error {response.status_code}",
                extra=log_extra,
            )
            response.raise_for_status()

        except requests.RequestException as exc:
            wait = min(
                config.RETRY_BACKOFF_BASE ** attempt,
                config.RETRY_BACKOFF_MAX,
            )
            logger.error(
                f"Request exception: {exc} – sleeping {wait:.1f}s",
                extra={
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

    raise RuntimeError(
        f"All {config.RETRY_LIMIT} retries exhausted for skip={skip}"
    )

def main():
    pass 



if __name__ == "__main__":
    main()