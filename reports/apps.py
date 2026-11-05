from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = 'reports'

    def ready(self):
        # Registra las senales que limpian las imagenes huerfanas.
        from . import cleanup  # noqa: F401
        # RF07: la funcion de SQLite que permite buscar sin tildes.
        from . import search  # noqa: F401
