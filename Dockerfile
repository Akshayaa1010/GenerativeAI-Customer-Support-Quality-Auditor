# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — install dependencies in a clean layer
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System libraries needed to build psycopg2 and spaCy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime — lean final image
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Make `import backend.xxx` work from /app root under Gunicorn
    PYTHONPATH=/app

WORKDIR /app

# Only libpq is needed at runtime (not the dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Cloud Run writes uploaded files to /tmp (ephemeral, instance-local)
# Audio files are processed then deleted immediately — /tmp is sufficient
RUN mkdir -p /tmp/uploads

# Cloud Run injects $PORT at runtime (default 8080)
EXPOSE 8080

# ─────────────────────────────────────────────────────────────────────────────
# Gunicorn — production WSGI server
#
# --workers 2        : 2 processes (Cloud Run min memory 512MB handles this)
# --threads 4        : 4 threads per worker for I/O-bound LLM calls
# --timeout 300      : audio transcription + scoring can take 2-3 minutes
# --preload          : import app once before forking — catches startup errors
# --access-logfile - : log to stdout (Cloud Run captures stdout → Cloud Logging)
# --error-logfile -  : log errors to stdout as well
# ─────────────────────────────────────────────────────────────────────────────
CMD exec gunicorn \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 2 \
    --threads 4 \
    --timeout 300 \
    --preload \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    app:app
