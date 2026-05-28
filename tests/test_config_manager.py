"""Tests for config_manager module."""

import sys
from pathlib import Path

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

    def test_validate_config_success(self):
        from config_manager import ConfigManager

        manager = ConfigManager()
        manager.config = _valid_config()
        assert manager._validate_config() is True  # pylint: disable=protected-access

    @pytest.mark.parametrize("missing_section", ["programmes", "audio", "scheduler"])
    def test_validate_config_missing_required_section(self, missing_section):
        from config_manager import ConfigManager

        config = _valid_config()
        del config[missing_section]
        manager = ConfigManager()
        manager.config = config
        assert manager._validate_config() is False  # pylint: disable=protected-access

    def test_validate_audio_invalid_quality(self):
        from config_manager import ConfigManager

        manager = ConfigManager()
        manager.config = _valid_config()
        manager.config["audio"]["quality"] = "ultra"
        assert manager._validate_audio() is False  # pylint: disable=protected-access

    def test_validate_scheduler_invalid_minute(self):
        from config_manager import ConfigManager

        manager = ConfigManager()
        manager.config = _valid_config()
        manager.config["scheduler"]["minutes_past_hour"] = [61]
        assert manager._validate_scheduler() is False  # pylint: disable=protected-access

    def test_get_uses_dot_notation_and_default(self):
        from config_manager import ConfigManager

        manager = ConfigManager()
        manager.config = {"audio": {"trim_start_seconds": 4}}
        assert manager.get("audio.trim_start_seconds") == 4
        assert manager.get("audio.unknown", "fallback") == "fallback"

    def test_load_config_yaml_error_returns_none(self, tmp_path):
        from config_manager import ConfigManager

        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text("audio: [broken", encoding="utf-8")
        manager = ConfigManager(str(bad_config))
        assert manager.load_config() is None
