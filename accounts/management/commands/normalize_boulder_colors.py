"""
Django management command to normalize all boulder colors to standard CSS values.

Usage:
    python manage.py normalize_boulder_colors
"""

from django.core.management.base import BaseCommand
from accounts.models import Boulder


class Command(BaseCommand):
    help = 'Normalize all boulder colors to standard CSS hex values using fuzzy matching'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))

        boulders = Boulder.objects.all()
        total_count = boulders.count()
        updated_count = 0
        unchanged_count = 0

        self.stdout.write(f'Processing {total_count} boulders...\n')

        for boulder in boulders:
            old_color = boulder.color

            # Trigger normalization by calling the classmethod
            if old_color:
                normalized_color = Boulder.normalize_color(old_color)

                if old_color != normalized_color:
                    updated_count += 1
                    self.stdout.write(
                        f'Boulder {boulder.label}: '
                        f'{self.style.WARNING(old_color)} → {self.style.SUCCESS(normalized_color)} '
                        f'({boulder.color_display_name})'
                    )

                    if not dry_run:
                        boulder.color = normalized_color
                        boulder.save()
                else:
                    unchanged_count += 1
            else:
                unchanged_count += 1

        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE - No changes were saved'))
        else:
            self.stdout.write(self.style.SUCCESS('NORMALIZATION COMPLETE'))

        self.stdout.write(f'Total boulders: {total_count}')
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated_count}'))
        self.stdout.write(f'Unchanged: {unchanged_count}')

        if dry_run and updated_count > 0:
            self.stdout.write('\nRun without --dry-run to apply changes.')
