from typing import Optional

import phonenumbers


def to_international_format(
        phone_number: str, country_code: Optional[str]='US'
):
    """
    Return phone number formatted in international format
    :param phone_number: number to format
    :param country_code: code in a form of 'US' or 'RU', or None if unknown
    :return: formatted number
    """
    if not phone_number:
        return phone_number
    return phonenumbers.format_number(
        phonenumbers.parse(phone_number, country_code),
        phonenumbers.PhoneNumberFormat.INTERNATIONAL
    )
