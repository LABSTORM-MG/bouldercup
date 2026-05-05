from datetime import date, timedelta
import logging

from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AgeGroup, Boulder, Participant, Result
from .utils import hash_password

logger = logging.getLogger(__name__)


def _shift_years(reference_date: date, years: int) -> date:
    """Return date shifted back by `years`, keeping month/day when possible."""
    try:
        return reference_date.replace(year=reference_date.year - years)
    except ValueError:
        return reference_date.replace(month=2, day=28, year=reference_date.year - years)


@receiver(pre_save, sender=Boulder)
def capture_boulder_zone_count(sender, instance, **kwargs):
    """Capture old zone_count before Boulder save for comparison in post_save."""
    if instance.pk:
        try:
            instance._old_zone_count = Boulder.objects.filter(pk=instance.pk).values_list('zone_count', flat=True).get()
        except Boulder.DoesNotExist:
            instance._old_zone_count = None
    else:
        instance._old_zone_count = None


@receiver(post_save, sender=Boulder)
def normalize_results_after_zone_change(sender, instance, **kwargs):
    """
    Normalize Result zone fields when a Boulder's zone_count changes.

    Uses QuerySet.update() to bypass .save(), so updated_at, HistoricalRecords,
    and version are not touched — this is a technical cleanup, not a participant action.
    """
    old_zone_count = getattr(instance, '_old_zone_count', None)
    if old_zone_count is None or old_zone_count == instance.zone_count:
        return

    qs = Result.objects.filter(boulder=instance)

    if instance.zone_count == 0:
        qs.update(zone1=False, zone2=False, attempts_zone1=0, attempts_zone2=0)
    elif instance.zone_count == 1:
        qs.filter(zone2=True).update(zone2=False, attempts_zone2=0)


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

    # Invalidate scoreboard caches if any participants were reassigned
    # This ensures scoreboards reflect new age group assignments
    if reassigned_count > 0:
        from .services.scoring_service import ScoringService
        ScoringService.invalidate_all_scoreboards()
        logger.info(
            f"Age group '{instance.name}' (ID: {instance.id}) boundary changed: "
            f"{reassigned_count} participants reassigned, scoreboard caches invalidated"
        )
