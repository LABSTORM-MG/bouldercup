from django.db import migrations, models


def update_flash_points(apps, schema_editor):
    Settings = apps.get_model("accounts", "CompetitionSettings")
    Settings.objects.filter(flash_points=5).update(flash_points=30)


def revert_flash_points(apps, schema_editor):
    Settings = apps.get_model("accounts", "CompetitionSettings")
    Settings.objects.filter(flash_points=30).update(flash_points=5)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_alter_rulebook_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="competitionsettings",
            name="flash_points",
            field=models.PositiveIntegerField(
                default=30, help_text="Flash-Punkte (ersetzt Top-Punkte bei Top im ersten Versuch)."
            ),
        ),
        migrations.RunPython(update_flash_points, revert_flash_points),
    ]
