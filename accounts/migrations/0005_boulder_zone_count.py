from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_boulder_age_groups"),
    ]

    operations = [
        migrations.AddField(
            model_name="boulder",
            name="zone_count",
            field=models.PositiveSmallIntegerField(
                choices=[(0, "Keine Zone"), (1, "Eine Zone"), (2, "Zwei Zonen")],
                default=0,
                help_text="Anzahl der Zonen, die getickt werden können.",
            ),
        ),
    ]
