from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_boulder_zone_count"),
    ]

    operations = [
        migrations.CreateModel(
            name="Result",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("zone1", models.BooleanField(default=False)),
                ("zone2", models.BooleanField(default=False)),
                ("top", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "boulder",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="accounts.boulder",
                    ),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="results",
                        to="accounts.participant",
                    ),
                ),
            ],
            options={
                "ordering": ["participant", "boulder"],
                "unique_together": {("participant", "boulder")},
            },
        ),
    ]
