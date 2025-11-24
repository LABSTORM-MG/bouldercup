from datetime import date

from django.db import models


class AgeGroup(models.Model):
    """Represents a tournament age bracket."""

    GENDER_CHOICES = [
        ("male", "Männlich"),
        ("female", "Weiblich"),
        ("mixed", "Gemischt"),
    ]

    name = models.CharField(max_length=150, unique=True)
    min_age = models.PositiveIntegerField(help_text="Minimum age für diese Gruppe.")
    max_age = models.PositiveIntegerField(help_text="Maximum age für diese Gruppe.")
    gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES, default="mixed", help_text="Zielgruppe."
    )

    class Meta:
        ordering = ["min_age", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.min_age}-{self.max_age}, {self.get_gender_display()})"

    def matches(self, age: int, gender: str) -> bool:
        in_range = self.min_age <= age <= self.max_age
        gender_ok = self.gender == "mixed" or self.gender == gender
        return in_range and gender_ok


class Participant(models.Model):
    """Stores a competitor account and links to the matching age group."""

    GENDER_CHOICES = AgeGroup.GENDER_CHOICES

    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    age_group = models.ForeignKey(
        AgeGroup,
        on_delete=models.PROTECT,
        related_name="participants",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "date_of_birth"],
                name="unique_participant_name_dob",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def assign_age_group(self):
        if self.age_group_id:
            return
        match = (
            AgeGroup.objects.filter(min_age__lte=self.age, max_age__gte=self.age)
            .filter(models.Q(gender="mixed") | models.Q(gender=self.gender))
            .order_by("min_age", "name")
            .first()
        )
        if match:
            self.age_group = match

    def save(self, *args, **kwargs):
        # Automatically link to the appropriate age group if none is set.
        self.assign_age_group()
        if not self.password and self.date_of_birth:
            self.password = self.date_of_birth.strftime("%d%m%Y")
        super().save(*args, **kwargs)

    @property
    def age(self) -> int:
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )
