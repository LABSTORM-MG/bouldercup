"""
Django management command to restore database from backup.

Usage:
    python manage.py restore_database db_backup_20260115_123456.sqlite3
    python manage.py restore_database db_backup_20260115_123456.sqlite3.gz
    python manage.py restore_database backup.sqlite3 --no-safety-backup
"""
import gzip
import logging
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from web_project.settings.config import BACKUP

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Restore database from backup'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_file',
            type=str,
            help='Backup file to restore (filename only, not full path)',
        )
        parser.add_argument(
            '--no-safety-backup',
            action='store_true',
            help='Skip creating safety backup of current database',
        )

    def handle(self, *args, **options):
        backup_file = options['backup_file']
        backup_dir = Path(BACKUP.BACKUP_DIR)
        backup_path = backup_dir / backup_file

        if not backup_path.exists():
            self.stdout.write(self.style.ERROR(f'Backup not found: {backup_path}'))
            logger.error(f'Restore failed: backup not found at {backup_path}')
            return

        db_path = Path(settings.DATABASES['default']['NAME'])

        # Create safety backup of current database
        if not options['no_safety_backup'] and db_path.exists():
            safety_backup = db_path.parent / f'{db_path.name}.before_restore'
            shutil.copy2(db_path, safety_backup)
            self.stdout.write(f'Safety backup created: {safety_backup}')
            logger.info(f'Created safety backup: {safety_backup}')

        # Restore
        try:
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(backup_path, db_path)

            self.stdout.write(self.style.SUCCESS(f'Database restored from: {backup_file}'))
            logger.info(f'Database restored from backup: {backup_file}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Restore failed: {str(e)}'))
            logger.error(f'Database restore failed: {str(e)}', exc_info=True)
            raise
