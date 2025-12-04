#!/usr/bin/env python3
"""
BBC News Bulletin Scraper
Application to automate pulling audio bulletins from BBC Sounds.
"""

import logging
import os
import signal
import sys
from pathlib import Path
from typing import NoReturn, Optional

from config_manager import ConfigManager
from health_monitor import HealthMonitor
from scheduler import BulletinScheduler
from scraper import BBCScraper


class BBCBulletinScraper:
    """Main application class for BBC bulletin scraping."""

    def __init__(self):
        config_path = os.environ.get("BBC_CONFIG")
        self.config_manager = ConfigManager(config_path)
        self.scraper: Optional[BBCScraper] = None
        self.scheduler: Optional[BulletinScheduler] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame=None) -> None:
        """Handle shutdown signals gracefully."""
        logging.info("Received signal %s, shutting down gracefully...", signum)
        self.shutdown()

    def _get_default_log_path(self) -> str:
        """Get appropriate default log path based on environment."""
        # Check if we're likely running in Docker (common Docker paths exist)
        if Path("/app").exists():
            return "/app/logs/scraper.log"

        # Check if we're in the project directory
        cwd = Path.cwd()
        if (cwd / "src").exists() and (cwd / "config").exists():
            return str(cwd / "logs" / "scraper.log")

        # Fallback to current directory logs
        return str(Path.cwd() / "logs" / "scraper.log")

    def initialize(self) -> bool:
        """Initialize the application components."""
        try:
            # Load configuration
            config = self.config_manager.load_config()
            if not config:
                print("ERROR: Failed to load configuration")
                return False

            # Setup logging based on config
            self._setup_logging(config)

            # Initialize scraper
            self.scraper = BBCScraper(config)

            # Initialize scheduler
            self.scheduler = BulletinScheduler(config, self.scraper)

            # Initialize health monitor
            self.health_monitor = HealthMonitor(config, self.scheduler, self.scraper)

            logging.info("BBC Bulletin Scraper initialized successfully")
            return True

        except Exception as e:
            print(f"ERROR: Failed to initialize application: {e}")
            logging.error("Failed to initialize application: %s", e)
            return False

    def _setup_logging(self, config: dict) -> None:
        """Setup logging configuration."""
        log_config = config.get("logging", {})
        log_level = log_config.get("level", "INFO")

        # Smart default for log file - prefer local paths for development
        default_log_file = self._get_default_log_path()
        log_file = log_config.get("file", default_log_file)

        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
            force=True,  # Force reconfiguration
        )

        # Test logging is working
        logging.info("Logging system initialized successfully")

    def run(self) -> None:
        """Run the application."""
        if not self.initialize():
            print("ERROR: Initialization failed, exiting...")
            sys.exit(1)

        try:
            logging.info("Starting BBC Bulletin Scraper...")
            self.running = True

            # Start the scheduler
            if self.scheduler is not None:
                self.scheduler.start()
            else:
                logging.error("Scheduler is None - cannot start")
                raise RuntimeError("Scheduler not initialized")

            # Trigger immediate download on startup
            try:
                logging.info("Attempting to trigger startup download...")
                if self.scheduler is not None:
                    self.scheduler.trigger_immediate_download()
                    logging.info("Startup download trigger completed")
                else:
                    logging.error("Scheduler is None - cannot trigger startup download")
            except Exception as e:
                logging.warning("Failed to trigger startup download: %s", e)

            # Keep the application running
            logging.info("Entering main application loop...")
            while self.running:
                import time

                time.sleep(1)

        except Exception as e:
            logging.error("Application error: %s", e)
            sys.exit(1)

    def shutdown(self) -> None:
        """Shutdown the application gracefully."""
        self.running = False

        if self.scheduler is not None:
            self.scheduler.shutdown()

        if self.health_monitor is not None:
            self.health_monitor.stop_http_server()

        logging.info("BBC Bulletin Scraper shutdown complete")


def main() -> NoReturn:
    """Main entry point."""
    app = BBCBulletinScraper()
    app.run()
    sys.exit(0)  # Explicitly exit to satisfy NoReturn annotation


if __name__ == "__main__":
    main()
