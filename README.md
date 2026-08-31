# BackToYou

Sistema de objetos perdidos y encontrados para la comunidad EAFIT.

Django 6 · SQLite · Python 3.12+

---

## Puesta en marcha

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --demo
python manage.py runserver
```

La aplicación queda en http://127.0.0.1:8000

### Cuentas de ejemplo

`seed_demo --demo` crea dos cuentas, ambas con la contraseña `BackToYou.2026`:

| Correo | Rol |
|--------|-----|
| `demo.user@eafit.edu.co` | Usuario regular |
| `demo.admin@eafit.edu.co` | Administrador |

---

## La base de datos no se comparte por git

`db.sqlite3` y la carpeta `media/` están en `.gitignore`. Cada persona trabaja
con su propia copia local.

Un archivo SQLite es binario: si se rastreara en git, cada cambio en la base
generaría un conflicto que git no puede resolver automáticamente.

Si necesitas volver a empezar con datos limpios:

```bash
python manage.py seed_demo --demo
```

El comando es idempotente: correrlo dos veces no duplica nada. Sin `--demo`
crea únicamente el catálogo de categorías, que es lo mínimo para poder
publicar un reporte.

---

## Tests

```bash
python manage.py test --settings=backtoyou.test_settings
```

El `--settings` no es opcional en la práctica: usa un hasher de contraseñas
rápido y baja la suite de más de cinco minutos a unos tres segundos. La
aplicación sigue usando PBKDF2 en todo momento.

---

## Estructura

```
accounts/                 Registro, login y roles (RF01, RF02, RF09)
reports/
  views/
    public.py             Listado, búsqueda, detalle y contacto
    create.py             Creación de reportes
    owner.py              Acciones del creador sobre sus reportes
    moderation.py         Cola de moderación del administrador
  tests/                  Un módulo por requisito
  management/commands/    seed_demo
backtoyou/
  settings.py             Configuración
  test_settings.py        Configuración de tests
templates/                base.html, home.html, 404.html
static/css/               Hoja de estilos
```

Las vistas están separadas por responsabilidad para que dos personas puedan
trabajar en requisitos distintos sin editar el mismo archivo.

---

## Configuración para despliegue

En desarrollo no hay que configurar nada. Para desplegar, define estas
variables de entorno:

| Variable | Ejemplo |
|----------|---------|
| `DJANGO_SECRET_KEY` | una clave larga y aleatoria |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `backtoyou.eafit.edu.co` |
