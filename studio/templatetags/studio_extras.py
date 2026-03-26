from django import template

from studio.services import currency


register = template.Library()


@register.filter
def money(value):
    return currency(value)
