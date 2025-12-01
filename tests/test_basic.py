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

        config = {
            "audio": {
                "trim_start_seconds": 5,
                "trim_end_seconds": 2,
                "normalise_lufs": -16,
                "quality": "high",
            }
        }
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

    def test_normalise_lufs_processing(self):
        """Test LUFS normalisation functionality."""
        from audio_processor import AudioProcessor

        # Test different normalise_lufs values
        test_cases = [
            (None, False),  # Disabled
            (-16, True),  # Standard broadcast
            (-23, True),  # EBU R128
            (-14, True),  # Streaming
        ]

        for lufs_value, should_have_loudnorm in test_cases:
            config = {"audio": {"normalise_lufs": lufs_value, "format": "wav"}}
            processor = AudioProcessor(config)

            # Build command (with fake paths)
            cmd = processor._build_ffmpeg_command(
                Path("/fake/input.wav"),
                Path("/fake/output.wav"),
                trim_start_seconds=0,
                trim_end_seconds=0,
                normalise_lufs=lufs_value,
                output_format="wav",
            )

            # Check for loudnorm filter
            has_loudnorm = any("loudnorm" in str(arg) for arg in cmd)
            assert (
                has_loudnorm == should_have_loudnorm
            ), f"LUFS {lufs_value} loudnorm check failed"

            # Check specific loudnorm parameters when enabled
            if should_have_loudnorm:
                loudnorm_filter = next(
                    (arg for arg in cmd if "loudnorm" in str(arg)), None
                )
                assert (
                    f"I={lufs_value}" in loudnorm_filter
                ), f"LUFS target {lufs_value} not found in filter"

    def test_legacy_normalise_fallback(self):
        """Test legacy normalise boolean fallback."""
        from audio_processor import AudioProcessor

        # Test legacy boolean settings
        test_cases = [
            ({"normalise": True}, -16),  # British spelling
            ({"normalize": True}, -16),  # American spelling
            ({"normalise": False}, None),  # Disabled British
            ({"normalize": False}, None),  # Disabled American
        ]

        for legacy_config, expected_lufs in test_cases:
            config = {"audio": {**legacy_config, "format": "wav"}}
            processor = AudioProcessor(config)

            # Build command
            cmd = processor._build_ffmpeg_command(
                Path("/fake/input.wav"),
                Path("/fake/output.wav"),
                trim_start_seconds=0,
                trim_end_seconds=0,
                normalise_lufs=expected_lufs,
                output_format="wav",
            )

            # Check for loudnorm presence
            has_loudnorm = any("loudnorm" in str(arg) for arg in cmd)
            should_have_loudnorm = expected_lufs is not None
            assert (
                has_loudnorm == should_have_loudnorm
            ), f"Legacy {legacy_config} fallback failed"

    def test_trim_end_functionality(self):
        """Test trim_end_seconds functionality."""
        from unittest.mock import Mock

        from audio_processor import AudioProcessor

        config = {"audio": {"trim_end_seconds": 2.0, "format": "wav"}}
        processor = AudioProcessor(config)

        # Mock get_duration to return a known value
        original_get_duration = processor.get_duration
        processor.get_duration = Mock(return_value=60.0)  # 60 second file

        try:
            # Build command with trimming
            cmd = processor._build_ffmpeg_command(
                Path("/fake/input.wav"),
                Path("/fake/output.wav"),
                trim_start_seconds=4.0,
                trim_end_seconds=2.0,
                normalise_lufs=None,
                output_format="wav",
            )

            # Check for duration limiting (-t parameter)
            has_duration_limit = "-t" in cmd
            assert has_duration_limit, "Duration limit not found for end trimming"

            # Check calculated duration: 60 - 4 (start) - 2 (end) = 54 seconds
            if "-t" in cmd:
                t_index = cmd.index("-t")
                duration = cmd[t_index + 1]
                assert duration == "54.0", f"Expected duration 54.0, got {duration}"

        finally:
            # Restore original method
            processor.get_duration = original_get_duration

    def test_trim_end_edge_cases(self, caplog):
        """Test trim_end_seconds edge cases."""
        import logging
        from unittest.mock import Mock

        from audio_processor import AudioProcessor

        config = {"audio": {"trim_end_seconds": 2.0, "format": "wav"}}
        processor = AudioProcessor(config)

        # Test case 1: Cannot determine duration
        processor.get_duration = Mock(return_value=None)

        with caplog.at_level(logging.WARNING):
            cmd = processor._build_ffmpeg_command(
                Path("/fake/input.wav"),
                Path("/fake/output.wav"),
                trim_start_seconds=0,
                trim_end_seconds=2.0,
                normalise_lufs=None,
                output_format="wav",
            )

            # Should not have -t parameter when duration unknown
            assert (
                "-t" not in cmd
            ), "Duration limit should not be set when duration unknown"

        # Should log warning
        assert any(
            "Could not determine duration" in record.message
            for record in caplog.records
        )

        # Clear logs for next test
        caplog.clear()

        # Test case 2: Invalid target duration (trim more than total)
        processor.get_duration = Mock(return_value=5.0)  # 5 second file

        with caplog.at_level(logging.WARNING):
            cmd = processor._build_ffmpeg_command(
                Path("/fake/input.wav"),
                Path("/fake/output.wav"),
                trim_start_seconds=4.0,  # Start trim
                trim_end_seconds=2.0,  # End trim (4+2=6 > 5 total)
                normalise_lufs=None,
                output_format="wav",
            )

            # Should not have -t parameter when target duration invalid
            assert (
                "-t" not in cmd
            ), "Duration limit should not be set when target duration invalid"

        # Should log warning about invalid duration
        assert any(
            "Calculated target duration" in record.message for record in caplog.records
        )


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
