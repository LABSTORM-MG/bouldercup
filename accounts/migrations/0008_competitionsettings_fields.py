from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_competitionsettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="competitionsettings",
            name="attempt_penalty",
            field=models.PositiveIntegerField(default=1, help_text="Minuspunkte pro Versuch (Custom)."),
        ),
        migrations.AddField(
            model_name="competitionsettings",
            name="flash_points",
            field=models.PositiveIntegerField(default=5, help_text="Zusatzpunkte bei Flash (Top im ersten Versuch, Custom)."),
        ),
        migrations.AddField(
            model_name="competitionsettings",
            name="top_points",
            field=models.PositiveIntegerField(default=25, help_text="Punkte pro Top (Custom)."),
        ),
        migrations.AddField(
            model_name="competitionsettings",
            name="zone_points",
            field=models.PositiveIntegerField(default=10, help_text="Punkte pro Zone (Custom)."),
        ),
    ]
