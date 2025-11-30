import re
from datetime import date

from django.db import models
from django.utils.text import slugify


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

    @property
    def boulders(self):
        # Expose reverse relation when defined on Boulder.
        return self.boulder_set.all()


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

    def assign_age_group(self, force: bool = False):
        if self.age_group_id and not force:
            return
        match = (
            AgeGroup.objects.filter(min_age__lte=self.age, max_age__gte=self.age)
            .filter(models.Q(gender="mixed") | models.Q(gender=self.gender))
            .order_by("min_age", "name")
            .first()
        )
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


class Boulder(models.Model):
    """Represents a single boulder in the competition."""

    COLOR_ALIASES = {
        "rot": "#ef4444",
        "hellrot": "#f87171",
        "dunkelrot": "#b91c1c",
        "blau": "#3b82f6",
        "hellblau": "#38bdf8",
        "dunkelblau": "#1d4ed8",
        "grun": "#22c55e",
        "gruen": "#22c55e",
        "hellgrun": "#86efac",
        "dunkelgrun": "#15803d",
        "gelb": "#facc15",
        "orange": "#fb923c",
        "lila": "#a855f7",
        "violett": "#8b5cf6",
        "pink": "#ec4899",
        "tuerkis": "#06b6d4",
        "türkis": "#06b6d4",
        "mint": "#a7f3d0",
        "schwarz": "#0f172a",
        "grau": "#9ca3af",
        "silber": "#cbd5e1",
        "weiss": "#e5e7eb",
        "weiß": "#e5e7eb",
        "braun": "#92400e",
    }
    HEX_PATTERN = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

    label = models.CharField(
        max_length=30,
        unique=True,
        help_text="Kürzel oder Nummer, z.B. B12 oder A3.",
    )
    zone_count = models.PositiveSmallIntegerField(
        default=0,
        choices=[
            (0, "Keine Zone"),
            (1, "Eine Zone"),
            (2, "Zwei Zonen"),
        ],
        help_text="Anzahl der Zonen, die getickt werden können.",
    )
    color = models.CharField(
        max_length=50,
        help_text="Griff-/Tape-Farbe zur einfachen Zuordnung.",
    )
    age_groups = models.ManyToManyField(
        AgeGroup,
        related_name="boulders",
        blank=True,
        help_text="Wähle alle Altersgruppen, für die dieser Boulder gedacht ist.",
    )
    note = models.TextField(blank=True)
    location = models.CharField(
        max_length=150,
        blank=True,
        help_text="Sektor/Zone (kann später als eigenes Modell ausgegliedert werden).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["label"]

    def __str__(self) -> str:
        return f"{self.label} ({self.color})"

    @classmethod
    def normalize_color(cls, value: str) -> str:
        """
        Map free-text color input to a CSS-friendly value.

        Accepts hex values (with/without #) and German color names with
        common variants such as "grün", "gruen", "hellblau".
        """
        if not value:
            return value

        raw = value.strip()
        if cls.HEX_PATTERN.match(raw):
            normalized = raw.lower()
            if not normalized.startswith("#"):
                normalized = f"#{normalized}"
            # Expand shorthand hex (e.g. #f00 -> #ff0000) to keep it predictable.
            if len(normalized) == 4:
                normalized = "#" + "".join(char * 2 for char in normalized[1:])
            return normalized

        # slugify handles umlauts, spaces and punctuation (e.g. "Grün" -> "grun")
        alias_key = slugify(raw).replace("-", "")
        if alias_key in cls.COLOR_ALIASES:
            return cls.COLOR_ALIASES[alias_key]

        return raw.lower()

    def save(self, *args, **kwargs):
        self.color = self.normalize_color(self.color)
        super().save(*args, **kwargs)


class Result(models.Model):
    """Stores the outcome for a participant on a specific boulder."""

    participant = models.ForeignKey(
        Participant, on_delete=models.CASCADE, related_name="results"
    )
    boulder = models.ForeignKey(
        Boulder, on_delete=models.CASCADE, related_name="results"
    )
    attempts = models.PositiveIntegerField(default=0)
    zone1 = models.BooleanField(default=False)
    zone2 = models.BooleanField(default=False)
    top = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("participant", "boulder")
        ordering = ["participant", "boulder"]

    def __str__(self) -> str:
        return f"{self.participant} – {self.boulder}: top={self.top}, z2={self.zone2}, z1={self.zone1}, tries={self.attempts}"


class CompetitionSettings(models.Model):
    """Singleton model to pick the active scoring/grading system."""

    GRADING_CHOICES = [
        ("ifsc", "IFSC (Tops/Zones/Versuche)"),
        ("custom", "Punktebasiert"),
    ]

    grading_system = models.CharField(
        max_length=20, choices=GRADING_CHOICES, default="ifsc"
    )
    top_points = models.PositiveIntegerField(default=25, help_text="Punkte pro Top (Custom).")
    zone_points = models.PositiveIntegerField(default=10, help_text="Punkte pro Zone (Custom).")
    flash_points = models.PositiveIntegerField(default=5, help_text="Zusatzpunkte bei Flash (Top im ersten Versuch, Custom).")
    attempt_penalty = models.PositiveIntegerField(default=1, help_text="Minuspunkte pro Versuch (Custom).")
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wettkampf-Einstellung"
        verbose_name_plural = "Wettkampf-Einstellungen"

    def __str__(self) -> str:
        return f"Aktives Scoring: {self.get_grading_system_display()}"
