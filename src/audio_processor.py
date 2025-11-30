"""
Audio Processing Module for BBC News Bulletin Scraper
Handles audio trimming, format conversion, and quality normalization.
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional


class AudioProcessor:
    """Handles audio processing using ffmpeg."""

    def __init__(self, config: dict):
        self.config = config
        self.audio_config = config.get("audio", {})

    def process_audio(self, input_file: Path, output_file: Path) -> bool:
        """
        Process audio file with trimming and format conversion.

        Args:
            input_file: Path to input audio file
            output_file: Path to output audio file

        Returns:
            bool: True if processing successful, False otherwise
        """
        try:
            # Get processing parameters
            trim_seconds = self.audio_config.get("trim_start_seconds", 0)
            normalize = self.audio_config.get("normalize", True)
            output_format = self.audio_config.get("format", "mp3")

            # Build ffmpeg command
            cmd = self._build_ffmpeg_command(
                input_file, output_file, trim_seconds, normalize, output_format
            )

            logging.info(f"Processing audio: {input_file} -> {output_file}")
            logging.debug(f"FFmpeg command: {' '.join(cmd)}")

            # Execute ffmpeg
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                logging.info(f"Audio processing completed: {output_file}")
                return True
            else:
                logging.error(f"FFmpeg failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logging.error("Audio processing timed out")
            return False
        except Exception as e:
            logging.error(f"Audio processing error: {e}")
            return False

    def _build_ffmpeg_command(
        self,
        input_file: Path,
        output_file: Path,
        trim_seconds: float,
        normalize: bool,
        output_format: str,
    ) -> list:
        """Build ffmpeg command with specified parameters."""
        cmd = ["ffmpeg", "-y"]  # -y to overwrite output files

        # Input file
        cmd.extend(["-i", str(input_file)])

        # Audio processing filters
        filters = []

        # Trim from start if specified
        if trim_seconds > 0:
            cmd.extend(["-ss", str(trim_seconds)])

        # Normalize audio levels if enabled
        if normalize:
            filters.append("loudnorm")

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
