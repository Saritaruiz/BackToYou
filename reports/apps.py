from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = 'reports'

    def ready(self):
        # Registra las senales que limpian las imagenes huerfanas.
        from . import cleanup  # noqa: F401
