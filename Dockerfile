# Lightweight Python image
FROM python:3.10-slim

# Prevent python buffering
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies needed for Playwright
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Copy project files
COPY . .

# Install Playwright browsers
RUN playwright install --with-deps

# Start Streamlit using Railway PORT
CMD streamlit run frontend/dashboard.py --server.port=$PORT --server.address=0.0.0.0
