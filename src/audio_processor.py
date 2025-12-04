"""
Audio Processing Module for BBC News Bulletin Scraper
Handles audio trimming, format conversion, and normalisation.
"""

import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Optional


class AudioProcessor:
    """Handles audio processing using ffmpeg."""

    def __init__(self, config: dict):
        self.config = config
        self.audio_config = config.get("audio", {})

    def process_audio(
        self,
        input_file: Path,
        output_file: Path,
        programme_config: Optional[dict] = None,
    ) -> bool:
        """
        Process audio file with trimming and format conversion.

        Args:
            input_file: Path to input audio file
            output_file: Path to output audio file
            programme_config: Programme-specific config (optional, overrides global settings)

        Returns:
            bool: True if processing successful, False otherwise
        """
        # Create lock file to prevent concurrent processing of same output
        lock_file = output_file.with_suffix(".lock")

        # Check if output file already exists and is recent
        if output_file.exists():
            logging.info(f"Output file already exists: {output_file}")
            return True

        # Try to acquire lock
        try:
            lock_fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            logging.info(
                f"Another process is already processing {output_file}, skipping"
            )
            return True  # Consider this success since another process is handling it

        try:
            # Create temporary file in same directory as output to ensure atomic move works
            # Use unique identifier to prevent race conditions between concurrent processes
            unique_id = uuid.uuid4().hex[:8]
            temp_file = output_file.with_suffix(f".processing.{unique_id}")

            # Double-check output file doesn't exist after acquiring lock
            if output_file.exists():
                logging.info(
                    f"Output file created while waiting for lock: {output_file}"
                )
                return True
            # Get processing parameters - programme config overrides global config
            trim_start_seconds = (programme_config or {}).get(
                "trim_start_seconds", self.audio_config.get("trim_start_seconds", 0)
            )
            trim_end_seconds = (programme_config or {}).get(
                "trim_end_seconds", self.audio_config.get("trim_end_seconds", 0)
            )

            normalise_lufs = self.audio_config.get("normalise_lufs")
            # Support legacy normalize/normalise boolean setting
            if normalise_lufs is None:
                legacy_normalise = self.audio_config.get(
                    "normalise", False
                ) or self.audio_config.get("normalize", False)
                normalise_lufs = -16 if legacy_normalise else None
            output_format = self.audio_config.get("format", "mp3")

            # Build ffmpeg command - process to temporary file
            cmd = self._build_ffmpeg_command(
                input_file,
                temp_file,  # Use temporary file as output
                trim_start_seconds,
                trim_end_seconds,
                normalise_lufs,
                output_format,
            )

            logging.info(f"Processing audio: {input_file} -> {output_file}")
            logging.debug(f"FFmpeg command: {' '.join(cmd)}")

            try:
                # Execute ffmpeg
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
                )

                if result.returncode == 0:
                    # Atomically move temporary file to final destination
                    # This prevents the race condition where a 0-byte file appears before processing completes
                    temp_file.replace(output_file)
                    logging.info(f"Audio processing completed: {output_file}")
                    return True
                else:
                    logging.error(f"FFmpeg failed: {result.stderr}")
                    # Clean up temporary file on failure
                    if temp_file.exists():
                        temp_file.unlink()
                    return False

            except subprocess.TimeoutExpired:
                logging.error("Audio processing timed out")
                # Clean up temporary file on timeout
                if temp_file.exists():
                    temp_file.unlink()
                return False
            except Exception as e:
                logging.error(f"Audio processing error: {e}")
                # Clean up temporary file on error
                if temp_file.exists():
                    temp_file.unlink()
                return False

        finally:
            # Clean up lock file
            try:
                os.close(lock_fd)
                if lock_file.exists():
                    lock_file.unlink()
            except Exception as e:
                logging.warning(f"Failed to clean up lock file: {e}")

    def _build_ffmpeg_command(
        self,
        input_file: Path,
        output_file: Path,
        trim_start_seconds: float,
        trim_end_seconds: float,
        normalise_lufs: float | None,
        output_format: str,
    ) -> list:
        """Build ffmpeg command with specified parameters."""
        cmd = ["ffmpeg", "-y"]  # -y to overwrite output files

        # Input file
        cmd.extend(["-i", str(input_file)])

        # Audio processing filters
        filters = []

        # Trim from start if specified
        if trim_start_seconds > 0:
            cmd.extend(["-ss", str(trim_start_seconds)])

        # Trim from end if specified (using -t duration instead of -to end time)
        if trim_end_seconds > 0:
            # We need to calculate duration: original_duration - trim_start - trim_end
            # Get input duration first
            input_duration = self.get_duration(input_file)
            if input_duration:
                target_duration = input_duration - trim_start_seconds - trim_end_seconds
                if target_duration > 0:
                    cmd.extend(["-t", str(target_duration)])
                else:
                    logging.warning(
                        f"Calculated target duration ({target_duration}s) is invalid for {input_file}, skipping end trim"
                    )
            else:
                logging.warning(
                    f"Could not determine duration of {input_file}, skipping end trim"
                )

        # Normalise audio loudness if enabled with specific LUFS target
        if normalise_lufs is not None:
            # Use loudnorm filter for proper loudness normalisation
            # This normalises to the target LUFS level using EBU R128 algorithm
            filters.append(f"loudnorm=I={normalise_lufs}:TP=-1.0:LRA=7.0")

        # Apply filters if any
        if filters:
            cmd.extend(["-af", ",".join(filters)])

        # Audio codec and quality settings
        if output_format == "mp3":
            cmd.extend(["-codec:a", "libmp3lame"])
            quality = self._get_mp3_quality()
            cmd.extend(["-b:a", quality])
        elif output_format == "m4a":
            cmd.extend(["-codec:a", "aac"])
            quality = self._get_aac_quality()
            cmd.extend(["-b:a", quality])
        elif output_format == "wav":
            cmd.extend(["-codec:a", "pcm_s16le"])

        # Remove video streams (audio only)
        cmd.extend(["-vn"])

        # Explicitly specify output format to handle non-standard temporary file extensions
        cmd.extend(["-f", output_format])

        # Output file
        cmd.append(str(output_file))

        return cmd

    def _get_mp3_quality(self) -> str:
        """Get MP3 bitrate based on quality setting."""
        quality_map = {"high": "320k", "std": "192k", "med": "128k", "low": "96k"}
        quality = self.audio_config.get("quality", "high")
        return quality_map.get(quality, "192k")

    def _get_aac_quality(self) -> str:
        """Get AAC bitrate based on quality setting."""
        quality_map = {"high": "256k", "std": "128k", "med": "96k", "low": "64k"}
        quality = self.audio_config.get("quality", "high")
        return quality_map.get(quality, "128k")

    def get_audio_info(self, file_path: Path) -> Optional[dict]:
        """Get audio file information using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                import json

                return json.loads(result.stdout)
            else:
                logging.error(f"ffprobe failed: {result.stderr}")
                return None

        except Exception as e:
            logging.error(f"Failed to get audio info: {e}")
            return None

    def validate_audio_file(self, file_path: Path) -> bool:
        """Validate that the file is a valid audio file."""
        if not file_path.exists():
            return False

        audio_info = self.get_audio_info(file_path)
        if not audio_info:
            return False

        # Check if file has audio streams
        streams = audio_info.get("streams", [])
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        return len(audio_streams) > 0

    def get_duration(self, file_path: Path) -> Optional[float]:
        """Get audio file duration in seconds."""
        audio_info = self.get_audio_info(file_path)
        if not audio_info:
            return None

        format_info = audio_info.get("format", {})
        duration = format_info.get("duration")

        if duration:
            try:
                return float(duration)
            except ValueError:
                return None

        return None
