# DummyJSON Product Extractor

## Description

This project contains two Python scripts that extract product data from the
DummyJSON public REST API (https://dummyjson.com/products) and write the
results to chunked JSON files on disk.

| Script | Description |
|---|---|
| `extract_products_sync.py` | Synchronous extractor using the `requests` library. Fetches one chunk at a time sequentially. |
| `extract_products_async.py` | Asynchronous extractor using `aiohttp` and `asyncio`. Dispatches multiple requests concurrently, bounded by `CONCURRENCY_LIMIT`. |

Both scripts:

- Write extracted products to `data/json/products_<chunk_number>_<date>_<time>.json`
- Write structured JSON logs to `logs/<YYMMDD>/<script_name>_<YYMMDD>_<HHMMSS>.json`
- Apply exponential backoff on retryable errors (HTTP 429, 5xx, network failures)
- Validate that each chunk contains exactly the expected number of products
- Emit a final log entry reporting the total execution time

---

## Project Structure

```
.
├── data/
│   └── json/                   # Extracted product chunks (generated at runtime)
├── logs/                       # JSON log files (generated at runtime)
├── config.py                   # Central configuration
├── config.sample               # Template showing all available environment variables
├── extract_products_sync.py    # Synchronous extraction script
├── extract_products_async.py   # Asynchronous extraction script
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd <project-folder>
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
```

Linux / macOS:
```bash
source .venv/bin/activate
```

Windows:
```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

All settings have defaults defined in `config.py` and the scripts will run
as-is without any changes. The DummyJSON public API requires no credentials.

If you want to override any value, set the environment variable directly in
your shell before running the script. For example:

Linux / macOS:
```bash
export TOTAL_PRODUCTS=50
export CHUNK_SIZE=5
```

Windows:
```bash
set TOTAL_PRODUCTS=50
set CHUNK_SIZE=5
```

A full list of available variables and their defaults is documented in
`config.sample`.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | `https://dummyjson.com` | Base URL of the API |
| `API_KEY` | None | Bearer token (if required by the API) |
| `API_USERNAME` | None | Basic-auth username (if required by the API) |
| `API_PASSWORD` | None | Basic-auth password (if required by the API) |
| `TOTAL_PRODUCTS` | `194` | Total number of products to extract |
| `CHUNK_SIZE` | `10` | Number of products per API request |
| `RETRY_LIMIT` | `5` | Maximum retries per request on failure or HTTP 429 |
| `CONCURRENCY_LIMIT` | `5` | Async script only: maximum concurrent requests |
| `RETRY_BACKOFF_BASE` | `2.0` | Exponential backoff base in seconds |
| `RETRY_BACKOFF_MAX` | `60.0` | Maximum backoff ceiling in seconds |
| `DATA_DIR` | `data/json` | Directory where output files are written |
| `LOG_DIR` | `logs` | Root directory for log files |

---

## Running the Scripts

Synchronous:
```bash
python extract_products_sync.py
```

Asynchronous:
```bash
python extract_products_async.py
```

Output files are written to `data/json/` and logs to `logs/<YYMMDD>/`.