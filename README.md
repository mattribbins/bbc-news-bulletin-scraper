# BBC News Bulletin Scraper

Python application to automatically download and content manage BBC News radio bulletins. Acts as a fancy automated wrapper to `get_iplayer`.

The main use case for this application is for community radio stations which have an agreeement with the BBC to download and re-broadcast BBC Local Radio bulletins on their radio station.

This application is provided as-is with no warranty or liability for misuse.

## Features

- **Automated Schedule**: Downloads bulletins at configurable days and times
- **Audio Processing**: Trims audio at the start of the bulletin
- **Format Conversion**: Converts audio to desired format (MP3, M4A, WAV)
- **Audio Normalization**: Optional loudness normalization
- **Flexible Output**: Supports local paths and in theory network shares (Windows/SMB)
- **Container-Based**: Run the app in your container platform of choice (Docker/Podman)

## Dependencies

### Core Requirements

- **Python 3.11+**: Core runtime environment
- **get_iplayer**: Open source tool to download audio from BBC iPlayer/Sounds
  - **macOS**: `brew install get_iplayer`
  - **Ubuntu/Debian**: `apt-get install get-iplayer`
  - **Manual Installation**: See [get_iplayer wiki](https://github.com/get-iplayer/get_iplayer/wiki/unixpkg)
- **ffmpeg**: Audio processing and format conversion
  - **macOS**: `brew install ffmpeg`
  - **Ubuntu/Debian**: `apt-get install ffmpeg`

### Container Installation (Recommended)

The Docker container automatically installs all dependencies including `get_iplayer` and `ffmpeg`. No manual dependency installation required.

### Local Development Setup

For local development, ensure you have the core requirements installed:

```bash
# macOS with Homebrew
brew install get_iplayer ffmpeg

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install get-iplayer ffmpeg

# Verify installation
get_iplayer --help
ffmpeg -version
```

## Quick Start

### Using the Quick Start Script

```bash
# Make the script executable and run
chmod +x start.sh
./start.sh
```

### Manual Setup with Make

```bash
# Quick start (build and run)
make start

# Or step by step
make docker-build
make docker-run

# View logs
make docker-logs

# Stop
make docker-stop
```

### Manual Setup with Docker Compose

```bash
# Start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
curl http://localhost:8080/health
```

## Configuration

### Basic Configuration

The main configuration is in `config/config.yaml`. The example config file explains all the settings.

### Network Share Setup (Windows)

For Windows network shares, update the docker-compose.yml:

```yaml
volumes:
  - type: bind
    source: \\\\audio-server\\Import\\News
    target: /app/output
```

## Programme Configuration

Add BBC programmes in the configuration:

```yaml
programmes:
  - name: "BBC Somerset Update"
    url: "https://www.bbc.co.uk/programmes/p08dy4zh"
    output_name: "somerset_update"
    pid_recursive: true
    enabled: true
```

## Monitoring and Health Checks

### Health Check Endpoints

- `http://localhost:8080/health` - Basic health status
- `http://localhost:8080/status` - Detailed application status  
- `http://localhost:8080/metrics` - Application metrics

### Health Check Response

```json
{
  "healthy": true,
  "timestamp": "2024-10-30T15:30:00Z",
  "uptime_seconds": 3600,
  "checks": [
    {
      "name": "scheduler",
      "status": "pass",
      "message": "Scheduler is running"
    },
    {
      "name": "disk_space", 
      "status": "pass",
      "message": "Disk space OK: 45.2GB (75.3%) free"
    }
  ]
}
```

## Logging

Logs are written to `/app/logs/scraper.log` with configurable levels:

- Application events and errors
- Download progress and results
- Audio processing status
- Scheduler execution
- Health check results

## Management Commands

### Docker Compose Commands

```bash
# Start application
docker-compose up -d

# Stop application  
docker-compose down

# View logs
docker-compose logs -f bbc-news-bull-scraper

# Restart application
docker-compose restart bbc-news-bull-scraper

# Update configuration (restart required)
docker-compose down
# Edit config/config.yaml
docker-compose up -d
```

### Manual Operations

```bash
# Access container shell
docker-compose exec bbc-news-bull-scraper bash

# Trigger manual download
curl -X POST http://localhost:8080/trigger-download

# Check configuration
docker-compose exec bbc-news-bull-scraper python -c "from src.config_manager import ConfigManager; print(ConfigManager().load_config())"
```

## Development

### Setup Development Environment

```bash
# Install with development dependencies
make install-dev

# Setup pre-commit hooks
make setup-dev

# Run all checks
make check
```

### Development Commands

```bash
# Format code
make format

# Run linters
make lint

# Run tests
make test

# Run all checks (format, lint, test)
make check

# Build package
make build

# Clean build artifacts
make clean
```

### Testing

```bash
# Run tests with coverage
make test

# Run specific test
python -m pytest tests/test_basic.py -v
```

## Support

This is provided as-is with no support or warranty. If you encounter issues:

1. Check application logs for errors: `docker-compose logs -f`
2. Verify configuration: Review `config/config.yaml`  
3. Test health endpoints: `curl http://localhost:8080/health`

## License

This project is licensed under the MIT License - see the LICENSE file for details.
