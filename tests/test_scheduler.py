"""Tests for scheduler module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


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

    def _make_scheduler(self, config):
        from scheduler import BulletinScheduler

        scraper = MagicMock()
        return BulletinScheduler(config, scraper), scraper

    def test_schedule_download_jobs_registers_each_minute(self):
        config = {"scheduler": {"minutes_past_hour": [5, 35], "days_of_week": [0, 2]}}
        scheduler, _scraper = self._make_scheduler(config)

        with patch.object(scheduler.scheduler, "add_job") as mock_add_job:
            scheduler._schedule_download_jobs()  # pylint: disable=protected-access

        assert mock_add_job.call_count == 2
        call_kwargs = [call.kwargs for call in mock_add_job.call_args_list]
        assert {kwargs["id"] for kwargs in call_kwargs} == {
            "download_bulletins_05",
            "download_bulletins_35",
        }

    def test_trigger_immediate_download_disabled_does_not_schedule(self):
        config = {"scheduler": {"download_on_startup": False}}
        scheduler, _scraper = self._make_scheduler(config)

        with patch.object(scheduler.scheduler, "add_job") as mock_add_job:
            scheduler.trigger_immediate_download()

        mock_add_job.assert_not_called()

    def test_trigger_immediate_download_enabled_schedules_job(self):
        config = {"scheduler": {"download_on_startup": True}}
        scheduler, _scraper = self._make_scheduler(config)

        with patch.object(scheduler.scheduler, "add_job") as mock_add_job:
            scheduler.trigger_immediate_download()

        mock_add_job.assert_called_once()
        assert mock_add_job.call_args.kwargs["id"] == "startup_download"

    def test_execute_download_updates_success_counters(self):
        config = {"scheduler": {"minutes_past_hour": [5]}}
        scheduler, scraper = self._make_scheduler(config)
        scraper.download_programmes.return_value = [{"success": True, "files": [1]}]

        scheduler._execute_download()  # pylint: disable=protected-access

        assert scheduler.total_runs == 1
        assert scheduler.successful_runs == 1
        assert scheduler.failed_runs == 0
        assert scheduler.last_run is not None

    def test_execute_download_updates_failed_counter_when_no_success(self):
        config = {"scheduler": {"minutes_past_hour": [5]}}
        scheduler, scraper = self._make_scheduler(config)
        scraper.download_programmes.return_value = [
            {"success": False, "files": [], "programme": {"name": "X"}, "error": "bad"}
        ]

        scheduler._execute_download()  # pylint: disable=protected-access

        assert scheduler.total_runs == 1
        assert scheduler.successful_runs == 0
        assert scheduler.failed_runs == 1

    def test_download_now_returns_false_on_exception(self):
        config = {"scheduler": {"minutes_past_hour": [5]}}
        scheduler, _scraper = self._make_scheduler(config)

        with patch.object(
            scheduler, "_execute_download", side_effect=RuntimeError("boom")
        ):
            assert scheduler.download_now() is False
