from django.apps import AppConfig


class DemonstrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'demonstration'

    def ready(self):
        from django.conf import settings
        if settings.MONKEYPATCH_OPTIMIZER:
            import strawberry_django_plus.optimizer
            from . import optimizer_monkeypatch
            strawberry_django_plus.optimizer._get_model_hints = optimizer_monkeypatch.custom_get_model_hints


