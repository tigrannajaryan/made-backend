from rest_framework.serializers import BaseSerializer

from rest_framework_friendly_errors import settings as friendly_rest_frm_settings
from rest_framework_friendly_errors.mixins import FriendlyErrorMessagesMixin

from .constants import HIGH_LEVEL_API_ERROR_CODES


class FormattedErrorMessageMixin(FriendlyErrorMessagesMixin):
    """
    Subclass of FriendlyErrorMessagesMixin with overridden
    error message building methods to support our format.
    """
    @staticmethod
    def _formatted_mixin_serializer_factory(serializer_class):
        """Return serializer class with added friendly format mixing"""

        class WithFormatMixinClass(FormattedErrorMessageMixin, serializer_class):
            pass

        assert issubclass(serializer_class, BaseSerializer)
        return WithFormatMixinClass

    def build_pretty_errors(self, errors):
        field_errors = {}
        non_field_errors = []

        for error_type in errors:

            # if an error comes from a nested serializer - call validation
            # recursively to get formatted error messages. If nested serializer
            # is not a subclass of FormattedErrorMessageMixin - build new class
            # with mixin
            if type(errors[error_type]) is dict and issubclass(
                    self.fields[error_type].__class__, BaseSerializer
            ):
                NestedFieldClass = self.fields[error_type].__class__

                if not issubclass(NestedFieldClass, FormattedErrorMessageMixin):
                    # add formatting mixin to serializer's class
                    NestedFieldClass = self._formatted_mixin_serializer_factory(
                        NestedFieldClass
                    )
                nested_serializer = NestedFieldClass(
                    data=self.initial_data[error_type]
                )
                if not nested_serializer.is_valid(raise_exception=False):
                    # merge nested serializer's field_errors into current field
                    field_errors[error_type] = nested_serializer.errors
                continue

            if error_type == 'non_field_errors':
                non_field_errors.extend(self.get_non_field_error_entries(
                    errors[error_type]))
            else:
                field = self.fields[error_type]
                field_errors[field.field_name] = self.get_field_error_entries(
                    errors[error_type], field, error_type
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

    def find_key(self, field, message, field_name):
        kwargs = self.get_field_kwargs(
            field, self.initial_data.get(field_name)
        )
        for key in field.error_messages:
            if (
                key == 'does_not_exist' and
                isinstance(kwargs.get('value'), list) and
                self.does_not_exist_many_to_many_handler(field, message, kwargs)
            ):
                return key
            unformatted = field.error_messages[key]
            if unformatted.format(**kwargs) == message:
                return key
        if getattr(field, 'child_relation', None):
            return self.find_key(field=field.child_relation, message=message,
                                 field_name=field_name)
        if getattr(field, 'child', None):
            return self.find_key(field=field.child, message=message,
                                 field_name=field_name)
        return None

    def get_field_error_entries(self, errors, field, field_name):
        from rest_framework.serializers import BaseSerializer
        if hasattr(field, 'child') and isinstance(field, BaseSerializer) and errors:
            # if this is a list of dicts - this means that errors are coming from
            # nested serializers' validation. Otherwise, this is an error enforced
            # by the parent serializer; alas, we can't process it so we'll just pass it through
            if (
                isinstance(errors, list) and isinstance(errors[0], dict) and
                len(errors) == len(self.data[field_name])
            ):
                # this is a many=True serializer with no parent-forced error
                ChildSerializerClass = field.child.__class__
                if not issubclass(ChildSerializerClass, FormattedErrorMessageMixin):
                    ChildSerializerClass = self._formatted_mixin_serializer_factory(
                        ChildSerializerClass
                    )
                return [
                    ChildSerializerClass(data=data_item).build_pretty_errors(list_element_errors)
                    for list_element_errors, data_item in zip(errors, self.data[field_name])
                ]
        return [self.get_field_error_entry(error, field) for error in errors]
