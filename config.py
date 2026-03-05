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


