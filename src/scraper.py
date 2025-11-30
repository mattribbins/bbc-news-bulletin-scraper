"""
Scraper Module for BBC News Bulletin Scraper
Handles downloading BBC programmes using get_iplayer and processing them.
"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from audio_processor import AudioProcessor


def _get_environment_default_path(path_type: str) -> str:
    """Get environment-appropriate default paths."""
    # Check if we're likely running in Docker
    if Path("/app").exists():
        return f"/app/{path_type}"

    # Check if we're in the project directory
    cwd = Path.cwd()
    if (cwd / "src").exists() and (cwd / "config").exists():
        return str(cwd / path_type)

    # Fallback to current directory
    return str(Path.cwd() / path_type)


class BBCScraper:
    """Main scraper for BBC programmes using get_iplayer."""

    def __init__(self, config: dict):
        self.config = config
        self.download_config = config.get("download", {})
        self.output_config = config.get("output", {})
        self.get_iplayer_config = config.get("get_iplayer", {})

        # Initialize audio processor
        self.audio_processor = AudioProcessor(config)

        # Setup directories with environment-aware defaults
        self.temp_dir = Path(self.download_config.get("temp_path", _get_environment_default_path("downloads")))
        self.output_dir = Path(self.output_config.get("base_path", _get_environment_default_path("output")))
        self.cache_dir = Path(
            self.get_iplayer_config.get("cache_dir", _get_environment_default_path(".get_iplayer"))
        )

        # Create directories
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Verify get_iplayer is available
        self._verify_get_iplayer()

    def _verify_get_iplayer(self) -> None:
        """Verify that get_iplayer is installed and accessible."""
        try:
            # Try to run get_iplayer --help to check if it's available
            result = subprocess.run(
                ["get_iplayer", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError("get_iplayer command failed")

            logging.info("get_iplayer verification successful")

        except subprocess.TimeoutExpired as exc:
            error_msg = "get_iplayer verification timed out"
            logging.error(error_msg)
            raise RuntimeError(error_msg) from exc
        except FileNotFoundError as exc:
            error_msg = (
                "get_iplayer not found. Please install it:\n"
                "macOS: brew install get_iplayer\n"
                "Ubuntu/Debian: apt-get install get-iplayer\n"
                "Or see: https://github.com/get-iplayer/get_iplayer/wiki"
            )
            logging.error(error_msg)
            raise RuntimeError(error_msg) from exc
        except Exception as exc:
            error_msg = f"get_iplayer verification failed: {exc}"
            logging.error(error_msg)
            raise RuntimeError(error_msg) from exc

    def download_programmes(self) -> List[Dict[str, Any]]:
        """Download all enabled programmes."""
        programmes = self.config.get("programmes", [])
        enabled_programmes = [p for p in programmes if p.get("enabled", True)]
        logging.info(f"Found {len(programmes)} programmes, {len(enabled_programmes)} enabled")

        results = []

        for programme in enabled_programmes:
            try:
                result = self.download_programme(programme)
                results.append(result)
            except Exception as e:
                logging.error(
                    "Failed to download programme %s: %s", programme.get("name"), e
                )
                results.append(
                    {
                        "programme": programme,
                        "success": False,
                        "error": str(e),
                        "files": [],
                    }
                )

        return results

    def download_programme(self, programme: Dict[str, Any]) -> Dict[str, Any]:
        """Download a specific programme."""
        programme_name = programme.get("name", "Unknown")

        logging.info("Starting download for programme: %s", programme_name)

        # Build get_iplayer command
        cmd = self._build_get_iplayer_command(programme)
        logging.debug("get_iplayer command: %s", " ".join(cmd))

        try:

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.temp_dir),
                timeout=self.download_config.get("timeout_seconds", 600),
                check=False,
            )

            logging.debug(f"get_iplayer return code: {result.returncode}")
            if result.returncode != 0:
                logging.debug(f"get_iplayer stderr: {result.stderr[:200]}")

            # Handle result - get_iplayer returns 1 if some episodes fail, but others may succeed
            if result.returncode == 0:
                logging.info("Download completed for: %s", programme_name)
            elif result.returncode == 1:
                logging.warning(f"get_iplayer partial success for {programme_name} (some episodes may have failed)")
            else:
                logging.error(f"get_iplayer failed completely for {programme_name}: {result.stderr}")
                return {
                    "programme": programme,
                    "success": False,
                    "error": result.stderr,
                    "files": [],
                }

            # Find downloaded files (works for both success and partial success)
            downloaded_files = self._find_downloaded_files(programme_name)
            logging.debug(f"Found {len(downloaded_files)} downloaded files for {programme_name}")

            # Process downloaded files
            processed_files = []
            for file_path in downloaded_files:
                processed_file = self._process_downloaded_file(file_path, programme)
                if processed_file:
                    processed_files.append(processed_file)

            return {
                "programme": programme,
                "success": True,
                "files": processed_files,
                "raw_output": result.stdout,
            }

        except subprocess.TimeoutExpired:
            error_msg = f"Download timeout for {programme_name}"
            logging.error(error_msg)
            return {
                "programme": programme,
                "success": False,
                "error": error_msg,
                "files": [],
            }
        except Exception as e:
            programme_name = programme.get('name', 'Unknown')
            logging.error("Download error for %s: %s", programme_name, e)
            return {
                "programme": programme,
                "success": False,
                "error": str(e),
                "files": [],
            }

    def _build_get_iplayer_command(self, programme: Dict[str, Any]) -> List[str]:
        """Build get_iplayer command for a programme."""
        cmd = ["get_iplayer"]

        # Extract PID from URL or use URL directly
        programme_url = programme.get("url", "")
        pid = self._extract_pid_from_url(programme_url)

        if pid:
            # Use PID format (preferred)
            cmd.extend(["--pid", pid])
        elif programme_url:
            # Use URL format as fallback
            cmd.extend(["--url", programme_url])
        else:
            raise ValueError(f"No valid URL or PID found for programme: {programme.get('name', 'Unknown')}")

        # Get latest episodes only - use recursive to find episodes but limit to recent ones
        if programme.get("pid_recursive", False):
            cmd.append("--pid-recursive")
            # Limit to episodes from the configured hours to get only latest bulletins
            since_hours = self.config.get("get_iplayer", {}).get("since_hours", 24)
            cmd.extend(["--since", str(since_hours)])

        # Output directory
        cmd.extend(["--output", str(self.temp_dir)])

        # Audio quality
        audio_quality = self.config.get("audio", {}).get("quality", "high")
        cmd.extend(["--radio-quality", self._map_audio_quality(audio_quality)])

        # Cache directory (profile-dir)
        cmd.extend(["--profile-dir", str(self.cache_dir)])

        # Specify radio type for BBC radio programmes
        cmd.extend(["--type", "radio"])

        # Limit to content available since configured hours (latest bulletins only)
        available_since_hours = self.config.get("get_iplayer", {}).get("available_since_hours", 12)
        cmd.extend(["--available-since", str(available_since_hours)])

        # Force download
        cmd.append("--get")

        # Add verbose output for debugging
        cmd.append("--verbose")

        # Overwrite existing files to avoid failures
        cmd.append("--overwrite")

        # Force download even if already in history
        cmd.append("--force")

        # Additional options from config
        extra_options = self.get_iplayer_config.get("extra_options", [])
        if extra_options:
            cmd.extend(extra_options)

        return cmd

    def _extract_pid_from_url(self, url: str) -> Optional[str]:
        """Extract PID from BBC programme URL."""
        if not url:
            return None

        # Extract PID from URLs like:
        # https://www.bbc.co.uk/programmes/p08dy4zh
        # https://www.bbc.co.uk/programmes/p08m00gv
        import re

        # Match PID pattern (starts with letter, followed by alphanumeric)
        pid_match = re.search(r'/programmes/([a-z][a-z0-9]+)', url)
        if pid_match:
            return pid_match.group(1)

        # If it's already just a PID
        if re.match(r'^[a-z][a-z0-9]+$', url):
            return url

        return None

    def _map_audio_quality(self, quality: str) -> str:
        """Map internal quality setting to get_iplayer format."""
        quality_map = {"high": "high", "std": "std", "med": "med", "low": "low"}
        return quality_map.get(quality, "std")

    def _find_downloaded_files(self, programme_name: str) -> List[Path]:
        """Find the latest downloaded file for a specific programme."""
        audio_extensions = [".mp3", ".m4a", ".wav", ".aac"]
        programme_files = []

        # Search in temp directory for recent audio files
        for ext in audio_extensions:
            pattern = f"*{ext}"
            for file_path in self.temp_dir.glob(pattern):
                # Skip partial/incomplete files
                if ".partial." in file_path.name or ".hls." in file_path.name:
                    continue

                # Check if file was created recently (within last hour)
                if self._is_recent_file(file_path):
                    # Check if filename relates to this programme
                    filename_lower = file_path.name.lower()

                    # Match by extracting key words from programme name
                    if self._is_programme_match(filename_lower, programme_name):
                        programme_files.append(file_path)

        # Sort by modification time (newest first) and return only the latest
        if programme_files:
            programme_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            latest_file = [programme_files[0]]  # Return only the most recent
            logging.info(f"Found latest file for {programme_name}: {latest_file[0].name}")
            return latest_file
        else:
            logging.info(f"No recent files found for {programme_name}")
            return []

    def _is_programme_match(self, filename_lower: str, programme_name: str) -> bool:
        """Check if filename matches programme name by extracting key identifying words."""
        programme_lower = programme_name.lower()

        # Extract key words from programme name (skip common BBC words)
        programme_words = programme_lower.replace("bbc", "").replace("update", "").strip().split()

        # Check if any significant programme word appears in filename
        for word in programme_words:
            if word and len(word) > 2 and word in filename_lower:  # Skip short words like "on", "of"
                return True

        return False

    def _is_recent_file(self, file_path: Path, max_age_hours: int = 1) -> bool:
        """Check if file was created recently."""
        try:
            from datetime import timedelta

            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            now = datetime.now()

            return (now - file_time) < timedelta(hours=max_age_hours)
        except Exception:
            return False

    def _process_downloaded_file(
        self, input_file: Path, programme: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Process a downloaded file (trim audio, convert format, move to output)."""
        try:
            # Generate output filename
            output_file = self._generate_output_filename(programme)

            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Process audio (trim, convert, normalize)
            if self.audio_processor.process_audio(input_file, output_file):
                # Clean up temp file
                self._cleanup_temp_file(input_file)

                # Get file info
                duration = self.audio_processor.get_duration(output_file)
                file_size = output_file.stat().st_size

                logging.info(f"Processed file saved: {output_file}")

                return {
                    "input_file": str(input_file),
                    "output_file": str(output_file),
                    "duration_seconds": duration,
                    "file_size_bytes": file_size,
                    "processed_at": datetime.now().isoformat(),
                }
            else:
                logging.error("Failed to process audio file: %s", input_file)
                return None

        except Exception as e:
            logging.error("Error processing file %s: %s", input_file, e)
            return None

    def _generate_output_filename(
        self, programme: Dict[str, Any]
    ) -> Path:
        """Generate simple output filename using output_name from programme config."""
        # Get output name from programme config
        output_name = programme.get("output_name")
        if not output_name:
            # Fallback to programme name if output_name not specified
            output_name = programme.get("name", "unknown").replace(" ", "_").lower()

        # Get audio format for extension
        audio_format = self.config.get("audio", {}).get("format", "mp3")

        # Simple filename: {output_name}.{extension}
        filename = f"{output_name}.{audio_format}"
        output_path = self.output_dir / filename

        return output_path

    def _cleanup_temp_file(self, file_path: Path) -> None:
        """Remove temporary file."""
        try:
            file_path.unlink()
            logging.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logging.warning(f"Failed to cleanup temp file {file_path}: {e}")

    def cleanup_old_files(self) -> None:
        """No longer needed - we keep latest bulletins only, no retention policy."""
        pass
