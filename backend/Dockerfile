# ============================================================================
# STAGE 1: Builder - Install dependencies
# ============================================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# STAGE 2: Runtime - Minimal image with only runtime dependencies
# ============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install only runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY app/ ./app/
COPY run_scheduler.py ./
COPY alembic.ini ./
COPY alembic/ ./alembic/

# Create necessary directories and set permissions
RUN mkdir -p logs models && \
    groupadd -r appuser && \
    useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

# Switch to non-root user for security
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
