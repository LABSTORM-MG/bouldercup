from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetitionSettingsProxy",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
                "verbose_name": "Punktesystem",
                "verbose_name_plural": "Punktesysteme",
            },
            bases=("accounts.competitionsettings",),
        ),
        migrations.CreateModel(
            name="SubmissionWindowProxy",
            fields=[],
            options={
                "proxy": True,
                "indexes": [],
                "constraints": [],
                "verbose_name": "Zeitslot",
                "verbose_name_plural": "Zeitslots",
            },
            bases=("accounts.submissionwindow",),
        ),
    ]
