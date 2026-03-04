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

MOCKAROO_HOST = os.getenv("MOCKAROO_HOST", "https://api.mockaroo.com")

# Your Mockaroo API key — required. Set this in your .env file.
# Get it from: https://mockaroo.com → My Account → API Key
MOCKAROO_API_KEY = os.getenv("MOCKAROO_API_KEY", None)

# The schema key identifies which Mockaroo schema to use.
# It comes from the API URL on your schema page, e.g.:
#   https://api.mockaroo.com/api/bb185820.json?count=10&key=...
#                                    ^^^^^^^^
# That 8-character value between /api/ and .json is your schema key.
MOCKAROO_SCHEMA_KEY = os.getenv("MOCKAROO_SCHEMA_KEY", None)

# The schema key is part of the URL path, not a query parameter.
# Correct:   https://api.mockaroo.com/api/<schema_key>.json?count=10&key=<api_key>
# Incorrect: https://api.mockaroo.com/api/generate.json?schema=<schema_key>&...
MOCKAROO_BASE_URL = f"{MOCKAROO_HOST}/api/{MOCKAROO_SCHEMA_KEY}.json"


# ---------------------------------------------------------------------------
# Extraction parameters
# ---------------------------------------------------------------------------

# Total number of products to extract from DummyJSON
DUMMYJSON_TOTAL_PRODUCTS = int(os.getenv("DUMMYJSON_TOTAL_PRODUCTS", "194"))

# Number of records per DummyJSON API call (pagination page size)
DUMMYJSON_CHUNK_SIZE = int(os.getenv("DUMMYJSON_CHUNK_SIZE", "10"))

# Total number of records to extract from Mockaroo.
# Mockaroo free tier allows 200 rows per day across all requests.
# Default is 10 — fetched in a single request — to stay well within the limit.
MOCKAROO_TOTAL_RECORDS = int(os.getenv("MOCKAROO_TOTAL_RECORDS", "10"))

# Number of records per Mockaroo API call.
# Default matches MOCKAROO_TOTAL_RECORDS so only one request is made.
MOCKAROO_CHUNK_SIZE = int(os.getenv("MOCKAROO_CHUNK_SIZE", "10"))

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