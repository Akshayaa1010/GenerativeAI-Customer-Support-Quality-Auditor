# Use a slim Python image to reduce size
FROM python:3.10-slim

# Prevent python buffering and bytecode
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && pip install --no-cache-dir playwright && \
    playwright install-deps chromium && \
    playwright install chromium && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python packages and spacy model
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Copy project files
COPY . .

# Start Streamlit using Railway PORT
CMD streamlit run frontend/dashboard.py --server.port ${PORT:-8501} --server.address 0.0.0.0
