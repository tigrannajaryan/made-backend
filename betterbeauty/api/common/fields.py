import phonenumbers
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.common.constants import ErrorMessages


def remove_non_ascii(s):
    return ''.join(filter(lambda a: a.isdigit() or a == '+', s))


class PhoneNumberField(serializers.CharField):
    default_error_messages = {
        'invalid': ErrorMessages.INVALID_PHONE_NUMBER,
    }

    def to_internal_value(self, data):
        try:
            phonenumber_object = phonenumbers.parse(data, "US")
            if phonenumbers.is_possible_number(phonenumber_object):
                phone_number_to_save = remove_non_ascii(phonenumbers.format_number(
                    phonenumber_object, phonenumbers.PhoneNumberFormat.E164))
                return super(PhoneNumberField, self).to_internal_value(phone_number_to_save)
        except phonenumbers.NumberParseException:
            pass
        raise ValidationError(self.error_messages['invalid'])
