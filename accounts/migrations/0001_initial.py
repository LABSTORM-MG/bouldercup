from django.db import migrations, models
import django.db.models.deletion


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
                ("gender", models.CharField(choices=[("male", "Männlich"), ("female", "Weiblich"), ("mixed", "Gemischt")], default="mixed", help_text="Zielgruppe.", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True, blank=True)),
            ],
            options={
                "ordering": ["min_age", "name"],
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
            name="Participant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=150, unique=True)),
                ("password", models.CharField(max_length=128)),
                ("name", models.CharField(max_length=150)),
                ("date_of_birth", models.DateField()),
                ("gender", models.CharField(choices=[("male", "Männlich"), ("female", "Weiblich"), ("mixed", "Gemischt")], max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("age_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="participants", to="accounts.agegroup")),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="CompetitionSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("grading_system", models.CharField(choices=[("ifsc", "IFSC (Tops/Zones/Versuche)"), ("custom", "Punktebasiert")], default="ifsc", max_length=20)),
                ("top_points", models.PositiveIntegerField(default=25, help_text="Punkte pro Top (Custom).")),
                ("zone_points", models.PositiveIntegerField(default=10, help_text="Punkte pro Zone (Custom).")),
                ("flash_points", models.PositiveIntegerField(default=5, help_text="Zusatzpunkte bei Flash (Top im ersten Versuch, Custom).")),
                ("attempt_penalty", models.PositiveIntegerField(default=1, help_text="Minuspunkte pro Versuch (Custom).")),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Wettkampf-Einstellung",
                "verbose_name_plural": "Wettkampf-Einstellungen",
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
    ]
