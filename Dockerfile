FROM python:3.11-slim

LABEL maintainer="kyeongyeon.kim"
LABEL description="QA Data Pipeline for regulatory data validation"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/
COPY main.py .

# Create data directories
RUN mkdir -p data/input data/output

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
