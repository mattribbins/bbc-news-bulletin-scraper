"""
Configuration Manager for BBC News Bulletin Scraper
Handles loading and validation of application configuration.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigManager:
    """Manages application configuration loading and validation."""

    DEFAULT_CONFIG_PATHS = [
        "./config/config-local.yaml",  # Local development first
        "./config/config.yaml",
        "./config.yaml",
        "/app/config/config.yaml",  # Docker paths last
        "/app/config.yaml",
    ]

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}

    def load_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file."""
        config_file = self._find_config_file()

        if not config_file:
            logging.warning("No configuration file found")
            # Generate a template config file
            template_path = self._generate_template_config()
            if template_path:
                logging.info(f"Generated template configuration file: {template_path}")
                logging.info(
                    "Please edit the configuration file and restart the application"
                )
                return None
            else:
                logging.error("Failed to generate template configuration file")
                return None

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f)

            logging.info(f"Configuration loaded from {config_file}")

            # Validate configuration
            if self._validate_config():
                return self.config
            else:
                logging.error("Configuration validation failed")
                return None

        except yaml.YAMLError as e:
            logging.error(f"Failed to parse YAML config: {e}")
            return None
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            return None

    def _find_config_file(self) -> Optional[Path]:
        """Find the configuration file."""
        if self.config_path:
            config_path = Path(self.config_path)
            if config_path.exists():
                return config_path
            else:
                logging.error(f"Specified config file not found: {self.config_path}")
                return None

        # Try default paths
        for path_str in self.DEFAULT_CONFIG_PATHS:
            path = Path(path_str)
            if path.exists():
                return path

        return None

    def _generate_template_config(self) -> Optional[Path]:
        """Generate a template configuration file."""
        try:
            # Determine best path for template
            template_path = Path("./config/config.yaml")

            # Create config directory if it doesn't exist
            template_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate template content
            template_content = self._get_template_content()

            # Write template file
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(template_content)

            return template_path

        except Exception as e:
            logging.error(f"Failed to generate template config: {e}")
            return None

    def _get_template_content(self) -> str:
        """Get template configuration content."""
        return """# BBC News Bulletin Scraper Configuration Template
# Please customize this configuration for your needs

# Application Settings
app:
  # Timezone for scheduling (default: system local timezone)
  # Uncomment the line below to override system timezone:
  # timezone: "Europe/London"

# BBC Programme Configuration
# Add your BBC programmes here
programmes:
  # Example: BBC Local Radio bulletin
  - name: "BBC Local Update"
    url: "https://www.bbc.co.uk/programmes/PROGRAMME_ID_HERE"
    output_name: "local_update"
    pid_recursive: true
    enabled: true

  # Add more programmes as needed:
  # - name: "Another Bulletin"
  #   url: "https://www.bbc.co.uk/programmes/ANOTHER_ID"
  #   output_name: "another_bulletin"
  #   pid_recursive: true
  #   enabled: false

# Audio Processing Settings
audio:
  # Trim seconds from the start of each bulletin
  trim_start_seconds: 4.0

  # Trim seconds from the end of each bulletin
  # Set to 0 to disable end trimming
  trim_end_seconds: 0.0

  # Audio quality settings (for mp3/m4a)
  quality: "high" # high, std, med, low

  # Output format
  format: "wav" # mp3, m4a, wav

  # Normalise audio loudness to target LUFS (Loudness Units relative to Full Scale)
  # -16 = broadcast standard for most content
  # -23 = EBU R128 standard (European broadcast)
  # -14 = streaming platforms (Spotify, etc.)
  # Set to null to disable normalisation completely
  normalise_lufs: -16

# Scheduling Configuration
scheduler:
  # Download at these minutes past each hour
  # e.g., [5, 35] = 00:05, 00:35, 01:05, 01:35, etc.
  minutes_past_hour: [5, 35]

  # Operating hours (24-hour format)
  start_hour: 6 # Start at 06:00
  end_hour: 22 # End at 22:00

  # Days of week to operate (0=Monday, 6=Sunday)
  days_of_week: [0, 1, 2, 3, 4, 5, 6] # All days

  # Download immediately on startup (regardless of schedule)
  download_on_startup: true

  # Timezone for scheduling (default: system local timezone)
  # timezone: "Europe/London"  # Uncomment to override system timezone

# Output Configuration
output:
  # Base output directory (can be network path)
  # For local development:
  base_path: "./output"
  # For Docker:
  # base_path: "/app/output"
  # For Windows network share:
  # base_path: "\\\\server\\share\\path"

# Download Configuration
download:
  # Temporary download directory
  # For local development:
  temp_path: "./downloads"
  # For Docker:
  # temp_path: "/app/downloads"

  # Maximum concurrent downloads
  max_concurrent: 2

  # Retry settings
  max_retries: 3
  retry_delay_seconds: 60

  # Timeout settings
  timeout_seconds: 600

# Logging Configuration
logging:
  level: "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL
  # For local development:
  file: "./logs/scraper.log"
  # For Docker:
  # file: "/app/logs/scraper.log"
  max_file_size_mb: 100
  backup_count: 5

  # Log retention
  retention_days: 30

# Health Check Configuration (optional)
health:
  enabled: true
  port: 8080
  check_interval_minutes: 5

# get_iplayer specific settings
get_iplayer:
  # Cache directory
  # For local development:
  cache_dir: "./.get_iplayer"
  # For Docker:
  # cache_dir: "/app/.get_iplayer"

  # Time filtering options
  since_hours: 48 # --since option (hours from now to search)
  available_since_hours: 24 # --available-since option (hours programme has been available)

  # Additional command line options
  # extra_options:
  #   - "--flag"

"""

    def _validate_config(self) -> bool:
        """Validate the loaded configuration."""
        try:
            # Check required top-level sections
            required_sections = ["programmes", "audio", "scheduler", "output"]
            for section in required_sections:
                if section not in self.config:
                    logging.error(f"Missing required config section: {section}")
                    return False

            # Validate programmes
            if not self._validate_programmes():
                return False

            # Validate audio settings
            if not self._validate_audio():
                return False

            # Validate scheduler settings
            if not self._validate_scheduler():
                return False

            # Validate output settings
            if not self._validate_output():
                return False

            logging.info("Configuration validation passed")
            return True

        except Exception as e:
            logging.error(f"Configuration validation error: {e}")
            return False

    def _validate_programmes(self) -> bool:
        """Validate programmes configuration."""
        programmes = self.config.get("programmes", [])

        if not programmes:
            logging.error("No programmes configured")
            return False

        for i, programme in enumerate(programmes):
            if not isinstance(programme, dict):
                logging.error(f"Programme {i} is not a dictionary")
                return False

            required_fields = ["name", "url"]
            for field in required_fields:
                if field not in programme:
                    logging.error(f"Programme {i} missing required field: {field}")
                    return False

        return True

    def _validate_audio(self) -> bool:
        """Validate audio configuration."""
        audio = self.config.get("audio", {})

        # Check trim_start_seconds is non-negative number
        trim_start_seconds = audio.get("trim_start_seconds", 0)
        if not isinstance(trim_start_seconds, (int, float)) or trim_start_seconds < 0:
            logging.error("trim_start_seconds must be a non-negative number")
            return False

        # Check trim_end_seconds is non-negative number
        trim_end_seconds = audio.get("trim_end_seconds", 0)
        if not isinstance(trim_end_seconds, (int, float)) or trim_end_seconds < 0:
            logging.error("trim_end_seconds must be a non-negative number")
            return False

        # Check normalise_lufs is valid (number or None/False)
        normalise_lufs = audio.get("normalise_lufs")
        if normalise_lufs is not None and not isinstance(normalise_lufs, (int, float)):
            # Check for legacy boolean setting
            legacy_bool = audio.get("normalise") or audio.get("normalize")
            if legacy_bool is None or not isinstance(legacy_bool, bool):
                logging.error("normalise_lufs must be a number or null")
                return False

        # Validate LUFS range (typical broadcast range is -14 to -31 LUFS)
        if normalise_lufs is not None and (
            normalise_lufs > -14 or normalise_lufs < -31
        ):
            logging.warning(
                f"normalise_lufs value {normalise_lufs} is outside typical broadcast range (-14 to -31 LUFS)"
            )

        # Check quality is valid
        valid_qualities = ["high", "std", "med", "low"]
        quality = audio.get("quality", "high")
        if quality not in valid_qualities:
            logging.error(
                f"Invalid audio quality: {quality}. Must be one of {valid_qualities}"
            )
            return False

        # Check format is valid
        valid_formats = ["mp3", "m4a", "wav"]
        format_type = audio.get("format", "mp3")
        if format_type not in valid_formats:
            logging.error(
                f"Invalid audio format: {format_type}. Must be one of {valid_formats}"
            )
            return False

        return True

    def _validate_scheduler(self) -> bool:
        """Validate scheduler configuration."""
        scheduler = self.config.get("scheduler", {})

        # Check minutes_past_hour
        minutes = scheduler.get("minutes_past_hour", [])
        if not isinstance(minutes, list) or not minutes:
            logging.error("minutes_past_hour must be a non-empty list")
            return False

        for minute in minutes:
            if not isinstance(minute, int) or minute < 0 or minute >= 60:
                logging.error(f"Invalid minute value: {minute}. Must be 0-59")
                return False

        # Check hour ranges
        start_hour = scheduler.get("start_hour", 0)
        end_hour = scheduler.get("end_hour", 23)

        if not 0 <= start_hour <= 23 or not 0 <= end_hour <= 23:
            logging.error("start_hour and end_hour must be 0-23")
            return False

        return True

    def _validate_output(self) -> bool:
        """Validate output configuration."""
        output = self.config.get("output", {})

        # Check base_path exists
        if "base_path" not in output:
            logging.error("output.base_path is required")
            return False

        return True

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def has_valid_config(self) -> bool:
        """Check if a valid configuration file exists."""
        config_file = self._find_config_file()
        return config_file is not None
