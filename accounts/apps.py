from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_migrate

        def ensure_superuser(**_):
            User = get_user_model()
            if not User.objects.filter(username="labstorm").exists():
                User.objects.create_superuser(
                    username="labstorm",
                    email="labstorm@example.com",
                    password="PasswordTest123",
                )

        post_migrate.connect(
            ensure_superuser,
            sender=self,
            dispatch_uid="accounts.ensure_superuser",
        )

        from . import signals  # noqa: F401
