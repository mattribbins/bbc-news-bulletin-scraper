"""
Tests for BBC News Bulletin Scraper
Basic smoke tests to validate the application structure.
"""

import sys
from pathlib import Path

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


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
