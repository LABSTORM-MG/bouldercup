from datetime import date, timedelta

from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AgeGroup, Participant
from .utils import hash_password


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
    Limit recalculation to participants likely impacted by this age group change.

    We touch participants currently in this group or whose DOB window and gender
    align with the updated group, instead of iterating the entire table.
    """
    today = date.today()
    latest_birth = _shift_years(today, instance.min_age)
    earliest_birth = _shift_years(today, instance.max_age + 1) + timedelta(days=1)

    gender_filter = Q()
    if instance.gender != "mixed":
        gender_filter = Q(gender=instance.gender)

    impacted = Participant.objects.filter(
        Q(age_group=instance)
        | (
            Q(date_of_birth__gte=earliest_birth)
            & Q(date_of_birth__lte=latest_birth)
            & gender_filter
        )
    ).select_related("age_group")

    for participant in impacted:
        participant.assign_age_group(force=True)
        participant.save(update_fields=["age_group"])
