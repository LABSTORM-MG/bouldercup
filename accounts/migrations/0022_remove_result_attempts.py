from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0021_add_result_history"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="result",
            name="attempts",
        ),
        migrations.RemoveField(
            model_name="historicalresult",
            name="attempts",
        ),
    ]
