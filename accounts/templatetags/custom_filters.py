from django import template

register = template.Library()

@register.filter
def split(value, separator=','):
    """Split a string into a list. Usage: {{ "a,b,c"|split:"," }}"""
    return value.split(separator)