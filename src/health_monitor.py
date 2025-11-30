"""
Health Monitoring Module for BBC News Bulletin Scraper
Provides health checks and monitoring capabilities.
"""

import json
import logging
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict


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


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health checks."""

    def __init__(self, health_monitor, *args, **kwargs):
        self.health_monitor = health_monitor
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self._handle_health_check()
        elif self.path == "/status":
            self._handle_status_check()
        elif self.path == "/metrics":
            self._handle_metrics()
        else:
            self._send_response(404, {"error": "Not found"})

    def _handle_health_check(self):
        """Handle basic health check."""
        health_status = self.health_monitor.get_health_status()
        status_code = 200 if health_status["healthy"] else 503
        self._send_response(status_code, health_status)

    def _handle_status_check(self):
        """Handle detailed status check."""
        status = self.health_monitor.get_detailed_status()
        self._send_response(200, status)

    def _handle_metrics(self):
        """Handle metrics endpoint."""
        metrics = self.health_monitor.get_metrics()
        self._send_response(200, metrics)

    def _send_response(self, status_code: int, data: dict):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def log_message(self, format, *args):
        """Override to suppress access logs."""
        pass


class HealthMonitor:
    """Monitors application health and provides status information."""

    def __init__(self, config: dict, scheduler=None, scraper=None):
        self.config = config
        self.health_config = config.get("health", {})
        self.scheduler = scheduler
        self.scraper = scraper

        # Health tracking
        self.start_time = datetime.now()
        self.last_check: datetime | None = None
        self.error_count = 0
        self.warning_count = 0

        # HTTP server for health checks
        self.http_server = None
        self.server_thread = None

        if self.health_config.get("enabled", False):
            self._start_http_server()

    def _start_http_server(self):
        """Start HTTP server for health checks."""
        try:
            port = self.health_config.get("port", 8080)

            # Create handler with health monitor reference
            def handler(*args, **kwargs):
                return HealthCheckHandler(self, *args, **kwargs)

            self.http_server = HTTPServer(("0.0.0.0", port), handler)

            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self.http_server.serve_forever, daemon=True
            )
            self.server_thread.start()

            logging.info(f"Health check server started on port {port}")

        except Exception as e:
            logging.error(f"Failed to start health check server: {e}")

    def stop_http_server(self):
        """Stop the HTTP server."""
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()

            if self.server_thread:
                self.server_thread.join(timeout=5)

            logging.info("Health check server stopped")

    def get_health_status(self) -> Dict[str, Any]:
        """Get basic health status."""
        self.last_check = datetime.now()

        # Basic health checks
        healthy = True
        checks = []

        # Check if scheduler is running
        if self.scheduler:
            scheduler_running = self.scheduler.scheduler.running
            checks.append(
                {
                    "name": "scheduler",
                    "status": "pass" if scheduler_running else "fail",
                    "message": (
                        "Scheduler is running"
                        if scheduler_running
                        else "Scheduler not running"
                    ),
                }
            )
            if not scheduler_running:
                healthy = False

        # Check disk space
        disk_check = self._check_disk_space()
        checks.append(disk_check)
        if disk_check["status"] == "fail":
            healthy = False

        # Check recent errors
        error_check = self._check_recent_errors()
        checks.append(error_check)
        if error_check["status"] == "fail":
            healthy = False

        return {
            "healthy": healthy,
            "timestamp": (
                self.last_check.isoformat()
                if self.last_check
                else datetime.now().isoformat()
            ),
            "uptime_seconds": (
                (self.last_check - self.start_time).total_seconds()
                if self.last_check
                else 0.0
            ),
            "checks": checks,
        }

    def get_detailed_status(self) -> Dict[str, Any]:
        """Get detailed application status."""
        status = {
            "application": {
                "name": self.config.get("app", {}).get(
                    "name", "BBC News Bulletin Scraper"
                ),
                "version": self.config.get("app", {}).get("version", "1.0.0"),
                "start_time": self.start_time.isoformat(),
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            },
            "health": self.get_health_status(),
            "configuration": {
                "programmes_enabled": len(
                    [
                        p
                        for p in self.config.get("programmes", [])
                        if p.get("enabled", True)
                    ]
                ),
                "output_path": self.config.get("output", {}).get("base_path"),
                "trim_seconds": self.config.get("audio", {}).get(
                    "trim_start_seconds", 0
                ),
            },
        }

        # Add scheduler status if available
        if self.scheduler:
            status["scheduler"] = self.scheduler.get_status()

        return status

    def get_metrics(self) -> Dict[str, Any]:
        """Get application metrics."""
        metrics = {
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "error_count_total": self.error_count,
            "warning_count_total": self.warning_count,
            "last_check_timestamp": (
                self.last_check.isoformat() if self.last_check else None
            ),
        }

        # Add scheduler metrics if available
        if self.scheduler:
            scheduler_status = self.scheduler.get_status()
            metrics.update(
                {
                    "download_runs_total": scheduler_status.get("total_runs", 0),
                    "download_runs_successful": scheduler_status.get(
                        "successful_runs", 0
                    ),
                    "download_runs_failed": scheduler_status.get("failed_runs", 0),
                }
            )

        # Add disk usage metrics
        disk_info = self._get_disk_usage()
        if disk_info:
            metrics.update(disk_info)

        return metrics

    def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space."""
        try:
            import shutil

            output_path = self.config.get("output", {}).get(
                "base_path", _get_environment_default_path("output")
            )
            total, _used, free = shutil.disk_usage(output_path)

            free_gb = free / (1024**3)
            free_percent = (free / total) * 100

            # Warn if less than 1GB or 10% free
            if free_gb < 1 or free_percent < 10:
                return {
                    "name": "disk_space",
                    "status": "fail",
                    "message": f"Low disk space: {free_gb:.1f}GB ({free_percent:.1f}%) free",
                }
            elif free_gb < 5 or free_percent < 20:
                return {
                    "name": "disk_space",
                    "status": "warn",
                    "message": f"Disk space warning: {free_gb:.1f}GB ({free_percent:.1f}%) free",
                }
            else:
                return {
                    "name": "disk_space",
                    "status": "pass",
                    "message": f"Disk space OK: {free_gb:.1f}GB ({free_percent:.1f}%) free",
                }

        except Exception as e:
            return {
                "name": "disk_space",
                "status": "fail",
                "message": f"Failed to check disk space: {e}",
            }

    def _check_recent_errors(self) -> Dict[str, Any]:
        """Check for recent errors in logs."""
        # Simple implementation - could be enhanced to read log files
        # recent_threshold = datetime.now() - timedelta(hours=1)  # noqa: F841

        if self.error_count > 10:  # Arbitrary threshold
            return {
                "name": "recent_errors",
                "status": "fail",
                "message": (f"High error count: {self.error_count} errors"),
            }
        elif self.error_count > 5:
            return {
                "name": "recent_errors",
                "status": "warn",
                "message": (f"Moderate error count: {self.error_count} errors"),
            }
        else:
            return {
                "name": "recent_errors",
                "status": "pass",
                "message": f"Error count OK: {self.error_count} errors",
            }

    def _get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage information."""
        try:
            import shutil

            output_path = self.config.get("output", {}).get(
                "base_path", _get_environment_default_path("output")
            )
            total, used, free = shutil.disk_usage(output_path)

            return {
                "disk_total_bytes": total,
                "disk_used_bytes": used,
                "disk_free_bytes": free,
                "disk_usage_percent": (used / total) * 100,
            }

        except Exception:
            return {}

    def record_error(self):
        """Record an error occurrence."""
        self.error_count += 1

    def record_warning(self):
        """Record a warning occurrence."""
        self.warning_count += 1

    def reset_counters(self):
        """Reset error and warning counters."""
        self.error_count = 0
        self.warning_count = 0
