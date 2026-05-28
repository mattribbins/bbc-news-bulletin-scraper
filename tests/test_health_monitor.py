"""Tests for health_monitor module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


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

    @pytest.mark.parametrize(
        ("free_bytes", "expected_status"),
        [
            (6 * (1024**3), "pass"),
            (3 * (1024**3), "warn"),
            (500 * (1024**2), "fail"),
        ],
    )
    def test_disk_space_thresholds(self, free_bytes, expected_status):
        from health_monitor import HealthMonitor

        monitor = HealthMonitor({"health": {"enabled": False}, "output": {"base_path": "."}})
        total = 20 * (1024**3)
        used = total - free_bytes

        with patch("shutil.disk_usage", return_value=(total, used, free_bytes)):
            disk_check = monitor._check_disk_space()  # pylint: disable=protected-access

        assert disk_check["status"] == expected_status

    def test_recent_error_thresholds(self):
        from health_monitor import HealthMonitor

        monitor = HealthMonitor({"health": {"enabled": False}})

        monitor.error_count = 0
        assert monitor._check_recent_errors()["status"] == "pass"  # pylint: disable=protected-access

        monitor.error_count = 6
        assert monitor._check_recent_errors()["status"] == "warn"  # pylint: disable=protected-access

        monitor.error_count = 11
        assert monitor._check_recent_errors()["status"] == "fail"  # pylint: disable=protected-access


def test_health_handler_routes():
    from health_monitor import HealthCheckHandler

    monitor = MagicMock()
    monitor.get_health_status.return_value = {"healthy": True}
    monitor.get_detailed_status.return_value = {"status": "ok"}
    monitor.get_metrics.return_value = {"m": 1}

    handler = HealthCheckHandler.__new__(HealthCheckHandler)
    handler.health_monitor = monitor
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    handler.wfile = MagicMock()

    for route in ["/health", "/status", "/metrics", "/unknown"]:
        handler.path = route
        handler.do_GET()

    assert handler.send_response.call_count == 4
