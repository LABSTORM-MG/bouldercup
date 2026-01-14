import re
from datetime import date

from django.db import models
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field


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
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        ordering = ["min_age", "name"]
        verbose_name = "Altersgruppe"
        verbose_name_plural = "Altersgruppen"
        indexes = [
            models.Index(fields=["min_age", "max_age", "gender"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.min_age}-{self.max_age}, {self.get_gender_display()})"

    def matches(self, age: int, gender: str) -> bool:
        in_range = self.min_age <= age <= self.max_age
        gender_ok = self.gender == "mixed" or self.gender == gender
        return in_range and gender_ok

    @property
    def boulders(self):
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
        verbose_name = "Teilnehmer*in"
        verbose_name_plural = "Teilnehmer*innen"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "date_of_birth"],
                name="unique_participant_name_dob",
            )
        ]
        indexes = [
            models.Index(fields=["age_group", "name"]),
            models.Index(fields=["username"]),
        ]

    def __str__(self) -> str:
        return self.name

    def assign_age_group(self, force: bool = False) -> None:
        """Assign appropriate age group based on age and gender."""
        if self.age_group_id and not force:
            return
        qs = AgeGroup.objects.filter(min_age__lte=self.age, max_age__gte=self.age).filter(
            models.Q(gender="mixed") | models.Q(gender=self.gender)
        )
        match = qs.order_by("-created_at", "-id").first()
        self.age_group = match

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
        indexes = [
            models.Index(fields=["label"]),
        ]

    def __str__(self) -> str:
        return f"{self.label} ({self.color})"

    def get_zone_count_display(self) -> str:
        """Get human-readable zone count."""
        return dict(self._meta.get_field('zone_count').choices).get(self.zone_count, str(self.zone_count))

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
    attempts_zone1 = models.PositiveIntegerField(default=0)
    attempts_zone2 = models.PositiveIntegerField(default=0)
    attempts_top = models.PositiveIntegerField(default=0)
    zone1 = models.BooleanField(default=False)
    zone2 = models.BooleanField(default=False)
    top = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("participant", "boulder")
        ordering = ["participant", "boulder"]
        indexes = [
            models.Index(fields=["participant", "-updated_at"]),
            models.Index(fields=["boulder", "-updated_at"]),
            models.Index(fields=["participant", "boulder"]),
        ]

    def __str__(self) -> str:
        return f"{self.participant} – {self.boulder}: top={self.top}, z2={self.zone2}, z1={self.zone1}, tries={self.attempts}"


