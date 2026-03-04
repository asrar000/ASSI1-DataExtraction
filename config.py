# config.py
#
# Reads all configuration from environment variables.
# Values are loaded automatically from the .env file at startup via python-dotenv.
# If a variable is not set, the default shown here is used instead.
#
# To configure the project:
#   1. Copy .env.example to .env
#   2. Fill in MOCKAROO_API_KEY and MOCKAROO_SCHEMA_KEY
#   3. Run the scripts — no manual exporting needed


import os
from dotenv import load_dotenv

# Load variables from .env into the environment before reading any values.
# If .env does not exist, this does nothing and the defaults below apply.
load_dotenv()


# ---------------------------------------------------------------------------
# DummyJSON API
# ---------------------------------------------------------------------------

# Base URL for the DummyJSON products endpoint
DUMMYJSON_HOST = os.getenv("DUMMYJSON_HOST", "https://dummyjson.com")
DUMMYJSON_BASE_URL = f"{DUMMYJSON_HOST}/products"

# DummyJSON is a public API and does not require credentials.
# Only set this if you are pointing the scripts at a secured instance.
DUMMYJSON_API_KEY = os.getenv("DUMMYJSON_API_KEY", None)


# ---------------------------------------------------------------------------
# Mockaroo API
# ---------------------------------------------------------------------------

# Base URL for the Mockaroo data generation endpoint
MOCKAROO_HOST = os.getenv("MOCKAROO_HOST", "https://api.mockaroo.com")
MOCKAROO_BASE_URL = f"{MOCKAROO_HOST}/api/generate.json"

# Your Mockaroo API key — required. Set this in your .env file.
# Get it from: https://mockaroo.com → My Account → API Key
MOCKAROO_API_KEY = os.getenv("MOCKAROO_API_KEY", None)

# The key of the Mockaroo schema to generate data from.
# Find it in your Mockaroo account on the schema detail page.
MOCKAROO_SCHEMA_KEY = os.getenv("MOCKAROO_SCHEMA_KEY", None)


# ---------------------------------------------------------------------------
# Extraction parameters
# ---------------------------------------------------------------------------

# Total number of products to extract from DummyJSON
DUMMYJSON_TOTAL_PRODUCTS = int(os.getenv("DUMMYJSON_TOTAL_PRODUCTS", "194"))

# Total number of records to extract from Mockaroo across all chunks
MOCKAROO_TOTAL_RECORDS = int(os.getenv("MOCKAROO_TOTAL_RECORDS", "100"))

# Number of records per API call — applies to both sources
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "10"))

# Maximum number of retries per request on failure or HTTP 429
RETRY_LIMIT = int(os.getenv("RETRY_LIMIT", "5"))

# Async script only: maximum number of concurrent requests across both sources
CONCURRENCY_LIMIT = int(os.getenv("CONCURRENCY_LIMIT", "5"))


# ---------------------------------------------------------------------------
# Retry / backoff settings
# ---------------------------------------------------------------------------

# Exponential backoff base — wait time grows as BASE ^ attempt number
RETRY_BACKOFF_BASE = float(os.getenv("RETRY_BACKOFF_BASE", "2.0"))

# Maximum wait ceiling in seconds — no single wait will ever exceed this
RETRY_BACKOFF_MAX = float(os.getenv("RETRY_BACKOFF_MAX", "60.0"))


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

# Where chunked JSON data files are written
DATA_DIR = os.getenv("DATA_DIR", "data/json")

# Root folder for log files (a dated sub-folder is created automatically)
LOG_DIR = os.getenv("LOG_DIR", "logs")