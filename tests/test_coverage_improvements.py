"""Additional tests to improve coverage across core modules."""

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


class TestConfigManagerCoverage:
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


class TestSchedulerCoverage:
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


class TestMainCoverage:
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


class TestHealthMonitorCoverage:
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


class TestScraperCoverage:
    @pytest.fixture()
    def scraper(self, tmp_path):
        from scraper import BBCScraper

        config = {
            "download": {"temp_path": str(tmp_path / "downloads")},
            "output": {"base_path": str(tmp_path / "output")},
            "get_iplayer": {"cache_dir": str(tmp_path / ".get_iplayer")},
            "audio": {"format": "wav", "quality": "high"},
        }
        verify = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=verify):
            return BBCScraper(config)

    def test_extract_pid_from_url_and_pid_string(self, scraper):
        pid = scraper._extract_pid_from_url(  # pylint: disable=protected-access
            "https://www.bbc.co.uk/programmes/p08dy4zh"
        )
        assert pid == "p08dy4zh"
        assert (
            scraper._extract_pid_from_url("p123abcd") == "p123abcd"  # pylint: disable=protected-access
        )
        assert scraper._extract_pid_from_url("") is None  # pylint: disable=protected-access

    def test_build_command_uses_url_when_pid_not_extractable(self, scraper):
        cmd = scraper._build_get_iplayer_command(  # pylint: disable=protected-access
            {"name": "X", "url": "https://example.com/not-bbc"}
        )
        assert "--url" in cmd

    def test_build_command_raises_when_no_url_or_pid(self, scraper):
        with pytest.raises(ValueError):
            scraper._build_get_iplayer_command({"name": "X"})  # pylint: disable=protected-access

    def test_programme_match_and_quality_mapping(self, scraper):
        assert scraper._is_programme_match("local_update_p08dy4zh.wav", "BBC Local Update")  # pylint: disable=protected-access
        assert not scraper._is_programme_match("sports_news.wav", "BBC Local Update")  # pylint: disable=protected-access
        assert scraper._map_audio_quality("unknown") == "std"  # pylint: disable=protected-access

    def test_pid_mark_and_check_processed(self, scraper):
        pid = "p123abcd"
        assert scraper._is_pid_processed(pid) is False  # pylint: disable=protected-access
        scraper._mark_pid_processed(pid)  # pylint: disable=protected-access
        assert scraper._is_pid_processed(pid) is True  # pylint: disable=protected-access

    def test_find_downloaded_files_ignores_processed_and_partial(self, scraper):
        fresh = scraper.temp_dir / "BBC_Local_Update_p08dy4zh_.wav"
        old = scraper.temp_dir / "BBC_Local_Update_p08old01_.wav"
        partial = scraper.temp_dir / "BBC_Local_Update.partial.wav"
        for file_path in [fresh, old, partial]:
            file_path.write_text("x", encoding="utf-8")

        scraper._mark_pid_processed("p08old01")  # pylint: disable=protected-access
        results = scraper._find_downloaded_files("BBC Local Update")  # pylint: disable=protected-access
        assert results == [fresh]

    def test_generate_output_filename_uses_fallback_name(self, scraper):
        path = scraper._generate_output_filename({"name": "My Bulletin"})  # pylint: disable=protected-access
        assert path.name == "my_bulletin.wav"

    def test_cleanup_temp_file_handles_missing_file(self, scraper):
        missing = scraper.temp_dir / "missing.wav"
        scraper._cleanup_temp_file(missing)  # pylint: disable=protected-access


class TestAudioProcessorCoverage:
    def test_get_audio_info_and_duration_and_validation(self, tmp_path):
        from audio_processor import AudioProcessor

        processor = AudioProcessor({"audio": {"format": "wav"}})
        audio_file = tmp_path / "a.wav"
        audio_file.write_text("x", encoding="utf-8")

        probe_output = (
            '{"format":{"duration":"12.5"},'
            '"streams":[{"codec_type":"audio"},{"codec_type":"video"}]}'
        )
        result = MagicMock(returncode=0, stdout=probe_output, stderr="")
        with patch("subprocess.run", return_value=result):
            info = processor.get_audio_info(audio_file)
            assert info is not None
            assert processor.get_duration(audio_file) == 12.5
            assert processor.validate_audio_file(audio_file) is True

    def test_get_audio_info_handles_probe_failure(self, tmp_path):
        from audio_processor import AudioProcessor

        processor = AudioProcessor({"audio": {"format": "wav"}})
        audio_file = tmp_path / "a.wav"
        audio_file.write_text("x", encoding="utf-8")
        result = MagicMock(returncode=1, stdout="", stderr="bad")
        with patch("subprocess.run", return_value=result):
            assert processor.get_audio_info(audio_file) is None


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


def test_main_signal_handler_invokes_shutdown(caplog):
    from main import BBCBulletinScraper

    with patch("main.signal.signal"):
        app = BBCBulletinScraper()
    app.shutdown = MagicMock()

    with caplog.at_level(logging.INFO):
        app._signal_handler(15)  # pylint: disable=protected-access

    app.shutdown.assert_called_once()
