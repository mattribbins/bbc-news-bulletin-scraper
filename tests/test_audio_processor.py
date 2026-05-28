"""Tests for audio_processor module."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


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
                assert (
                    float(duration) == 54.0
                ), f"Expected duration 54.0, got {duration}"

        finally:
            # Restore original method
            processor.get_duration = original_get_duration

    def test_trim_end_edge_cases(self, caplog):
        """Test trim_end_seconds edge cases."""
        import logging

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

    def test_atomic_file_operations(self):
        """Test that temporary file handling prevents race conditions."""
        from audio_processor import AudioProcessor

        config = {"audio": {"format": "wav"}}
        processor = AudioProcessor(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = Path(temp_dir) / "input.m4a"
            output_file = Path(temp_dir) / "output.wav"

            # Create a fake input file
            input_file.write_text("fake audio data")

            # Test successful processing with atomic move
            with (
                patch("subprocess.run") as mock_run,
                patch("os.open") as mock_open,
                patch("os.close"),
                patch("pathlib.Path.replace") as mock_replace,
            ):

                # Mock successful ffmpeg execution
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_run.return_value = mock_result

                # Mock file lock
                mock_open.return_value = 123  # fake file descriptor

                # Mock the atomic file move operation
                mock_replace.return_value = None

                success = processor.process_audio(input_file, output_file)

                # Verify success
                assert success is True

                # Verify subprocess was called with temp file as output
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]  # Get the command args

                # Find the temp file in the command (should be after -i input_file)
                temp_file_used = None
                for i, arg in enumerate(call_args):
                    if arg == str(input_file) and i > 0:
                        # The output file should be the last argument
                        temp_file_used = call_args[-1]
                        break

                assert temp_file_used is not None
                assert (
                    ".processing." in temp_file_used
                ), "Should use unique temp file with .processing.{uuid}"
                assert temp_file_used != str(
                    output_file
                ), "Should not write directly to output file"

            # Test failure cleanup
            with (
                patch("subprocess.run") as mock_run,
                patch("os.open") as mock_open,
                patch("os.close"),
                patch("pathlib.Path.replace") as mock_replace_fail,
            ):

                # Mock failed ffmpeg execution
                mock_result = MagicMock()
                mock_result.returncode = 1
                mock_result.stderr = "FFmpeg error"
                mock_run.return_value = mock_result

                # Mock file lock
                mock_open.return_value = 123

                # Mock the atomic file move operation (won't be called on failure)
                mock_replace_fail.return_value = None

                success = processor.process_audio(input_file, output_file)

                # Verify failure
                assert success is False

                # Verify output file was not created
                assert not output_file.exists()

            # Test timeout cleanup
            with (
                patch("subprocess.run") as mock_run,
                patch("os.open") as mock_open,
                patch("os.close"),
            ):

                # Mock timeout
                import subprocess

                mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 300)

                # Mock file lock
                mock_open.return_value = 123

                success = processor.process_audio(input_file, output_file)

                # Verify failure
                assert success is False

                # Verify output file was not created
                assert not output_file.exists()

            # Test file locking prevents concurrent processing
            with patch("subprocess.run") as mock_run, patch("os.open") as mock_open:

                # Mock file lock failure (another process is processing)
                mock_open.side_effect = FileExistsError("Lock file exists")

                success = processor.process_audio(input_file, output_file)

                # Should return True (considers it successful since another process is handling it)
                assert success is True

                # subprocess.run should not be called since lock failed
                mock_run.assert_not_called()

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

    def test_explicit_format_specification(self):
        """Test that FFmpeg command includes explicit format specification."""
        from audio_processor import AudioProcessor

        config = {"audio": {"format": "wav"}}
        processor = AudioProcessor(config)

        # Test with realistic temporary file paths that match the actual implementation
        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = Path(temp_dir) / "input.m4a"
            temp_output = (
                Path(temp_dir) / "output.processing.abc12345"
            )  # Simulate unique ID

            # Build command and check for explicit format specification
            cmd = processor._build_ffmpeg_command(  # pylint: disable=protected-access
                input_file,
                temp_output,
                trim_start_seconds=0,
                trim_end_seconds=0,
                normalise_lufs=None,
                output_format="wav",
            )

        # Check that -f wav is present in the command
        assert "-f" in cmd
        f_index = cmd.index("-f")
        assert (
            cmd[f_index + 1] == "wav"
        ), "Explicit format specification should be present"

        # Test with different formats
        for output_format in ["mp3", "m4a", "wav"]:
            temp_format_output = Path(temp_dir) / f"output.processing.{output_format}"
            cmd_format = (
                processor._build_ffmpeg_command(  # pylint: disable=protected-access
                    input_file,
                    temp_format_output,
                    trim_start_seconds=0,
                    trim_end_seconds=0,
                    normalise_lufs=None,
                    output_format=output_format,
                )
            )
            assert "-f" in cmd_format
            f_idx = cmd_format.index("-f")
            assert (
                cmd_format[f_idx + 1] == output_format
            ), f"Format {output_format} should be specified"
