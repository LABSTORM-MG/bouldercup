from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_merge_competitionsettings_result"),
    ]

    operations = [
        migrations.AddField(
            model_name="agegroup",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
