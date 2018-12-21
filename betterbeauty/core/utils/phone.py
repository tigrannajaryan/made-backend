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


def to_e164_format(phone_number, country_code: Optional[str]='US'):
    """
    Formats input phone based on E.164 format honouring country rules
    https://en.wikipedia.org/wiki/E.164
    :param phone_number: phone to be formatted
    :param country_code: optional country code, defaults to US
    :return: Formatted number
    """
    phone = None
    try:
        phone = phonenumbers.parse(phone_number, country_code)
        if not phonenumbers.is_valid_number(phone):
            phone = None
    except phonenumbers.NumberParseException:
        pass

    if not phone:
        return phone_number

    return phonenumbers.format_number(
        phone, phonenumbers.PhoneNumberFormat.E164
    )
