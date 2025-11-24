from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AgeGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150, unique=True)),
                (
                    "min_age",
                    models.PositiveIntegerField(
                        help_text="Minimum age für diese Gruppe."
                    ),
                ),
                (
                    "max_age",
                    models.PositiveIntegerField(
                        help_text="Maximum age für diese Gruppe."
                    ),
                ),
                (
                    "gender",
                    models.CharField(
                        choices=[
                            ("male", "Männlich"),
                            ("female", "Weiblich"),
                            ("mixed", "Gemischt"),
                        ],
                        default="mixed",
                        help_text="Zielgruppe.",
                        max_length=10,
                    ),
                ),
            ],
            options={
                "ordering": ["min_age", "name"],
            },
        ),
        migrations.CreateModel(
            name="Participant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("username", models.CharField(max_length=150, unique=True)),
                ("password", models.CharField(max_length=128)),
                ("name", models.CharField(max_length=150)),
                ("date_of_birth", models.DateField()),
                (
                    "gender",
                    models.CharField(
                        choices=[
                            ("male", "Männlich"),
                            ("female", "Weiblich"),
                            ("mixed", "Gemischt"),
                        ],
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "age_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.PROTECT,
                        related_name="participants",
                        to="accounts.agegroup",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(
                fields=("name", "date_of_birth"),
                name="unique_participant_name_dob",
            ),
        ),
    ]
