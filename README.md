# DummyJSON + Mockaroo Product Extractor

## Description

This project contains two Python scripts that extract product data from two sources:

- **DummyJSON** (https://dummyjson.com/products) — a public product catalogue API
- **Mockaroo** (https://api.mockaroo.com/api/bb185820.json) — a schema-based mock data generation API. The schema is publicly shared at https://www.mockaroo.com/bb185820

Both sources are extracted in the same script run and written to chunked JSON files on disk.

| Script | Description |
|---|---|
| `extract_products_sync.py` | Synchronous extractor using the `requests` library. Fetches DummyJSON first, then Mockaroo, one chunk at a time. |
| `extract_products_async.py` | Asynchronous extractor using `aiohttp` and `asyncio`. Fetches chunks from both sources concurrently, bounded by `CONCURRENCY_LIMIT`. |

Both scripts:

- Write DummyJSON output to `data/json/dummyjson_<chunk>_<date>_<time>.json`
- Write Mockaroo output to `data/json/mockaroo_<chunk>_<date>_<time>.json`
- Write structured JSON logs to `logs/<YYMMDD>/<script_name>_<YYMMDD>_<HHMMSS>.json`
- Apply exponential backoff on retryable errors (HTTP 429, 5xx, network failures)
- Validate that each chunk contains exactly the expected number of records
- Never write the Mockaroo API key to logs
- Emit a final log entry reporting total execution time and record counts for both sources
- Return `total_elapsed_ms` from `main()` so they can be called programmatically

---

## Mockaroo Schema

The Mockaroo schema is designed to mirror the flat fields of a DummyJSON product record
as closely as possible. It is publicly accessible — any Mockaroo account can generate
data from it using the schema key `bb185820`.

The schema output format must be set to **JSON** (not SQL or CSV).

| Field | Mockaroo Type | Settings |
|---|---|---|
| `id` | Row Number | — |
| `title` | Product (Grocery) | — |
| `description` | Sentences | At least 1, no more than 10 |
| `category` | Custom List | beauty, fragrances, furniture, groceries, home-decoration, kitchen-accessories, laptops, mens-shirts, mens-shoes, mens-watches, mobile-accessories, motorcycle, skin-care, smartphones, sports-accessories, sunglasses, tablets, tops, vehicle, womens-bags, womens-dresses, womens-jewellery, womens-shoes, womens-watches |
| `price` | Number | Min: 1, Max: 2000, Decimals: 2 |
| `discountPercentage` | Number | Min: 1, Max: 30, Decimals: 2 |
| `rating` | Number | Min: 1, Max: 5, Decimals: 2 |
| `stock` | Number | Min: 0, Max: 200, Decimals: 0 |
| `brand` | Company Name | — |
| `sku` | Regular Expression | `[A-Z0-9]{8}` |
| `weight` | Number | Min: 1, Max: 50, Decimals: 0 |
| `warrantyInformation` | Custom List | 1 month warranty, 3 months warranty, 6 months warranty, 1 year warranty, 2 year warranty, No warranty |
| `shippingInformation` | Custom List | Ships in 1-2 business days, Ships in 3-5 business days, Ships in 1 week, Ships in 2 weeks, Ships in 1 month |
| `availabilityStatus` | Custom List | In Stock, Low Stock, Out of Stock |
| `returnPolicy` | Custom List | No return policy, 7 days return policy, 14 days return policy, 30 days return policy, 60 days return policy, 90 days return policy |
| `minimumOrderQuantity` | Number | Min: 1, Max: 100, Decimals: 0 |
| `thumbnail` | URL | Protocol, host, path, query string all enabled |

The following DummyJSON fields are intentionally excluded from the Mockaroo schema.
They are either nested objects or arrays that a flat schema generator cannot produce:

- `tags` — variable-length array of strings
- `dimensions` — nested object containing width, height, and depth
- `reviews` — array of nested objects with reviewer name, rating, and comment
- `meta` — nested object containing timestamps, barcode, and QR code URL
- `images` — array of image URLs

---

## Mockaroo Daily Limit

The Mockaroo free tier allows **200 rows per day** across all requests. To stay within
this limit the defaults are set to extract 10 Mockaroo records per run (one request).

If you hit the limit, Mockaroo returns HTTP 200 with a plain-text error message instead
of JSON. The scripts detect this, log the raw response body, and exit with a clear error.

Options when the limit is reached:

- Wait until midnight UTC for the counter to reset
- Upgrade your Mockaroo account for a higher limit
- Use a second Mockaroo account with a different API key — the schema is public so any
  account can generate data from `bb185820`
- Reduce `MOCKAROO_TOTAL_RECORDS` in `.env` to use fewer rows per run

---

## Project Structure

```
.
├── data/
│   └── json/                      # Extracted data files (generated at runtime)
├── logs/                          # JSON log files (generated at runtime)
├── .env.example                   # Template showing all required environment variables
├── .env                           # Your local credentials — never committed
├── config.py                      # Central configuration — reads from .env automatically
├── path.py                        # Filesystem path constants (DATA_DIR, LOG_DIR, BASE_DIR)
├── extract_products_sync.py       # Synchronous extraction script
├── extract_products_async.py      # Asynchronous extraction script
├── comparison_sync_async.py       # Runs both scripts and writes a comparison report
├── comparison_sync_async.md       # Generated benchmark report (created at runtime)
├── requirements.txt               # Python dependencies
└── README.md                      # This file
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

### 4. Create your .env file

```bash
cp .env.example .env
```

Open `.env` and fill in your Mockaroo API key:

```
MOCKAROO_API_KEY=your_key_here
```

The `MOCKAROO_SCHEMA_KEY` is already set to `bb185820` in the provided `.env` file.
Your Mockaroo API key is found at https://mockaroo.com under My Account → API Key.

The `.env` file is loaded automatically when the scripts run — no manual exporting
needed. DummyJSON is a public API and requires no credentials.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DUMMYJSON_HOST` | `https://dummyjson.com` | Base URL of the DummyJSON API |
| `DUMMYJSON_API_KEY` | None | Bearer token for DummyJSON (not required for public use) |
| `MOCKAROO_HOST` | `https://api.mockaroo.com` | Base URL of the Mockaroo API |
| `MOCKAROO_API_KEY` | — | Your Mockaroo API key — **required** |
| `MOCKAROO_SCHEMA_KEY` | `bb185820` | Mockaroo schema key — pre-filled, no change needed |
| `DUMMYJSON_TOTAL_PRODUCTS` | `194` | Total products to extract from DummyJSON |
| `DUMMYJSON_CHUNK_SIZE` | `10` | Records per DummyJSON API call (pagination page size) |
| `MOCKAROO_TOTAL_RECORDS` | `10` | Total records to extract from Mockaroo per run |
| `MOCKAROO_CHUNK_SIZE` | `10` | Records per Mockaroo API call — keep equal to `MOCKAROO_TOTAL_RECORDS` for a single request |
| `RETRY_LIMIT` | `5` | Maximum retries per request on failure or HTTP 429 |
| `CONCURRENCY_LIMIT` | `5` | Async script only: maximum concurrent requests across both sources |
| `RETRY_BACKOFF_BASE` | `2.0` | Exponential backoff base in seconds |
| `RETRY_BACKOFF_MAX` | `60.0` | Maximum backoff ceiling in seconds |

Output paths are defined in `path.py` as hardcoded constants and are not configurable
via environment variables.

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

Comparison (runs both and generates a report):
```bash
python comparison_sync_async.py
```

Output files are written to `data/json/` and logs to `logs/<YYMMDD>/`.

A final log entry is emitted at the end of each run reporting the total execution time
and the number of records extracted from each source, for example:

```json
{"message": "All extractions complete in 3378.9 ms — DummyJSON: 194 records, Mockaroo: 10 records", "total_elapsed_ms": 3378.9, "dummyjson_records": 194, "mockaroo_records": 10}
```

---

## Benchmark Comparison

Running `comparison_sync_async.py` executes both scripts sequentially and writes
`comparison_sync_async.md` with a results table and verdict. Example output:

| Script | Elapsed Time (ms) |
|---|---|
| `extract_products_sync.py` | 4853.77 |
| `extract_products_async.py` | 1577.74 |

Async was faster by **3276.03 ms** (3.08× speedup over sync).

The async script is significantly faster because it fetches all 20 DummyJSON chunks
and the Mockaroo chunk concurrently, while the sync script fetches them one at a time.

---

## Docker

The project can be run entirely inside a Docker container without installing
Python or any dependencies on your host machine.

### Prerequisites

Docker and Docker Compose must be installed. If you are a non-sudo Ubuntu user
and get a permission denied error on the Docker socket, run this once:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### First-time setup

`data/` and `logs/` directories must exist on the host before running so Docker
bind-mounts them correctly. If they do not exist yet:

```bash
mkdir -p data/json logs
```

`comparison_sync_async.md` must also exist as a file before the first run.
If it does not exist yet:

```bash
touch comparison_sync_async.md
```

If the file was already generated by a previous non-Docker run it is ready as-is
and no action is needed.

### Build and run

```bash
docker compose up --build
```

This builds the image and runs `comparison_sync_async.py`, which internally
runs both the sync and async extractors and writes the comparison report.

### Subsequent runs

After the first build, skip `--build` unless you have changed the code:

```bash
docker compose up
```

### Output

All output is written directly to your host project directory:

- `data/json/` — chunked JSON extraction files
- `logs/` — structured JSON log files
- `comparison_sync_async.md` — benchmark comparison report

The container exits automatically when the script finishes.