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
        "/app/config/config.yaml",     # Docker paths last
        "/app/config.yaml",
    ]

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = {}

    def load_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file."""
        config_file = self._find_config_file()

        if not config_file:
            logging.error("No configuration file found")
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
        trim_seconds = audio.get("trim_start_seconds", 0)
        if not isinstance(trim_seconds, (int, float)) or trim_seconds < 0:
            logging.error("trim_start_seconds must be a non-negative number")
            return False

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
