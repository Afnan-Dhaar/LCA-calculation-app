# ===========================================================================
# Production Dockerfile for Brightway LCA Studio & PCF API
# ===========================================================================

FROM python:3.12-slim AS runtime

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    BRIGHTWAY2_DIR=/app/brightway_data

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY api.py brightway_engine.py db.py product_model.py excel_importer.py saved_products.json ./
COPY product_lca_template.xlsx ./

# Create data directories and create non-root user
RUN mkdir -p /app/brightway_data && \
    useradd -u 1001 -m lcauser && \
    chown -R lcauser:lcauser /app

USER lcauser

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI server via Uvicorn
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
