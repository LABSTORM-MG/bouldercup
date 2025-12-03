from django.db import migrations, models
import django.db.models.deletion
from django_ckeditor_5.fields import CKEditor5Field


def seed_competition_settings(apps, schema_editor):
    Settings = apps.get_model("accounts", "CompetitionSettings")
    if not Settings.objects.exists():
        Settings.objects.create(
            grading_system="ifsc",
            name="Standard Punkte-Setup",
            top_points=25,
            flash_points=5,
            min_top_points=0,
            zone_points=10,
            zone1_points=10,
            zone2_points=10,
            min_zone_points=0,
            min_zone1_points=0,
            min_zone2_points=0,
            attempt_penalty=1,
            singleton_guard=True,
        )


def seed_rulebook(apps, schema_editor):
    Rulebook = apps.get_model("accounts", "Rulebook")
    if not Rulebook.objects.exists():
        Rulebook.objects.create(name="Regelwerk", content="")


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AgeGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
                ("min_age", models.PositiveIntegerField(help_text="Minimum age für diese Gruppe.")),
                ("max_age", models.PositiveIntegerField(help_text="Maximum age für diese Gruppe.")),
                (
                    "gender",
                    models.CharField(
                        choices=[("male", "Männlich"), ("female", "Weiblich"), ("mixed", "Gemischt")],
                        default="mixed",
                        help_text="Zielgruppe.",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True, blank=True)),
            ],
            options={
                "ordering": ["min_age", "name"],
                "verbose_name": "Altersgruppe",
                "verbose_name_plural": "Altersgruppen",
            },
        ),
        migrations.CreateModel(
            name="CompetitionSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Standard Punkte-Setup", editable=False, max_length=150)),
                (
                    "grading_system",
                    models.CharField(
                        choices=[("ifsc", "IFSC (Tops/Zones/Versuche)"), ("point_based", "Punktebasiert")],
                        default="ifsc",
                        max_length=20,
                    ),
                ),
                ("singleton_guard", models.BooleanField(default=True, editable=False, unique=True)),
                ("top_points", models.PositiveIntegerField(default=25, help_text="Punkte pro Top.")),
                (
                    "flash_points",
                    models.PositiveIntegerField(
                        default=5, help_text="Flash-Punkte (ersetzt Top-Punkte bei Top im ersten Versuch)."
                    ),
                ),
                ("min_top_points", models.PositiveIntegerField(default=0, help_text="Mindestpunkte, die ein Top immer bringt.")),
                (
                    "zone_points",
                    models.PositiveIntegerField(default=10, help_text="Punkte pro Zone (wenn nur eine Zone gewertet wird)."),
                ),
                ("zone1_points", models.PositiveIntegerField(default=10, help_text="Punkte für Zone 1 (Low Zone bei zwei Zonen).")),
                ("zone2_points", models.PositiveIntegerField(default=10, help_text="Punkte für Zone 2 (High Zone bei zwei Zonen).")),
                ("min_zone_points", models.PositiveIntegerField(default=0, help_text="Mindestpunkte, die eine Zone immer bringt.")),
                ("min_zone1_points", models.PositiveIntegerField(default=0, help_text="Mindestpunkte für Zone 1 (Low Zone).")),
                ("min_zone2_points", models.PositiveIntegerField(default=0, help_text="Mindestpunkte für Zone 2 (High Zone).")),
                ("attempt_penalty", models.PositiveIntegerField(default=1, help_text="Minuspunkte pro Versuch.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Wettkampf-Einstellung",
                "verbose_name_plural": "Wettkampf-Einstellungen",
            },
        ),
        migrations.CreateModel(
            name="Rulebook",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Regelwerk", max_length=150)),
                ("content", CKEditor5Field("Regelwerk", blank=True, config_name="default")),
                ("singleton_guard", models.BooleanField(default=True, editable=False, unique=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Regelwerk",
                "verbose_name_plural": "Regelwerke",
            },
        ),
        migrations.CreateModel(
            name="SubmissionWindow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Standard Ergebnisfenster", max_length=150)),
                (
                    "submission_start",
                    models.DateTimeField(
                        blank=True, help_text="Zeitpunkt, ab dem Ergebnisse eingetragen werden dürfen.", null=True
                    ),
                ),
                (
                    "submission_end",
                    models.DateTimeField(
                        blank=True, help_text="Zeitpunkt, bis zu dem Ergebnisse eingetragen werden dürfen.", null=True
                    ),
                ),
                ("note", models.CharField(blank=True, help_text="Interne Notiz (optional).", max_length=200)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Zeitslot für Ergebnis-Eintrag",
                "verbose_name_plural": "Zeitslots für Ergebnis-Eintrag",
            },
        ),
        migrations.CreateModel(
            name="Participant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=150, unique=True)),
                ("password", models.CharField(max_length=128)),
                ("name", models.CharField(max_length=150)),
                ("date_of_birth", models.DateField()),
                ("gender", models.CharField(choices=[("male", "Männlich"), ("female", "Weiblich"), ("mixed", "Gemischt")], max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "age_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="participants",
                        to="accounts.agegroup",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "verbose_name": "Teilnehmer*in",
                "verbose_name_plural": "Teilnehmer*innen",
            },
        ),
        migrations.CreateModel(
            name="Boulder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(help_text="Kürzel oder Nummer, z.B. B12 oder A3.", max_length=30, unique=True)),
                ("zone_count", models.PositiveSmallIntegerField(choices=[(0, "Keine Zone"), (1, "Eine Zone"), (2, "Zwei Zonen")], default=0, help_text="Anzahl der Zonen, die getickt werden können.")),
                ("color", models.CharField(help_text="Griff-/Tape-Farbe zur einfachen Zuordnung.", max_length=50)),
                ("note", models.TextField(blank=True)),
                ("location", models.CharField(blank=True, help_text="Sektor/Zone (kann später als eigenes Modell ausgegliedert werden).", max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("age_groups", models.ManyToManyField(blank=True, help_text="Wähle alle Altersgruppen, für die dieser Boulder gedacht ist.", related_name="boulders", to="accounts.agegroup")),
            ],
            options={
                "ordering": ["label"],
            },
        ),
        migrations.CreateModel(
            name="Result",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("attempts_zone1", models.PositiveIntegerField(default=0)),
                ("attempts_zone2", models.PositiveIntegerField(default=0)),
                ("attempts_top", models.PositiveIntegerField(default=0)),
                ("zone1", models.BooleanField(default=False)),
                ("zone2", models.BooleanField(default=False)),
                ("top", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("boulder", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="accounts.boulder")),
                ("participant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="accounts.participant")),
            ],
            options={
                "ordering": ["participant", "boulder"],
                "unique_together": {("participant", "boulder")},
            },
        ),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(fields=("name", "date_of_birth"), name="unique_participant_name_dob"),
        ),
        migrations.RunPython(seed_competition_settings, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(seed_rulebook, reverse_code=migrations.RunPython.noop),
    ]
