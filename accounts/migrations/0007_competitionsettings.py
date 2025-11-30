from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_result"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetitionSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "grading_system",
                    models.CharField(
                        choices=[("ifsc", "IFSC (Tops/Zones/Versuche)"), ("custom", "Custom")],
                        default="ifsc",
                        max_length=20,
                    ),
                ),
                ("singleton", models.BooleanField(default=True, editable=False, unique=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Wettkampf-Einstellung",
                "verbose_name_plural": "Wettkampf-Einstellungen",
            },
        ),
    ]
