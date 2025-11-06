FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY production-services/project-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities (authentication and logging)
COPY shared /app/shared

# Copy application
COPY production-services/project-service/main.py .

# Expose port
EXPOSE 8011

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8011/health', timeout=5)"

# Run service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
