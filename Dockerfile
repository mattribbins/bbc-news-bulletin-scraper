# BBC News Bulletin Scraper
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Core dependencies
    curl \
    wget \
    perl \
    # Perl modules required by get_iplayer
    libwww-perl \
    libxml-libxml-perl \
    libmojolicious-perl \
    libcgi-pm-perl \
    liblwp-protocol-https-perl \
    libhtml-parser-perl \
    liburi-perl \
    libfile-slurp-perl \
    libjson-perl \
    # Audio processing
    ffmpeg \
    atomicparsley \
    # Utilities
    cron \
    rsync \
    && rm -rf /var/lib/apt/lists/*

# Install get_iplayer
RUN curl -fsSL https://raw.githubusercontent.com/get-iplayer/get_iplayer/master/get_iplayer -o /usr/local/bin/get_iplayer \
    && chmod +x /usr/local/bin/get_iplayer \
    # Verify get_iplayer installation
    && get_iplayer --help > /dev/null 2>&1 || echo "get_iplayer installed but may need additional setup"

# Set working directory
WORKDIR /app

# Copy pyproject.toml and install dependencies
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir .

# Copy application files
COPY src/ ./src/
COPY config/ ./config/

# Create necessary directories
RUN mkdir -p /app/downloads /app/output /app/logs /app/.get_iplayer

# Set environment variables
ENV PYTHONPATH=/app
ENV TZ=Europe/London

# Create non-root user for security
RUN useradd -r -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port for health checks (optional)
EXPOSE 8080

# Default command
CMD ["python", "src/main.py"]