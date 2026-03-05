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

DUMMYJSON_HOST = os.getenv("DUMMYJSON_HOST", "https://dummyjson.com")
DUMMYJSON_BASE_URL = f"{DUMMYJSON_HOST}/products"
DUMMYJSON_API_KEY = os.getenv("DUMMYJSON_API_KEY", None)


# ---------------------------------------------------------------------------
# Mockaroo API
# ---------------------------------------------------------------------------

MOCKAROO_HOST = os.getenv("MOCKAROO_HOST", "https://api.mockaroo.com")
MOCKAROO_API_KEY = os.getenv("MOCKAROO_API_KEY", None)
MOCKAROO_SCHEMA_KEY = os.getenv("MOCKAROO_SCHEMA_KEY", None)
MOCKAROO_BASE_URL = f"{MOCKAROO_HOST}/api/{MOCKAROO_SCHEMA_KEY}.json"


