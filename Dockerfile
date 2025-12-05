# BBC News Bulletin Scraper - Alpine Version (Default)
FROM python:3.11-alpine

# Install system dependencies
RUN apk add --no-cache \
    # Core dependencies
    curl \
    wget \
    perl \
    # Perl modules required by get_iplayer
    perl-libwww \
    perl-xml-libxml \
    perl-mojolicious \
    perl-cgi \
    perl-lwp-protocol-https \
    perl-html-parser \
    perl-uri \
    perl-file-slurp \
    perl-json \
    # Audio processing (much smaller in Alpine)
    ffmpeg \
    # Utilities
    dcron \
    rsync \
    bash

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
RUN adduser -D -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port for health checks (optional)
EXPOSE 8080

# Default command
CMD ["python", "src/main.py"]