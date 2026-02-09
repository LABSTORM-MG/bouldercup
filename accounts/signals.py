from datetime import date, timedelta
import logging

from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AgeGroup, Participant
from .utils import hash_password

logger = logging.getLogger(__name__)


def _shift_years(reference_date: date, years: int) -> date:
    """Return date shifted back by `years`, keeping month/day when possible."""
    try:
        return reference_date.replace(year=reference_date.year - years)
    except ValueError:
        return reference_date.replace(month=2, day=28, year=reference_date.year - years)


@receiver(pre_save, sender=Participant)
def set_participant_defaults(sender, instance, **kwargs):
    """
    Set default values for participant before saving.
    
    - Assigns age group based on age and gender
    - Sets default password from date of birth if not set
    """
    if not instance.age_group_id:
        instance.assign_age_group()

    if not instance.password and instance.date_of_birth:
        raw_password = instance.date_of_birth.strftime("%d%m%Y")
        instance.password = hash_password(raw_password)


@receiver(post_save, sender=AgeGroup)
def reassign_participants_after_group_change(sender, instance, **kwargs):
    """
    Reassign participants when age group boundaries change.

    Only reassigns if the calculated age group actually differs from current assignment.
    This preserves manual admin assignments where appropriate and avoids unnecessary updates.
    """
    from django.core.cache import cache
    from .models import CompetitionSettings

    # Get reference date for age calculation
    # Try to use competition date from settings, fall back to today
    settings = cache.get('competition_settings')
    if settings is None:
        settings = CompetitionSettings.objects.filter(singleton_guard=True).first()
        if settings:
            from web_project.settings.config import TIMING
            cache.set('competition_settings', settings, TIMING.SETTINGS_CACHE_TIMEOUT)

    reference_date = settings.competition_date if (settings and settings.competition_date) else date.today()

    # Calculate birth date range for this age group
    # Someone is min_age on the competition date if born between:
    # - reference_date minus min_age years (latest birth)
    # - reference_date minus (max_age + 1) years + 1 day (earliest birth)
    latest_birth = _shift_years(reference_date, instance.min_age)
    earliest_birth = _shift_years(reference_date, instance.max_age + 1) + timedelta(days=1)

    # Build gender filter - FIXED to include mixed gender participants
    gender_filter = Q()
    if instance.gender == "mixed":
        # Mixed age group can include any gender
        pass  # No filter needed
    else:
        # Specific gender age group: match that gender OR mixed gender participants
        gender_filter = Q(gender=instance.gender)

    # Find potentially impacted participants
    impacted = Participant.objects.filter(
        Q(age_group=instance)  # Currently in this group
        | (
            Q(date_of_birth__gte=earliest_birth)
            & Q(date_of_birth__lte=latest_birth)
            & gender_filter
        )
    ).select_related("age_group")

    # Collect participants that need reassignment
    to_update = []

    for participant in impacted:
        # Calculate what the age group SHOULD be
        old_age_group = participant.age_group
        old_age_group_id = participant.age_group_id

        # Temporarily clear age_group to force recalculation
        participant.age_group = None
        participant.age_group_id = None
        participant.assign_age_group(force=False)
        new_age_group_id = participant.age_group_id

        # Only track if age group actually changed
        if old_age_group_id != new_age_group_id:
            to_update.append(participant)
            logger.info(
                f"Participant {participant.username} (ID: {participant.id}) "
                f"reassigned from {old_age_group.name if old_age_group else 'None'} "
                f"to {participant.age_group.name if participant.age_group else 'None'} "
                f"due to age group boundary change"
            )
        else:
            # Restore original age group (no change needed)
            participant.age_group = old_age_group
            participant.age_group_id = old_age_group_id

    # Bulk update all participants that need reassignment (single query)
    reassigned_count = 0
    if to_update:
        Participant.objects.bulk_update(to_update, ['age_group'])
        reassigned_count = len(to_update)

    # Invalidate ALL caches if any participants were reassigned
    # This ensures scoreboard and other cached data reflects new assignments
    if reassigned_count > 0:
        cache.clear()
        logger.info(
            f"Age group '{instance.name}' (ID: {instance.id}) boundary changed: "
            f"{reassigned_count} participants reassigned, all caches cleared"
        )
