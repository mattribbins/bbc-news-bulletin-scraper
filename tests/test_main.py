"""Tests for main application module."""

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _valid_config() -> dict:
    return {
        "programmes": [
            {
                "name": "BBC Local Update",
                "url": "https://www.bbc.co.uk/programmes/p08dy4zh",
            }
        ],
        "audio": {
            "trim_start_seconds": 1,
            "trim_end_seconds": 0,
            "quality": "high",
            "format": "wav",
            "normalise_lufs": -16,
        },
        "scheduler": {
            "minutes_past_hour": [5, 35],
            "start_hour": 6,
            "end_hour": 22,
            "days_of_week": [0, 1, 2, 3, 4],
            "download_on_startup": True,
        },
        "output": {"base_path": "./output"},
    }


class TestApplication:
    """Test main application functionality."""

    def test_main_application_import(self):
        """Test that main application can be imported."""
        from main import BBCBulletinScraper

        app = BBCBulletinScraper()
        assert app is not None
        assert hasattr(app, "initialize")
        assert hasattr(app, "shutdown")

    def test_programme_specific_trim_settings(self):
        """Test per-programme trim settings override global settings."""
        import tempfile

        from audio_processor import AudioProcessor

        # Global config with default trim settings
        config = {
            "audio": {
                "trim_start_seconds": 4.0,
                "trim_end_seconds": 1.0,
                "format": "wav",
            }
        }
        processor = AudioProcessor(config)

        # Programme-specific config that overrides global settings
        programme_config = {
            "trim_start_seconds": 6.0,
            "trim_end_seconds": 2.5,
            "name": "Test Programme",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = Path(temp_dir) / "input.m4a"
            output_file = Path(temp_dir) / "output.wav"

            # Create a fake input file
            input_file.write_text("fake audio data")

            # Mock subprocess.run to capture the actual command that would be executed
            with (
                patch("subprocess.run") as mock_run,
                patch("os.open") as mock_open,
                patch("os.close"),
                patch("pathlib.Path.replace") as mock_replace,
                patch.object(processor, "get_duration", return_value=60.0),
            ):

                # Mock successful ffmpeg execution
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_run.return_value = mock_result

                # Mock file lock
                mock_open.return_value = 123

                # Mock the atomic file move operation
                mock_replace.return_value = None

                # Call process_audio with programme_config to test the override logic
                success = processor.process_audio(
                    input_file, output_file, programme_config
                )

                # Verify the method succeeded
                assert success is True

                # Verify subprocess was called
                mock_run.assert_called_once()

                # Get the actual command that was passed to subprocess.run
                actual_cmd = mock_run.call_args[0][0]

                # Verify that programme-specific trim values were used (not global ones)

                # Check start trim: should be 6.0 (programme) not 4.0 (global)
                assert "-ss" in actual_cmd
                ss_index = actual_cmd.index("-ss")
                assert (
                    float(actual_cmd[ss_index + 1]) == 6.0
                ), f"Expected programme trim_start_seconds (6.0), got {actual_cmd[ss_index + 1]}"

                # Check end trim: calculated duration should be 60 - 6.0 - 2.5 = 51.5
                # (programme values: start=6.0, end=2.5, not global start=4.0, end=1.0)
                assert "-t" in actual_cmd
                t_index = actual_cmd.index("-t")
                assert (
                    float(actual_cmd[t_index + 1]) == 51.5
                ), f"Expected programme-calculated duration (51.5), got {actual_cmd[t_index + 1]}"

                # Additional verification: test without programme config to ensure global values work

            # Test that global config is used when no programme config is provided
            with (
                patch("subprocess.run") as mock_run_global,
                patch("os.open") as mock_open_global,
                patch("os.close"),
                patch("pathlib.Path.replace") as mock_replace_global,
                patch.object(processor, "get_duration", return_value=60.0),
            ):

                mock_result_global = MagicMock()
                mock_result_global.returncode = 0
                mock_run_global.return_value = mock_result_global
                mock_open_global.return_value = 124

                # Mock the atomic file move operation
                mock_replace_global.return_value = None

                # Call process_audio WITHOUT programme_config
                success_global = processor.process_audio(input_file, output_file, None)

                assert success_global is True
                mock_run_global.assert_called_once()

                # Get the command for global config
                global_cmd = mock_run_global.call_args[0][0]

                # Should use global values: start=4.0, end=1.0
                # Calculated duration: 60 - 4.0 - 1.0 = 55.0
                ss_index_global = global_cmd.index("-ss")
                assert (
                    float(global_cmd[ss_index_global + 1]) == 4.0
                ), f"Expected global trim_start_seconds (4.0), got {global_cmd[ss_index_global + 1]}"

                t_index_global = global_cmd.index("-t")
                assert (
                    float(global_cmd[t_index_global + 1]) == 55.0
                ), f"Expected global-calculated duration (55.0), got {global_cmd[t_index_global + 1]}"

    def test_initialize_returns_false_when_config_missing(self):
        from main import BBCBulletinScraper

        with (
            patch("main.signal.signal"),
            patch("main.ConfigManager") as mock_config_manager,
        ):
            mock_config_manager.return_value.load_config.return_value = None
            app = BBCBulletinScraper()
            assert app.initialize() is False

    def test_initialize_success_sets_components(self):
        from main import BBCBulletinScraper

        config = _valid_config()
        config["logging"] = {"level": "INFO", "file": "./logs/test.log"}

        with (
            patch("main.signal.signal"),
            patch("main.ConfigManager") as mock_config_manager,
            patch("main.BBCScraper") as mock_scraper_cls,
            patch("main.BulletinScheduler") as mock_scheduler_cls,
            patch("main.HealthMonitor") as mock_health_cls,
            patch("logging.basicConfig"),
        ):
            mock_config_manager.return_value.load_config.return_value = config
            app = BBCBulletinScraper()

            assert app.initialize() is True
            assert app.scraper is mock_scraper_cls.return_value
            assert app.scheduler is mock_scheduler_cls.return_value
            assert app.health_monitor is mock_health_cls.return_value

    def test_shutdown_stops_scheduler_and_health_server(self):
        from main import BBCBulletinScraper

        with patch("main.signal.signal"):
            app = BBCBulletinScraper()

        app.scheduler = MagicMock()
        app.health_monitor = MagicMock()
        app.running = True

        app.shutdown()

        assert app.running is False
        app.scheduler.shutdown.assert_called_once()
        app.health_monitor.stop_http_server.assert_called_once()


def test_main_signal_handler_invokes_shutdown(caplog):
    from main import BBCBulletinScraper

    with patch("main.signal.signal"):
        app = BBCBulletinScraper()
    app.shutdown = MagicMock()

    with caplog.at_level(logging.INFO):
        app._signal_handler(15)  # pylint: disable=protected-access

    app.shutdown.assert_called_once()
    assert "Received signal 15" in caplog.text
