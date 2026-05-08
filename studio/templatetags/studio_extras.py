from django import template

from studio.services import currency


register = template.Library()


@register.filter
def money(value):
    return currency(value)


@register.filter
def get_item(mapping, key):
    """Permite indexar dicts dentro de templates Django (ex.: dict|get_item:variavel)."""
    if mapping is None:
        return None
    try:
        return mapping[key]
    except (KeyError, TypeError):
        return None
