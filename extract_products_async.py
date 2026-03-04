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


def main():
    pass
if __name__ == "__main__":
    main()