class CompetitionSettings(models.Model):
    """Singleton model holding the scoring/grading system."""

    GRADING_CHOICES = [
        ("ifsc", "IFSC (Tops/Zones/Versuche)"),
        ("point_based", "Punktebasiert"),
        ("point_based_dynamic", "Punktebasiert (dynamisch)"),
        ("point_based_dynamic_attempts", "Punktebasiert (dynamisch + Versuche)"),
    ]

    name = models.CharField(max_length=150, default="Standard Punkte-Setup", editable=False)
    grading_system = models.CharField(
        max_length=30, choices=GRADING_CHOICES, default="ifsc"
    )
    singleton_guard = models.BooleanField(default=True, unique=True, editable=False)
    top_points = models.PositiveIntegerField(default=25, help_text="Punkte pro Top.")
    flash_points = models.PositiveIntegerField(
        default=30, help_text="Flash-Punkte (ersetzt Top-Punkte bei Top im ersten Versuch)."
    )
    min_top_points = models.PositiveIntegerField(
        default=0, help_text="Mindestpunkte, die ein Top immer bringt."
    )
    # Dynamic scoring: percentage-based top points
    top_points_100 = models.PositiveIntegerField(
        default=25,
        verbose_name="100%",
        help_text="Top-Punkte wenn 100% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_90 = models.PositiveIntegerField(
        default=25,
        verbose_name="90%",
        help_text="Top-Punkte wenn 90% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_80 = models.PositiveIntegerField(
        default=25,
        verbose_name="80%",
        help_text="Top-Punkte wenn 80% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_70 = models.PositiveIntegerField(
        default=30,
        verbose_name="70%",
        help_text="Top-Punkte wenn 70% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_60 = models.PositiveIntegerField(
        default=35,
        verbose_name="60%",
        help_text="Top-Punkte wenn 60% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_50 = models.PositiveIntegerField(
        default=40,
        verbose_name="50%",
        help_text="Top-Punkte wenn 50% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_40 = models.PositiveIntegerField(
        default=42,
        verbose_name="40%",
        help_text="Top-Punkte wenn 40% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_30 = models.PositiveIntegerField(
        default=44,
        verbose_name="30%",
        help_text="Top-Punkte wenn 30% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_20 = models.PositiveIntegerField(
        default=46,
        verbose_name="20%",
        help_text="Top-Punkte wenn 20% der Teilnehmer den Boulder getoppt haben.",
    )
    top_points_10 = models.PositiveIntegerField(
        default=50,
        verbose_name="10%",
        help_text="Top-Punkte wenn 10% oder weniger der Teilnehmer den Boulder getoppt haben.",
    )
    zone_points = models.PositiveIntegerField(
        default=10,
        help_text="Punkte pro Zone (wenn nur eine Zone gewertet wird).",
    )
    zone1_points = models.PositiveIntegerField(
        default=10, help_text="Punkte für Zone 1 (Low Zone bei zwei Zonen)."
    )
    zone2_points = models.PositiveIntegerField(
        default=10, help_text="Punkte für Zone 2 (High Zone bei zwei Zonen)."
    )
    min_zone_points = models.PositiveIntegerField(
        default=0, help_text="Mindestpunkte, die eine Zone immer bringt."
    )
    min_zone1_points = models.PositiveIntegerField(
        default=0, help_text="Mindestpunkte für Zone 1 (Low Zone)."
    )
    min_zone2_points = models.PositiveIntegerField(
        default=0, help_text="Mindestpunkte für Zone 2 (High Zone)."
    )
    attempt_penalty = models.PositiveIntegerField(default=1, help_text="Minuspunkte pro Versuch.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wettkampf-Einstellung"
        verbose_name_plural = "Wettkampf-Einstellungen"

    def __str__(self) -> str:
        return f"Wertung: {self.get_grading_system_display()}"
    
    def save(self, *args, **kwargs):
        """Invalidate cache on save."""
        super().save(*args, **kwargs)
        from django.core.cache import cache
        cache.delete('competition_settings')


class Rulebook(models.Model):
    """Standalone rulebook content."""

    name = models.CharField(max_length=150, default="Regelwerk")
    content = CKEditor5Field("Regelwerk", config_name="default", blank=True)
    singleton_guard = models.BooleanField(default=True, unique=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Regelwerk"
        verbose_name_plural = "Regelwerke"

    def __str__(self) -> str:
        return self.name


class SubmissionWindow(models.Model):
    """Optional submission window for result entry (future enforcement)."""

    name = models.CharField(max_length=150, default="Standard Ergebnisfenster")
    submission_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Zeitpunkt, ab dem Ergebnisse eingetragen werden dürfen.",
    )
    submission_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Zeitpunkt, bis zu dem Ergebnisse eingetragen werden dürfen.",
    )
    note = models.CharField(
        max_length=200,
        blank=True,
        help_text="Interne Notiz (optional).",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Zeitslot für Ergebnis-Eintrag"
        verbose_name_plural = "Zeitslots für Ergebnis-Eintrag"

    def __str__(self) -> str:
        start = self.submission_start.isoformat() if self.submission_start else "offen"
        end = self.submission_end.isoformat() if self.submission_end else "offen"
        return f"Ergebnisfenster: {start} – {end}"
