# Use official Playwright image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Prevent python buffering
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python packages and spacy model
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Copy project files
COPY . .

# Install Playwright browsers (already includes deps in this image)
RUN playwright install chromium

# Start Streamlit using Railway PORT
CMD streamlit run frontend/dashboard.py --server.port=$PORT --server.address=0.0.0.0
