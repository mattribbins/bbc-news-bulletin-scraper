"""
Scheduler Module for BBC News Bulletin Scraper
Handles automatic scheduling of downloads at specified times.
"""

import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class BulletinScheduler:
    """Manages scheduled downloading of BBC bulletins."""

    def __init__(self, config: dict, scraper):
        self.config = config
        self.scraper = scraper
        self.scheduler_config = config.get("scheduler", {})

        # Setup timezone - use system local timezone if not specified
        timezone_str = self.scheduler_config.get("timezone")
        if timezone_str:
            self.timezone: pytz.BaseTzInfo | None = pytz.timezone(timezone_str)
        else:
            # Use system local timezone
            self.timezone = None  # APScheduler will use system local timezone

        # Initialize scheduler
        self.scheduler = self._create_scheduler()

        # Track job execution
        self.last_run: datetime | None = None
        self.total_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0

    def _create_scheduler(self) -> BackgroundScheduler:
        """Create and configure the APScheduler instance."""
        # Configure job stores and executors
        jobstores = {"default": MemoryJobStore()}

        executors = {"default": ThreadPoolExecutor(max_workers=2)}

        job_defaults = {
            "coalesce": True,  # Combine multiple pending executions
            "max_instances": 1,  # Only one instance at a time
            "misfire_grace_time": 300,  # 5 minutes grace for missed jobs
        }

        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=self.timezone,
        )

        return scheduler

    def start(self) -> None:
        """Start the scheduler and configure download jobs."""
        try:
            # Add download jobs
            self._schedule_download_jobs()

            # Start the scheduler
            self.scheduler.start()

            logging.info("Bulletin scheduler started successfully")
            self._log_scheduled_jobs()

        except Exception as e:
            logging.error("Failed to start scheduler: %s", e)
            raise

    def trigger_immediate_download(self) -> None:
        """Trigger an immediate download regardless of schedule."""
        # Check if startup download is enabled
        download_on_startup = self.scheduler_config.get("download_on_startup", False)
        logging.info("Download on startup setting: %s", download_on_startup)

        if not download_on_startup:
            logging.info("Startup download is disabled in configuration")
            return

        try:
            logging.info("Triggering immediate bulletin download on startup")

            # Schedule a one-time job to run immediately (in 2 seconds to allow startup to complete)
            self.scheduler.add_job(
                func=self._execute_download,
                trigger="date",
                run_date=datetime.now(self.timezone).replace(microsecond=0)
                + timedelta(seconds=2),
                id="startup_download",
                name="Startup Download",
                replace_existing=True,
            )

            logging.info("Immediate download scheduled for 2 seconds from startup")

        except Exception as e:
            logging.error("Failed to trigger immediate download: %s", e)

    def download_now(self) -> bool:
        """Execute an immediate download synchronously and return success status."""
        try:
            logging.info("Executing immediate bulletin download")
            self._execute_download()
            return True
        except Exception as e:
            logging.error("Failed to execute immediate download: %s", e)
            return False

    def _schedule_download_jobs(self) -> None:
        """Schedule download jobs based on configuration."""
        minutes_past_hour = self.scheduler_config.get("minutes_past_hour", [5])
        start_hour = self.scheduler_config.get("start_hour", 0)
        end_hour = self.scheduler_config.get("end_hour", 23)
        days_of_week = self.scheduler_config.get("days_of_week", list(range(7)))

        # Convert day numbers (0=Monday) to cron format (0=Sunday)
        cron_days = [(day + 1) % 7 for day in days_of_week]
        cron_days_str = ",".join(map(str, cron_days))

        for minute in minutes_past_hour:
            # Create cron trigger
            trigger = CronTrigger(
                minute=minute,
                hour=f"{start_hour}-{end_hour}",
                day_of_week=cron_days_str,
                timezone=self.timezone,
            )

            # Add job
            job_id = f"download_bulletins_{minute:02d}"
            self.scheduler.add_job(
                func=self._execute_download,
                trigger=trigger,
                id=job_id,
                name=f"Download BBC Bulletins at :{minute:02d}",
                replace_existing=True,
            )

            logging.info("Scheduled download job: %s at minute %d", job_id, minute)

    def _schedule_cleanup_job(self) -> None:
        """Schedule daily cleanup job."""
        # Run cleanup at 2 AM daily
        trigger = CronTrigger(hour=2, minute=0, timezone=self.timezone)

        self.scheduler.add_job(
            func=self._execute_cleanup,
            trigger=trigger,
            id="daily_cleanup",
            name="Daily File Cleanup",
            replace_existing=True,
        )

        logging.info("Scheduled daily cleanup job at 02:00")

    def _execute_download(self) -> None:
        """Execute the download job."""
        job_start_time = datetime.now(self.timezone)
        self.total_runs += 1

        try:
            logging.info("Starting scheduled bulletin download")

            # Execute the download
            results = self.scraper.download_programmes()

            # Process results
            successful_programmes = [r for r in results if r.get("success", False)]
            failed_programmes = [r for r in results if not r.get("success", False)]

            total_files = sum(len(r.get("files", [])) for r in successful_programmes)
            logging.debug(
                f"Download results: {len(successful_programmes)} successful, {len(failed_programmes)} failed, {total_files} files processed"
            )

            # Log results
            if successful_programmes:
                self.successful_runs += 1
                logging.info(
                    f"Download completed successfully: "
                    f"{len(successful_programmes)} programmes, "
                    f"{total_files} files processed"
                )
            else:
                self.failed_runs += 1
                logging.warning("No programmes downloaded successfully")

            if failed_programmes:
                logging.warning(
                    f"{len(failed_programmes)} programmes failed to download"
                )
                for result in failed_programmes:
                    programme_name = result.get("programme", {}).get("name", "Unknown")
                    error_msg = result.get("error", "Unknown error")
                    logging.error(
                        "Failed programme: %s - %s", programme_name, error_msg
                    )

            self.last_run = job_start_time

        except Exception as e:
            self.failed_runs += 1
            logging.error("Scheduled download failed: %s", e)
            raise

    def _execute_cleanup(self) -> None:
        """No longer needed - cleanup job removed since we keep latest bulletins only."""
        pass

    def _log_scheduled_jobs(self) -> None:
        """Log information about scheduled jobs."""
        jobs = self.scheduler.get_jobs()

        logging.info(f"Scheduled {len(jobs)} jobs:")
        for job in jobs:
            next_run = job.next_run_time
            if next_run:
                next_run_str = next_run.strftime("%Y-%m-%d %H:%M:%S")
                logging.info(f"  {job.name} - Next run: {next_run_str}")
            else:
                logging.info(f"  {job.name} - No next run scheduled")

    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully."""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
                logging.info("Scheduler shutdown completed")
        except Exception as e:
            logging.error("Error during scheduler shutdown: %s", e)

    def get_status(self) -> dict:
        """Get scheduler status information."""
        return {
            "running": self.scheduler.running if self.scheduler else False,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_jobs": (
                [
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run": (
                            job.next_run_time.isoformat() if job.next_run_time else None
                        ),
                    }
                    for job in self.scheduler.get_jobs()
                ]
                if self.scheduler
                else []
            ),
        }

    def trigger_download_now(self) -> dict:
        """Manually trigger a download job."""
        try:
            logging.info("Manual download triggered")
            results = self.scraper.download_programmes()

            successful_programmes = [r for r in results if r.get("success", False)]
            failed_programmes = [r for r in results if not r.get("success", False)]
            total_files = sum(len(r.get("files", [])) for r in successful_programmes)

            return {
                "success": True,
                "programmes_successful": len(successful_programmes),
                "programmes_failed": len(failed_programmes),
                "total_files": total_files,
                "results": results,
            }

        except Exception as e:
            logging.error(f"Manual download failed: {e}")
            return {"success": False, "error": str(e)}
