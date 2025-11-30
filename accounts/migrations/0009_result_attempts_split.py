from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_competitionsettings_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="result",
            name="attempts_zone1",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="result",
            name="attempts_zone2",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="result",
            name="attempts_top",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
