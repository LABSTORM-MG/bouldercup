from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AgeGroup, Participant


@receiver(post_save, sender=AgeGroup)
def reassign_participants_after_group_change(sender, instance, **kwargs):
    for participant in Participant.objects.all():
        participant.assign_age_group(force=True)
        participant.save(update_fields=["age_group"])
