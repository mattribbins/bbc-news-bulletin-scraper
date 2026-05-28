"""Tests for scraper module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestScraper:
    """Test BBC scraper functionality."""

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


class TestScraperReturnCodes:
    """Test get_iplayer return-code handling in BBCScraper.download_programme."""

    @pytest.fixture()
    def scraper(self, tmp_path):
        """Return a BBCScraper with all filesystem and subprocess side-effects patched out."""
        import subprocess

        from scraper import BBCScraper

        config = {
            "download": {
                "temp_path": str(tmp_path / "downloads"),
                "timeout_seconds": 60,
            },
            "output": {"base_path": str(tmp_path / "output")},
            "get_iplayer": {"cache_dir": str(tmp_path / ".get_iplayer")},
            "audio": {"format": "wav", "quality": "high"},
        }

        verify_result = MagicMock()
        verify_result.returncode = 0

        with patch("subprocess.run", return_value=verify_result):
            s = BBCScraper(config)

        return s

    @pytest.fixture()
    def programme(self):
        return {
            "name": "Test Programme",
            "url": "https://www.bbc.co.uk/programmes/p08dy4zh",
            "output_name": "test_programme",
            "pid_recursive": False,
            "enabled": True,
        }

    def _make_run_result(self, returncode, stderr=""):
        r = MagicMock()
        r.returncode = returncode
        r.stderr = stderr
        r.stdout = ""
        return r

    def _run_with_code(self, scraper, programme, returncode, files=None):
        """Patch subprocess.run and _find_downloaded_files, then call download_programme."""
        from scraper import BBCScraper

        with (
            patch("subprocess.run", return_value=self._make_run_result(returncode)),
            patch.object(
                BBCScraper,
                "_find_downloaded_files",
                return_value=files or [],
            ),
            patch.object(
                BBCScraper,
                "_process_downloaded_file",
                return_value=None,
            ),
        ):
            return scraper.download_programme(programme)

    # --- success path ---

    def test_code_0_success(self, scraper, programme):
        result = self._run_with_code(scraper, programme, returncode=0)
        assert result["success"] is True

    def test_code_0_scans_for_files(self, scraper, programme):
        from scraper import BBCScraper

        with (
            patch("subprocess.run", return_value=self._make_run_result(0)),
            patch.object(
                BBCScraper, "_find_downloaded_files", return_value=[]
            ) as mock_find,
            patch.object(BBCScraper, "_process_downloaded_file", return_value=None),
        ):
            scraper.download_programme(programme)
            mock_find.assert_called_once()

    # --- partial/mixed codes (fail-count) — should fall through and scan ---

    @pytest.mark.parametrize("code", [1, 2, 4, 6, 8, 10, 13])
    def test_partial_codes_return_success_and_scan(self, scraper, programme, code):
        from scraper import BBCScraper

        with (
            patch("subprocess.run", return_value=self._make_run_result(code)),
            patch.object(
                BBCScraper, "_find_downloaded_files", return_value=[]
            ) as mock_find,
            patch.object(BBCScraper, "_process_downloaded_file", return_value=None),
        ):
            result = scraper.download_programme(programme)
            assert (
                result["success"] is True
            ), f"code {code} should fall through to file scan"
            mock_find.assert_called_once()

    # --- hard-fail codes — should return success: False immediately ---

    @pytest.mark.parametrize("code", [3, 5, 7, 11, 12])
    def test_hard_fail_codes_return_failure(self, scraper, programme, code):
        from scraper import BBCScraper

        with (
            patch(
                "subprocess.run", return_value=self._make_run_result(code, stderr="err")
            ),
            patch.object(
                BBCScraper, "_find_downloaded_files", return_value=[]
            ) as mock_find,
        ):
            result = scraper.download_programme(programme)
            assert result["success"] is False, f"code {code} should be a hard failure"
            mock_find.assert_not_called()

    # --- negative return codes (signal termination) — should also hard-fail ---

    @pytest.mark.parametrize("code", [-1, -9, -15])
    def test_negative_codes_return_failure(self, scraper, programme, code):
        from scraper import BBCScraper

        with (
            patch("subprocess.run", return_value=self._make_run_result(code)),
            patch.object(
                BBCScraper, "_find_downloaded_files", return_value=[]
            ) as mock_find,
        ):
            result = scraper.download_programme(programme)
            assert (
                result["success"] is False
            ), f"code {code} (signal) should be a hard failure"
            mock_find.assert_not_called()
