# Use a slim Python base image
FROM python:3.10-slim

# Set environment variables for non-interactive setup
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies: cron and a headless browser (Chromium)
RUN apt-get update && apt-get install -y \
    cron \
    chromium \
    chromium-driver \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Set up the application directory
WORKDIR /app

# Copy uv lock file and pyproject.toml and install Python packages using uv
COPY uv.lock pyproject.toml .
RUN uv sync

# Copy the application code
COPY ./ ./

# Create a directory for the output ICS files
RUN mkdir -p /app/output && chown -R www-data:www-data /app/output

# Start the cron service in the foreground
CMD ["uv", "run", "amazon_orders.py"]
