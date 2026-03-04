# config.py


import os

# ---------------------------------------------------------------------------
# API connection
# ---------------------------------------------------------------------------
API_HOST = os.getenv("API_HOST", "https://dummyjson.com")
API_BASE_URL = f"{API_HOST}/products"

# ---------------------------------------------------------------------------
# API credentials (optional – DummyJSON public API does not require a key)
# ---------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY", None)          # Bearer token / API key
API_USERNAME = os.getenv("API_USERNAME", None) # Basic-auth username
API_PASSWORD = os.getenv("API_PASSWORD", None) # Basic-auth password

# ---------------------------------------------------------------------------
# Extraction parameters
# ---------------------------------------------------------------------------
TOTAL_PRODUCTS = int(os.getenv("TOTAL_PRODUCTS", "194"))  # Total products available on the API
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "10"))            # Products per API request (page size)
RETRY_LIMIT = int(os.getenv("RETRY_LIMIT", "5"))           # Max retry attempts per request
CONCURRENCY_LIMIT = int(os.getenv("CONCURRENCY_LIMIT", "5"))  # Async only: max concurrent requests

# ---------------------------------------------------------------------------
# Retry / backoff settings with standard values from the exponential backoff algorithm
# ---------------------------------------------------------------------------
RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", "2.0"))  # Exponential base (seconds)
RETRY_BACKOFF_MAX = float(os.getenv("RETRY_BACKOFF_MAX", "60.0"))   # Maximum backoff cap (seconds)

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------
DATA_DIR = os.getenv("DATA_DIR", "data/json")
LOG_DIR = os.getenv("LOG_DIR", "logs")