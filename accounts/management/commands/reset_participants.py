"""
Django management command to completely reset the database.

This command deletes the entire database file and recreates it from scratch.
All data is wiped including:
- All participants and results
- All admin messages and submission windows
- Competition settings
- Age groups and boulders
- Rulebook and help text
- Everything

This is equivalent to what dev_start.sh does when it deletes db.sqlite3.
"""

import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    help = "Completely reset the database (deletes db.sqlite3 and recreates from migrations)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that you want to completely reset the database",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stdout.write(
                self.style.ERROR(
                    "This command will COMPLETELY DELETE the database and recreate it from scratch.\n"
                    "ALL DATA WILL BE LOST including settings, age groups, boulders, and participants.\n"
                    "To confirm, run: python manage.py reset_participants --confirm"
                )
            )
            return

        # Get database path from settings
        db_path = settings.DATABASES['default']['NAME']

        if not os.path.exists(db_path):
            self.stdout.write(self.style.WARNING(f"Database file not found: {db_path}"))
            self.stdout.write("Creating fresh database...")
        else:
            self.stdout.write(self.style.WARNING(f"Deleting database file: {db_path}"))
            os.remove(db_path)
            self.stdout.write(self.style.SUCCESS("Database file deleted"))

        # Run migrations to create fresh database
        self.stdout.write("Running migrations to create fresh database...")
        call_command('migrate', verbosity=1)

        self.stdout.write(
            self.style.SUCCESS(
                "\nDatabase completely reset! Fresh database created from migrations."
            )
        )
