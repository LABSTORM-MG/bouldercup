"""
Django management command to backup the SQLite database with rotation.

Usage:
    python manage.py backup_database
    python manage.py backup_database --compress
"""
import gzip
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from web_project.settings.config import BACKUP

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backup the SQLite database with rotation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress backup with gzip',
        )

    def handle(self, *args, **options):
        # Get database path
        db_path = settings.DATABASES['default']['NAME']
        if not os.path.exists(db_path):
            self.stdout.write(self.style.ERROR(f'Database not found: {db_path}'))
            logger.error(f'Backup failed: database not found at {db_path}')
            return

        # Create backup directory
        backup_dir = Path(BACKUP.BACKUP_DIR)
        backup_dir.mkdir(exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        compress = options.get('compress', BACKUP.BACKUP_COMPRESS)
        ext = '.sqlite3.gz' if compress else '.sqlite3'
        backup_name = f'db_backup_{timestamp}{ext}'
        backup_path = backup_dir / backup_name

        try:
            # Create backup
            if compress:
                with open(db_path, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(db_path, backup_path)

            self.stdout.write(self.style.SUCCESS(f'Backup created: {backup_path}'))
            logger.info(f'Database backup created: {backup_name}')

            # Rotate old backups
            self._rotate_backups(backup_dir, ext)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Backup failed: {str(e)}'))
            logger.error(f'Database backup failed: {str(e)}', exc_info=True)
            raise

    def _rotate_backups(self, backup_dir, ext):
        """Keep only the most recent N backups."""
        backups = sorted(backup_dir.glob(f'db_backup_*{ext}'))

        if len(backups) > BACKUP.BACKUP_KEEP_COUNT:
            for old_backup in backups[:-BACKUP.BACKUP_KEEP_COUNT]:
                old_backup.unlink()
                self.stdout.write(f'Removed old backup: {old_backup.name}')
                logger.info(f'Removed old backup: {old_backup.name}')
