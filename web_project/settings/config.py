"""
Centralized configuration for BoulderCup application.

All timing values, intervals, and magic numbers are defined here
and can be overridden via environment variables.
"""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class TimingConfig:
    """Timing and interval configuration."""

    # Grace period for submissions after window ends (prevents data loss from network latency)
    GRACE_PERIOD_SECONDS: int = int(os.getenv('GRACE_PERIOD_SECONDS', '30'))

    # Cache timeout for competition settings (changes rarely)
    SETTINGS_CACHE_TIMEOUT: int = int(os.getenv('SETTINGS_CACHE_TIMEOUT', '300'))

    # Cache timeout for live scoreboard (updates frequently)
    SCOREBOARD_CACHE_TIMEOUT: int = int(os.getenv('SCOREBOARD_CACHE_TIMEOUT', '5'))

    # Session cookie age (24 hours)
    SESSION_COOKIE_AGE: int = int(os.getenv('SESSION_COOKIE_AGE', '86400'))

    # Maximum cache entries
    CACHE_MAX_ENTRIES: int = int(os.getenv('CACHE_MAX_ENTRIES', '1000'))

    # Timestamp comparison epsilon (for floating point comparison)
    TIMESTAMP_EPSILON: float = float(os.getenv('TIMESTAMP_EPSILON', '0.0001'))


@dataclass(frozen=True)
class FrontendConfig:
    """Frontend timing configuration (in milliseconds)."""

    # Warning countdown threshold (show warning in last 5 minutes)
    WARNING_COUNTDOWN_SECONDS: int = 300

    # Autosave delay after last change
    AUTOSAVE_DELAY_MS: int = 5000

    # Server polling interval for window state changes
    POLL_INTERVAL_MS: int = 15000

    # Jitter range for initial poll (5-10 seconds)
    POLL_JITTER_MIN_MS: int = 5000
    POLL_JITTER_MAX_MS: int = 10000

    # Base delay before reload when window starts
    RELOAD_BASE_DELAY_MS: int = 500

    # Base delay before reload when window ends
    RELOAD_BASE_DELAY_WINDOW_END_MS: int = 1500

    # Random jitter added to reloads (0-5 seconds)
    RELOAD_JITTER_MS: int = 5000

    # Toast notification durations
    TOAST_ERROR_DURATION_MS: int = 3000
    TOAST_SUCCESS_DURATION_MS: int = 1500


@dataclass(frozen=True)
class BackupConfig:
    """Database backup configuration."""

    # Directory for database backups
    BACKUP_DIR: str = os.getenv('BACKUP_DIR', 'backups')

    # Backup interval in seconds (default 3 minutes)
    BACKUP_INTERVAL_SECONDS: int = int(os.getenv('BACKUP_INTERVAL_SECONDS', '180'))

    # Number of backup files to keep (rotation)
    BACKUP_KEEP_COUNT: int = int(os.getenv('BACKUP_KEEP_COUNT', '3'))

    # Compress backups with gzip
    BACKUP_COMPRESS: bool = os.getenv('BACKUP_COMPRESS', 'false').lower() == 'true'


@dataclass(frozen=True)
class HealthConfig:
    """Health monitoring configuration."""

    # Directory for application logs
    LOG_DIR: str = os.getenv('LOG_DIR', 'logs')

    # Maximum log file size before rotation (10 MB)
    LOG_MAX_BYTES: int = int(os.getenv('LOG_MAX_BYTES', '10485760'))

    # Number of rotated log files to keep
    LOG_BACKUP_COUNT: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))

    # Number of log entries to show in health endpoint
    HEALTH_LOG_ENTRIES: int = int(os.getenv('HEALTH_LOG_ENTRIES', '100'))


# Singleton instances - import these from other modules
TIMING = TimingConfig()
FRONTEND = FrontendConfig()
BACKUP = BackupConfig()
HEALTH = HealthConfig()
