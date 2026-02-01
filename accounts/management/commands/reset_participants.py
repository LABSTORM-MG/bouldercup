"""
Django management command to reset all participant data from the database.

This command removes:
- All participants
- All results
- All admin messages (broadcast messages)
- All submission windows

It preserves:
- Competition settings
- Age groups
- Boulders
- Rulebook and help text
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Participant, Result, AdminMessage, SubmissionWindow


class Command(BaseCommand):
    help = "Reset all participant data (participants, results, admin messages, submission windows)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that you want to reset all participant data",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stdout.write(
                self.style.ERROR(
                    "This command will delete all participants, results, admin messages, and submission windows.\n"
                    "To confirm, run: python manage.py reset_participants --confirm"
                )
            )
            return

        self.stdout.write("Resetting participant data...")

        with transaction.atomic():
            # Count before deletion
            participant_count = Participant.objects.count()
            result_count = Result.objects.count()
            admin_message_count = AdminMessage.objects.count()
            submission_window_count = SubmissionWindow.objects.count()

            # Delete all participant-related data
            Result.objects.all().delete()
            Participant.objects.all().delete()
            AdminMessage.objects.all().delete()
            SubmissionWindow.objects.all().delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully deleted:\n"
                    f"  - {participant_count} participants\n"
                    f"  - {result_count} results\n"
                    f"  - {admin_message_count} admin messages\n"
                    f"  - {submission_window_count} submission windows"
                )
            )
