FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY project-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities (authentication and logging)
COPY ../shared /app/shared

# Copy application
COPY project-service/main.py .

# Expose port
EXPOSE 8011

# Run service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
