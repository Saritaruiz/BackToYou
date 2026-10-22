"""NFR37 - Iconos de categoria y de la interfaz.

Iconos lineales del manual de marca: trazo de 1.5 px y un detalle relleno en
Ciruela (clase icon-accent). Van en linea para que tomen el color del texto.
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _svg(body):
    return mark_safe(
        '<svg class="icon" viewBox="0 0 64 64" fill="none" stroke="currentColor" '
        'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{body}</svg>'
    )


ICONS = {
    "laptop": '<rect x="14" y="16" width="36" height="24" rx="2"/><path d="M8 44h48l-4 6H12z"/>'
              '<circle class="icon-accent" cx="32" cy="19.5" r="1.6"/>',
    "card": '<rect x="9" y="16" width="46" height="32" rx="4"/>'
            '<rect class="icon-accent" x="15" y="23" width="13" height="16" rx="2"/>'
            '<path d="M33 26h16M33 32h16M33 38h10"/>',
    "bottle": '<rect class="icon-accent" x="26" y="7" width="12" height="7" rx="1.5"/>'
              '<path d="M27 14h10v5c4 3 6 7 6 12v21a4 4 0 0 1-4 4H25a4 4 0 0 1-4-4V31c0-5 2-9 6-12z"/>'
              '<path d="M21 34h22M21 44h22"/>',
    "hoodie": '<path d="M22 12l-10 6 4 10 6-3v27h20V25l6 3 4-10-10-6c-2 4-6 6-10 6s-8-2-10-6z"/>'
              '<rect class="icon-accent" x="27" y="38" width="10" height="7" rx="2"/>',
    "backpack": '<path d="M26 16v-3a6 6 0 0 1 12 0v3"/><rect x="16" y="16" width="32" height="40" rx="9"/>'
                '<rect x="22" y="38" width="20" height="12" rx="3"/><path d="M22 28h20"/>'
                '<circle class="icon-accent" cx="32" cy="44" r="2"/>',
    "keys": '<circle cx="22" cy="22" r="11"/><circle class="icon-accent" cx="22" cy="22" r="4"/>'
            '<path d="M30 30l22 22M44 44l5-5M48 48l5-5"/>',
    "book": '<path d="M32 18c-6-4-14-5-22-4v32c8-1 16 0 22 4c6-4 14-5 22-4V14c-8-1-16 0-22 4z"/>'
            '<path d="M32 18v32"/><path class="icon-accent" d="M40 19v11l3-2 3 2V18z"/>',
    "sunglasses": '<circle cx="20" cy="34" r="9"/><circle class="icon-accent" cx="44" cy="34" r="9"/>'
                  '<path d="M29 32q3-3 6 0M11 32l-4-9M53 32l4-9"/>',
    "tag": '<path d="M10 12h22l24 24-20 20-26-26z"/><circle class="icon-accent" cx="21" cy="23" r="4"/>',
    "search": '<circle cx="27" cy="27" r="15"/><path d="M38 38l14 14"/>',
    "shield": '<path d="M32 8l20 7v14c0 13-9 22-20 27C21 51 12 42 12 29V15z"/>'
              '<path class="icon-accent-line" d="M24 32l6 6 11-12"/>',
    "check": '<circle cx="32" cy="32" r="22"/><path class="icon-accent-line" d="M22 33l7 7 14-15"/>',
    "chat": '<path d="M10 14h44v28H28l-10 9v-9h-8z"/><path class="icon-accent-line" d="M20 25h24M20 32h16"/>',
}

# Palabras de cada categoria por defecto (seed_categories) y de los datos de
# prueba. Una categoria nueva sin icono propio usa el de "Other".
CATEGORY_KEYWORDS = (
    ("electr", "laptop"),
    ("card", "card"),
    ("document", "card"),
    ("bottle", "bottle"),
    ("cloth", "hoodie"),
    ("bag", "backpack"),
    ("key", "keys"),
    ("book", "book"),
    ("notebook", "book"),
    ("accessor", "sunglasses"),
)


def icon_for_category(name):
    name = (name or "").lower()
    for keyword, icon in CATEGORY_KEYWORDS:
        if keyword in name:
            return icon
    return "tag"


@register.simple_tag
def category_icon(name):
    return _svg(ICONS[icon_for_category(name)])


@register.simple_tag
def ui_icon(name):
    return _svg(ICONS[name])
