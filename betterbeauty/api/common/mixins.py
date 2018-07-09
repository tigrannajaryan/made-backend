from rest_framework_friendly_errors import settings as friendly_rest_frm_settings
from rest_framework_friendly_errors.mixins import FriendlyErrorMessagesMixin

from .constants import HIGH_LEVEL_API_ERROR_CODES


class FormattedErrorMessageMixin(FriendlyErrorMessagesMixin):
    """
    Subclass of FriendlyErrorMessagesMixin with overridden
    error message building methods to support our format.
    """

    def build_pretty_errors(self, errors):
        field_errors = {}
        non_field_errors = []
        for error_type in errors:
            # if an error comes from a nested serializer - call validation
            # recursively to get formatted error messages. Nested serializer
            # must also be subclassed from the mixin
            if type(errors[error_type]) is dict:
                nested_serializer = self.fields[error_type].__class__(
                    data=self.initial_data[error_type]
                )
                nested_serializer.is_valid(raise_exception=False)
                field_errors[error_type] = nested_serializer.errors
                continue
            if error_type == 'non_field_errors':
                non_field_errors.extend(self.get_non_field_error_entries(
                    errors[error_type]))
            else:
                field = self.fields[error_type]
                field_errors[field.field_name] = self.get_field_error_entries(
                    errors[error_type], field
                )
        if field_errors or non_field_errors:
            return {
                'code': HIGH_LEVEL_API_ERROR_CODES[400],
                'field_errors': field_errors,
                'non_field_errors': non_field_errors
            }
        return {}

    def get_field_error_entry(self, error, field):
        if error in self.registered_errors:
            return self.registered_errors[error]

        # Find serializer's error key (e.g. "required") by formatted message. If
        # found - return key. If not found - return message as is (it's coming from
        # custom validator, so should be appropriately formatted already)

        try:
            key = self.find_key(field, error, field.field_name)
        except KeyError:
            key = None
        if key:
            return {'code': key}
        return {'code': error}

    def get_non_field_error_entry(self, error):
        if error in self.registered_errors:
            return self.registered_errors[error]

        # special case for invalid format on nested serializer
        if friendly_rest_frm_settings.INVALID_DATA_MESSAGE.format(
                data_type=type(self.initial_data).__name__) == error:
            return {'code': 'invalid'}
        return {'code': error}
