from django import template

from core.utils.phone import to_international_format

register = template.Library()


@register.filter
def to_international(value, arg):
    """
    Simple template filter to format phone number in international format, e.g.
        {{ stylist.phone_number|to_international }}  or
        {{ stylist.phone_number|to_international:stylist.salon.country }}

    :param value: value of phone to format
    :param arg: optional country code
    :return: formatted phone
    """
    return to_international_format(phone_number=value, country_code=arg)
