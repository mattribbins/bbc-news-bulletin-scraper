"""
Tests for BBC News Bulletin Scraper
Basic smoke tests to validate the application structure.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestConfigManager:
    """Test configuration management."""

    def test_config_manager_import(self):
        """Test that ConfigManager can be imported."""
        from config_manager import ConfigManager

        config_manager = ConfigManager()
        assert config_manager is not None

    def test_config_validation_structure(self):
        """Test configuration validation methods exist."""
        from config_manager import ConfigManager

        config_manager = ConfigManager()
        assert hasattr(config_manager, "_validate_config")
        assert hasattr(config_manager, "_validate_programmes")


class TestAudioProcessor:
    """Test audio processing functionality."""

    def test_audio_processor_import(self):
        """Test that AudioProcessor can be imported."""
        from audio_processor import AudioProcessor

        config = {"audio": {"trim_start_seconds": 5, "quality": "high"}}
        processor = AudioProcessor(config)
        assert processor is not None

    def test_audio_quality_mapping(self):
        """Test audio quality mapping functions."""
        from audio_processor import AudioProcessor

        config = {"audio": {"quality": "high"}}
        processor = AudioProcessor(config)

        # Test that the processor has the quality mapping method
        assert hasattr(processor, "_get_mp3_quality")
        # Test that it returns a valid quality string
        mp3_quality = processor._get_mp3_quality()  # pylint: disable=protected-access
        assert mp3_quality in ["320k", "192k", "128k", "96k"]


class TestScheduler:
    """Test scheduling functionality."""

    def test_scheduler_import(self):
        """Test that BulletinScheduler can be imported."""
        from scheduler import BulletinScheduler

        config = {"scheduler": {"minutes_past_hour": [5]}}
        scraper_mock = MagicMock()

        scheduler = BulletinScheduler(config, scraper_mock)
        assert scheduler is not None

    def test_scheduler_status(self):
        """Test scheduler status functionality."""
        from scheduler import BulletinScheduler

        config = {"scheduler": {"minutes_past_hour": [5]}}
        scraper_mock = MagicMock()

        scheduler = BulletinScheduler(config, scraper_mock)
        status = scheduler.get_status()

        assert "running" in status
        assert "total_runs" in status
        assert "next_jobs" in status


class TestHealthMonitor:
    """Test health monitoring functionality."""

    def test_health_monitor_import(self):
        """Test that HealthMonitor can be imported."""
        from health_monitor import HealthMonitor

        config = {"health": {"enabled": False}}  # Disable HTTP server for test
        monitor = HealthMonitor(config)
        assert monitor is not None

    def test_health_status_structure(self):
        """Test health status response structure."""
        from health_monitor import HealthMonitor

        config = {"health": {"enabled": False}}
        monitor = HealthMonitor(config)

        status = monitor.get_health_status()

        assert "healthy" in status
        assert "timestamp" in status
        assert "checks" in status
        assert isinstance(status["checks"], list)


class TestApplication:
    """Test main application functionality."""

    def test_main_application_import(self):
        """Test that main application can be imported."""
        from main import BBCBulletinScraper

        app = BBCBulletinScraper()
        assert app is not None
        assert hasattr(app, "initialize")
        assert hasattr(app, "shutdown")


def test_package_structure():
    """Test that all required modules are available."""
    required_modules = [
        "main",
        "config_manager",
        "scraper",
        "audio_processor",
        "scheduler",
        "health_monitor",
    ]

    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError as e:
            pytest.fail(f"Required module {module_name} could not be imported: {e}")


def test_configuration_file_exists():
    """Test that configuration file template exists."""
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    assert config_path.exists(), "Configuration template file should exist"


if __name__ == "__main__":
    pytest.main([__file__])
