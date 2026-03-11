# Use official Playwright image
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Prevent python buffering and bytecode
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python packages and spacy model
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Copy project files
COPY . .

# Ensure chromium is installed
RUN playwright install chromium

# Start Streamlit using Railway PORT (using sh -c to expand environment variables)
CMD ["sh", "-c", "streamlit run frontend/dashboard.py --server.port=${PORT} --server.address=0.0.0.0"]
