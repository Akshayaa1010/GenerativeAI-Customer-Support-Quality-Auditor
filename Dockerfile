# Use official slim Python image
FROM python:3.10-slim

# Prevent Python from writing bytecode and buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install required system build packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install Python dependencies & SpaCy English NLP model
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Copy codebase into container
COPY . .

# Ensure data directories exist
RUN mkdir -p data/uploads data/user_data

# Expose port (Cloud Run injects $PORT at runtime — default 8080)
EXPOSE 8080

# Launch with Gunicorn — uses Cloud Run-injected $PORT (fallback 8080)
# 1 worker + 8 threads: reduces memory vs multi-worker while keeping I/O concurrency
# Shell exec form ensures gunicorn receives OS signals for graceful shutdown
CMD exec gunicorn \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 1 \
    --threads 8 \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    app:app
