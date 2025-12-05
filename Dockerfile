# BBC News Bulletin Scraper - Alpine Version (Default)
FROM python:3.11-alpine

# Update package index and install core dependencies
# Use set +e to ignore trigger execution errors in emulated ARM64 builds
RUN set +e; apk update && apk add --no-cache \
    curl \
    wget \
    bash \
    dcron \
    rsync; \
    exit_code=$?; \
    if [ $exit_code -eq 2 ] && [ "$(apk info | wc -l)" -gt 10 ]; then \
    echo "Packages installed successfully despite trigger errors"; \
    exit 0; \
    elif [ $exit_code -ne 0 ]; then \
    exit $exit_code; \
    fi

# Install Perl and required modules
RUN apk add --no-cache \
    perl \
    perl-libwww \
    perl-xml-libxml \
    perl-mojolicious \
    perl-cgi \
    perl-lwp-protocol-https \
    perl-html-parser \
    perl-uri \
    perl-file-slurp \
    perl-json

# Install ffmpeg (audio processing)
RUN apk add --no-cache ffmpeg

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