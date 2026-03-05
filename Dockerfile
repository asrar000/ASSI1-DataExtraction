# Dockerfile
# ---------------------------------------------------------------------------
# Runs comparison_sync_async.py which internally runs both sync and async
# extraction scripts and writes comparison_sync_async.md on completion.
#
# Built for a non-sudo Ubuntu user — no root privileges assumed on the host.
# ---------------------------------------------------------------------------

FROM python:3.12-slim

# Create a non-root user to run the application
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install dependencies as root before switching user
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY config.py path.py \
     extract_products_sync.py \
     extract_products_async.py \
     comparison_sync_async.py \
     ./

# Create output directories and hand ownership to appuser
RUN mkdir -p data/json logs && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# data/json and logs are mounted as volumes from the host at runtime
VOLUME ["/app/data/json", "/app/logs"]

CMD ["python", "comparison_sync_async.py"]