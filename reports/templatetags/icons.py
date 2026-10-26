"""NFR37 - Iconos de categoria y de la interfaz.

Los iconos de categoria son los del manual de marca (seccion 6,
"Iconografia BackToYou"): lineales, trazo de 1.5 px y esquinas redondeadas
sobre una cuadricula de 24 x 24, en Salvia, con un solo detalle relleno en
Ciruela suave (clase icon-fill). Van en linea para que tomen el color del texto.
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _svg(body, kind, grid):
    return mark_safe(
        f'<svg class="icon {kind}" viewBox="0 0 {grid} {grid}" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{body}</svg>'
    )


# Manual de marca: cuadricula de 24 x 24.
CATEGORY_ICONS = {
    "electronics": '<rect class="icon-fill" x="4.5" y="5" width="15" height="11" rx="1.5"/>'
                   '<path d="M2.5 18h19"/>',
    "card": '<circle class="icon-fill" cx="8.5" cy="11.5" r="3" stroke="none"/>'
            '<rect x="3" y="5.5" width="18" height="13" rx="2.5"/>'
            '<circle cx="8.5" cy="10.5" r="1.75"/>'
            '<path d="M6 15.5c.6-1.6 1.5-2.4 2.5-2.4s1.9.8 2.5 2.4"/>'
            '<path d="M14 10h4.5M14 13.5h3.5"/>',
    "bottle": '<path class="icon-fill" d="M8 13h8v7a1.5 1.5 0 0 1-1.5 1.5h-5A1.5 1.5 0 0 1 8 20z" stroke="none"/>'
              '<rect x="10" y="2.5" width="4" height="2.5" rx=".5"/>'
              '<path d="M10.5 5v2.3C9 8.2 8 9.8 8 11.5v8.5A1.5 1.5 0 0 0 9.5 21.5h5a1.5 1.5 0 0 0 1.5-1.5v-8.5'
              'c0-1.7-1-3.3-2.5-4.2V5"/><path d="M8 13h8"/>',
    "clothing": '<path class="icon-fill" d="M9 4.5c.6 1.2 1.7 1.9 3 1.9s2.4-.7 3-1.9z" stroke="none"/>'
                '<rect class="icon-fill" x="13.5" y="9.5" width="2" height="2" rx=".4" stroke="none"/>'
                '<path d="M9 4.5 4 7l1.5 4.5L8 10.5v10h8v-10l2.5 1L20 7l-5-2.5c-.6 1.2-1.7 1.9-3 1.9s-2.4-.7-3-1.9z"/>',
    "bag": '<path d="M10 4.5V3.5a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1"/>'
           '<path d="M6 10.5A6 6 0 0 1 12 4.5a6 6 0 0 1 6 6v9a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2z"/>'
           '<rect class="icon-fill" x="8.5" y="13" width="7" height="4.5" rx="1.5"/>',
    "keys": '<circle class="icon-fill" cx="6.5" cy="12" r="4"/>'
            '<circle cx="6.5" cy="12" r="1.25"/>'
            '<path d="M10.5 12h11M16.5 12v3M19.5 12v2.5"/>',
    "book": '<rect x="5" y="3" width="14" height="18" rx="1.5"/>'
            '<path d="M8 3v18"/>'
            '<path class="icon-fill" d="M13.5 3v5.5l1.5-1.2 1.5 1.2V3"/>',
    "glasses": '<circle class="icon-fill" cx="7" cy="14.5" r="3.5"/>'
               '<circle class="icon-fill" cx="17" cy="14.5" r="3.5"/>'
               '<path d="M10.5 14c1-1 2-1 3 0M3.5 13.5 3 10.5M20.5 13.5l.5-3"/>',
    "tag": '<path class="icon-fill" d="M12.5 6H9l-5.5 6 5.5 6h3.5z" stroke="none"/>'
           '<path d="M21 7.5v9a1.5 1.5 0 0 1-1.5 1.5H9l-5.5-6L9 6h10.5A1.5 1.5 0 0 1 21 7.5z"/>'
           '<circle cx="8.75" cy="12" r="1.25"/><path d="M13.5 10.5h4M13.5 13.5h3"/>',
    # "Todas las categorias" en el filtro del indice.
    "all": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/>'
           '<rect x="4" y="13" width="7" height="7" rx="1.5"/><rect class="icon-fill" x="13" y="13" width="7" height="7" rx="1.5"/>',
}

# Iconos de la interfaz (entrega segura, buscador): cuadricula de 64 x 64.
UI_ICONS = {
    "search": '<circle cx="27" cy="27" r="15"/><path d="M38 38l14 14"/>',
    "shield": '<path d="M32 8l20 7v14c0 13-9 22-20 27C21 51 12 42 12 29V15z"/>'
              '<path class="icon-accent-line" d="M24 32l6 6 11-12"/>',
    "check": '<circle cx="32" cy="32" r="22"/><path class="icon-accent-line" d="M22 33l7 7 14-15"/>',
    "chat": '<path d="M10 14h44v28H28l-10 9v-9h-8z"/><path class="icon-accent-line" d="M20 25h24M20 32h16"/>',
}

# Palabras de cada categoria por defecto (seed_categories) y de los datos de
# prueba. Una categoria nueva sin icono propio usa el de "Other".
CATEGORY_KEYWORDS = (
    ("electr", "electronics"),
    ("card", "card"),
    ("document", "card"),
    ("bottle", "bottle"),
    ("cloth", "clothing"),
    ("bag", "bag"),
    ("key", "keys"),
    ("book", "book"),
    ("notebook", "book"),
    ("accessor", "glasses"),
)


def icon_for_category(name):
    name = (name or "").lower()
    for keyword, icon in CATEGORY_KEYWORDS:
        if keyword in name:
            return icon
    return "tag"


@register.simple_tag
def category_icon(name):
    return _svg(CATEGORY_ICONS[icon_for_category(name)], "category-icon", 24)


@register.simple_tag
def all_categories_icon():
    return _svg(CATEGORY_ICONS["all"], "category-icon", 24)


@register.simple_tag
def ui_icon(name):
    return _svg(UI_ICONS[name], "ui-icon", 64)
