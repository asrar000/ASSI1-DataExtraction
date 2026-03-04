# DummyJSON + Mockaroo Product Extractor

## Description

This project contains two Python scripts that extract product data from two sources:

- DummyJSON (https://dummyjson.com/products) — a public product catalogue API
- Mockaroo (https://api.mockaroo.com/api/generate.json) — a schema-based data generation API

Both sources are extracted in the same script run and written to chunked JSON files on disk.

| Script | Description |
|---|---|
| `extract_products_sync.py` | Synchronous extractor using the `requests` library. Fetches DummyJSON first, then Mockaroo, one chunk at a time. |
| `extract_products_async.py` | Asynchronous extractor using `aiohttp` and `asyncio`. Fetches chunks from both sources concurrently, bounded by `CONCURRENCY_LIMIT`. |

Both scripts:

- Write DummyJSON output to `data/json/dummyjson_<chunk_number>_<date>_<time>.json`
- Write Mockaroo output to `data/json/mockaroo_<chunk_number>_<date>_<time>.json`
- Write structured JSON logs to `logs/<YYMMDD>/<script_name>_<YYMMDD>_<HHMMSS>.json`
- Apply exponential backoff on retryable errors (HTTP 429, 5xx, network failures)
- Validate that each chunk contains exactly the expected number of records
- Never write the Mockaroo API key to logs
- Emit a final log entry reporting the total execution time for both sources

---

## Mockaroo Schema

The Mockaroo schema used in this project is designed to mirror the flat fields
of a DummyJSON product record as closely as possible.

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

## Project Structure

```
.
├── data/
│   └── json/                   # Extracted data files (generated at runtime)
├── logs/                       # JSON log files (generated at runtime)
├── .env.example                # Template showing all required environment variables
├── config.py                   # Central configuration — reads from .env automatically
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

### 4. Create your .env file

```bash
cp .env.example .env
```

Open `.env` and fill in the two required values:

```
MOCKAROO_API_KEY=your_key_here
MOCKAROO_SCHEMA_KEY=your_schema_key_here
```

Your Mockaroo API key is found at https://mockaroo.com under My Account.
Your schema key is on the schema detail page in your Mockaroo account.

The `.env` file is loaded automatically when the scripts run — no manual
exporting needed. DummyJSON is a public API and requires no credentials.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DUMMYJSON_HOST` | `https://dummyjson.com` | Base URL of the DummyJSON API |
| `DUMMYJSON_API_KEY` | None | Bearer token for DummyJSON (not required for public use) |
| `MOCKAROO_HOST` | `https://api.mockaroo.com` | Base URL of the Mockaroo API |
| `MOCKAROO_API_KEY` | None | Your Mockaroo API key — required |
| `MOCKAROO_SCHEMA_KEY` | None | Mockaroo schema key to generate data from — required |
| `DUMMYJSON_TOTAL_PRODUCTS` | `194` | Total products to extract from DummyJSON |
| `MOCKAROO_TOTAL_RECORDS` | `100` | Total records to extract from Mockaroo |
| `CHUNK_SIZE` | `10` | Number of records per API call (applies to both sources) |
| `RETRY_LIMIT` | `5` | Maximum retries per request on failure or HTTP 429 |
| `CONCURRENCY_LIMIT` | `5` | Async script only: maximum concurrent requests across both sources |
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