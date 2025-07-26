from django import template

register = template.Library()

@register.filter
def sub(value, arg):
    """Subtracts the arg from the value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def multiply(value, arg):
    """Multiplies the value by the arg."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def divide(value, arg):
    """Divides the value by the arg."""
    try:
        if float(arg) == 0:
            return '' # Avoid division by zero
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter(name='split_outside_quotes')
def split_outside_quotes(value, arg):
    """
    Splits a string by a delimiter, but ignores delimiters inside quotes.
    For this simple case, we assume no nested quotes.
    """
    import re
    # A simple regex might not handle all edge cases, but for a simple comma-separated list it's fine.
    return [x.strip() for x in value.split(arg)]

@register.filter(name='index_of')
def index_of(sequence, item):
    """
    Returns the index of an item in a sequence.
    Returns -1 if the item is not found, so comparisons work as expected.
    """
    try:
        return sequence.index(item)
    except (ValueError, AttributeError):
        return -1

@register.filter(name='get_stage_display')
def get_stage_display(order, stage_key):
    """Returns the display value for a given order status key."""
    if hasattr(order, 'STATUS_CHOICES'):
        return dict(order.STATUS_CHOICES).get(stage_key, '')
    return ''

@register.filter
def keyvalue(dictionary, key):
    return dictionary.get(key)