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

# Run as a non-root user (Hugging Face Spaces uses uid 1000).
# Uploaded audio goes to the system temp folder and is deleted after each audit.
RUN useradd --uid 1000 --create-home appuser && chown -R appuser /app
USER appuser

# Cloud Run injects $PORT; Hugging Face Spaces uses app_port 8080 from the Space README.
EXPOSE 8080

# ─────────────────────────────────────────────────────────────────────────────
# Gunicorn — production WSGI server
#
# --workers 1        : one process keeps memory low (spaCy is loaded per process).
#                      Audit progress is stored in the database, so more workers
#                      or instances are safe if you need them.
# --threads 8        : 8 threads for I/O-bound LLM calls
# --timeout 300      : audio transcription + scoring can take 2-3 minutes
# --preload          : import app once before forking — catches startup errors
# --access-logfile - : log to stdout (Cloud Run captures stdout → Cloud Logging)
# --error-logfile -  : log errors to stdout as well
# ─────────────────────────────────────────────────────────────────────────────
CMD exec gunicorn \
    --bind 0.0.0.0:${PORT:-8080} \
    --workers 1 \
    --threads 8 \
    --timeout 300 \
    --preload \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    app:app
