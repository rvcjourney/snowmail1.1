# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Add Gunicorn for production serving
RUN pip install --no-cache-dir gunicorn

# Install Playwright OS dependencies as root
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Change ownership to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user BEFORE installing browsers so cache is under /home/appuser
USER appuser

# Install Playwright Chromium as appuser (creates cache under /home/appuser/.cache/ms-playwright)
RUN playwright install chromium

# Expose port 3017
EXPOSE 3017

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3017/ || exit 1

# Run the application
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "-b", "0.0.0.0:3017", "--timeout", "150", "--graceful-timeout", "150", "--access-logfile", "-", "finalcode:app"]
