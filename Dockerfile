# Use official slim Python image
FROM python:3.10-slim

# Prevent Python from writing bytecode and buffer stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

# Install required system build packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install Python dependencies & SpaCy English NLP model
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Copy codebase into container
COPY . .

# Ensure data directories exist
RUN mkdir -p data/uploads data/user_data

# Expose container port
EXPOSE 7860

# Launch application using Gunicorn WSGI server
CMD exec gunicorn --bind 0.0.0.0:${PORT:-7860} --workers 2 --threads 4 app:app
