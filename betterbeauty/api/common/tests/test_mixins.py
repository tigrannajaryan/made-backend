from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.common.mixins import FormattedErrorMessageMixin


class NestedSerializerBase(serializers.Serializer):
    """Sample nested serializer declared solely for test purposes"""
    int_field = serializers.IntegerField()
    custom_field = serializers.CharField(required=True)
    list_field = serializers.ListField(
        child=serializers.IntegerField()
    )

    class Meta:
        fields = ['int_field', 'custom_field', 'list_field', ]

    def validate(self, attrs):
        if attrs['custom_field'] == 'raise_non_field_error':
            raise ValidationError('nested-non-field-error')
        return attrs

    def validate_custom_field(self, s):
        if s == 'raise_field_error':
            raise ValidationError('nested-field-error')
        if s == 'raise_multiple_field_errors':
            raise ValidationError(['nested-field-error-1', 'nested-field-error-2'])
        return s


class NestedSerializerWithFormatting(FormattedErrorMessageMixin, NestedSerializerBase):
    """Sample nested serializer with formatting declared solely for test purposes"""
    pass


class MainSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    """Sample parent serializer declared solely for test purposes"""
    int_field = serializers.IntegerField()
    custom_field = serializers.CharField()
    list_field = serializers.ListField(
        child=serializers.IntegerField()
    )
    nested_field = NestedSerializerWithFormatting()
    nested_list_field = NestedSerializerWithFormatting(many=True)

    nested_field_unformatted = NestedSerializerBase()
    nested_list_field_unformatted = NestedSerializerBase(many=True)

    def validate(self, attrs):
        data = self.initial_data
        if data['custom_field'] == 'raise_non_field_error':
            raise ValidationError('parent-non-field-error')
        if data['custom_field'] == 'override_list_fields':
            raise ValidationError({
                'nested_list_field': 'parent_overridden',
                'nested_list_field_unformatted': 'parent_overridden',
            })
        return attrs

    def validate_custom_field(self, s):
        if s == 'raise_field_error':
            raise ValidationError('parent-field-error')
        if s == 'raise_multiple_field_errors':
            raise ValidationError(['parent-field-error-1', 'parent-field-error-2'])
        return s

    class Meta:
        fields = ['int_field', 'custom_field', 'nested_field', 'nested_list_field']


class TestFormattedErrorMessageMixin(object):

    def test_plain_serializer_with_drf_error(self):
        data = {
            'custom_field': 'something',
            'list_field': [],
            'nested_field': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_list_field': [],
            'nested_list_field_unformatted': []
        }
        serializer = MainSerializer(data=data)
        assert(not serializer.is_valid(raise_exception=False))
        assert(serializer.errors['non_field_errors'] == [])
        assert(serializer.errors['field_errors'] == {
            'int_field': [
                {'code': 'required'}
            ]
        })

    def test_plain_serializer_with_list_error(self):
        data = {
            'int_field': 1,
            'custom_field': 'something',
            'list_field': [1, 2, 'a', ],
            'nested_field': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_list_field': [],
            'nested_list_field_unformatted': []
        }
        serializer = MainSerializer(data=data)
        assert (not serializer.is_valid(raise_exception=False))
        assert (serializer.errors['non_field_errors'] == [])
        assert (serializer.errors['field_errors'] == {
            'list_field': [
                {'code': 'invalid'}
            ]
        })

        data = {
            'int_field': 1,
            'custom_field': 'something',
            'list_field': 'not a list',
            'nested_field': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_list_field': [],
            'nested_list_field_unformatted': []
        }
        serializer = MainSerializer(data=data)
        assert (not serializer.is_valid(raise_exception=False))
        assert (serializer.errors['non_field_errors'] == [])
        assert (serializer.errors['field_errors'] == {
            'list_field': [
                {'code': 'not_a_list'}
            ]
        })

    def test_plain_serializer_with_custom_error(self):
        data = {
            'int_field': 1,
            'custom_field': 'raise_field_error',
            'list_field': [],
            'nested_field': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_list_field': [],
            'nested_list_field_unformatted': []
        }
        serializer = MainSerializer(data=data)
        assert (not serializer.is_valid(raise_exception=False))
        assert (serializer.errors['non_field_errors'] == [])
        assert (serializer.errors['field_errors'] == {
            'custom_field': [
                {'code': 'parent-field-error'}
            ]
        })

        data = {
            'int_field': 1,
            'custom_field': 'raise_multiple_field_errors',
            'list_field': [],
            'nested_field': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_list_field': [],
            'nested_list_field_unformatted': []
        }
        serializer = MainSerializer(data=data)
        assert(not serializer.is_valid(raise_exception=False))
        assert(serializer.errors['non_field_errors'] == [])
        assert(
            frozenset(
                [e['code'] for e in serializer.errors['field_errors']['custom_field']]
            ) == frozenset(['parent-field-error-1', 'parent-field-error-2'])
        )

    def test_plain_serializer_with_non_field_custom_error(self):
        data = {
            'int_field': 1,
            'custom_field': 'raise_non_field_error',
            'list_field': [],
            'nested_field': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_list_field': [],
            'nested_list_field_unformatted': []
        }
        serializer = MainSerializer(data=data)
        assert(not serializer.is_valid(raise_exception=False))
        assert(serializer.errors['field_errors'] == {})
        assert(serializer.errors['non_field_errors'] == [{'code': 'parent-non-field-error'}, ])

    def test_nested_serializer_with_drf_and_custom_errors(self):
        data = {
            'int_field': 1,
            'custom_field': 'something',
            'list_field': [],
            'nested_field': {
                'custom_field': 'raise_multiple_field_errors',
                'list_field': [1, 2, 'a']
            },
            'nested_field_unformatted': {
                'custom_field': 'raise_multiple_field_errors',
                'list_field': [1, 2, 'a']
            },
            'nested_list_field': [],
            'nested_list_field_unformatted': []
        }
        serializer = MainSerializer(data=data)
        assert (not serializer.is_valid(raise_exception=False))
        assert (serializer.errors['non_field_errors'] == [])
        assert (serializer.errors['field_errors'] == {
            'nested_field': {
                'code': 'err_api_exception',
                'field_errors': {
                    'custom_field': [
                        {'code': 'nested-field-error-1'},
                        {'code': 'nested-field-error-2'}
                    ],
                    'int_field': [{'code': 'required'}],
                    'list_field': [{'code': 'invalid'}]
                },
                'non_field_errors': []
            },
            'nested_field_unformatted': {
                'code': 'err_api_exception',
                'field_errors': {
                    'custom_field': [
                        {'code': 'nested-field-error-1'},
                        {'code': 'nested-field-error-2'}
                    ],
                    'int_field': [{'code': 'required'}],
                    'list_field': [{'code': 'invalid'}]
                },
                'non_field_errors': []
            },
        })

    def test_nested_list_serializer_with_drf_and_custom_error(self):
        data = {
            'int_field': 1,
            'custom_field': 'something',
            'list_field': [],
            'nested_field': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_list_field': [
                {
                    'custom_field': 'raise_multiple_field_errors',
                    'list_field': [1, 2, 'a']
                },
                {
                    'int_field': 1,
                    'custom_field': 'something',
                    'list_field': []
                },
                {
                    'custom_field': 'raise_multiple_field_errors',
                    'list_field': [1, 2, 'a']
                }
            ],
            'nested_list_field_unformatted': [
                {
                    'custom_field': 'raise_multiple_field_errors',
                    'list_field': [1, 2, 'a']
                },
                {
                    'int_field': 1,
                    'custom_field': 'something',
                    'list_field': []
                },
                {
                    'custom_field': 'raise_multiple_field_errors',
                    'list_field': [1, 2, 'a']
                }
            ]
        }

        serializer = MainSerializer(data=data)
        assert (not serializer.is_valid(raise_exception=False))
        assert (serializer.errors['non_field_errors'] == [])
        assert (serializer.errors['field_errors'] == {
            'nested_list_field': [
                {
                    'code': 'err_api_exception',
                    'field_errors': {
                        'custom_field': [
                            {'code': 'nested-field-error-1'},
                            {'code': 'nested-field-error-2'}
                        ],
                        'int_field': [{'code': 'required'}],
                        'list_field': [{'code': 'invalid'}]
                    },
                    'non_field_errors': []
                },
                {},  # no error in this element
                {
                    'code': 'err_api_exception',
                    'field_errors': {
                        'custom_field': [
                            {'code': 'nested-field-error-1'},
                            {'code': 'nested-field-error-2'}
                        ],
                        'int_field': [{'code': 'required'}],
                        'list_field': [{'code': 'invalid'}]
                    },
                    'non_field_errors': []
                }
            ],
            'nested_list_field_unformatted': [
                {
                    'code': 'err_api_exception',
                    'field_errors': {
                        'custom_field': [
                            {'code': 'nested-field-error-1'},
                            {'code': 'nested-field-error-2'}
                        ],
                        'int_field': [{'code': 'required'}],
                        'list_field': [{'code': 'invalid'}]
                    },
                    'non_field_errors': []
                },
                {},  # no error in this element
                {
                    'code': 'err_api_exception',
                    'field_errors': {
                        'custom_field': [
                            {'code': 'nested-field-error-1'},
                            {'code': 'nested-field-error-2'}
                        ],
                        'int_field': [{'code': 'required'}],
                        'list_field': [{'code': 'invalid'}]
                    },
                    'non_field_errors': []
                }
            ]
        })

    def test_nested_list_serializer_with_parent_override(self):
        # Verify, that parent serializer can completely override
        # nested serializer's validation (this is effectively what we're doing
        # with service validation in AppointmentMixin
        data = {
            'int_field': 1,
            'custom_field': 'override_list_fields',
            'list_field': [],
            'nested_field': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 1,
                'custom_field': 'something',
                'list_field': []
            },
            'nested_list_field': [
                {
                    'int_field': 1,
                    'custom_field': 'something',
                    'list_field': []
                },
                {
                    'int_field': 1,
                    'custom_field': 'something',
                    'list_field': []
                }
            ],
            'nested_list_field_unformatted': [
                {
                    'int_field': 1,
                    'custom_field': 'something',
                    'list_field': []
                }
            ]
        }

        serializer = MainSerializer(data=data)
        assert (not serializer.is_valid(raise_exception=False))
        assert (serializer.errors['non_field_errors'] == [])
        assert (serializer.errors['field_errors'] == {
            'nested_list_field': [{'code': 'parent_overridden'}],
            'nested_list_field_unformatted': [{'code': 'parent_overridden'}]
        })

    def test_nested_serializer_with_non_field_custom_error(self):
        data = {
            'int_field': 1,
            'custom_field': 'something',
            'list_field': [],
            'nested_field': {
                'int_field': 3,
                'custom_field': 'raise_non_field_error',
                'list_field': []
            },
            'nested_field_unformatted': {
                'int_field': 4,
                'custom_field': 'raise_non_field_error',
                'list_field': []
            },
            'nested_list_field': [
                {
                    'int_field': 5,
                    'custom_field': 'raise_non_field_error',
                    'list_field': []
                }
            ],
            'nested_list_field_unformatted': [
                {
                    'int_field': 6,
                    'custom_field': 'raise_non_field_error',
                    'list_field': []
                }
            ]
        }
        serializer = MainSerializer(data=data)
        assert (not serializer.is_valid(raise_exception=False))
        assert(serializer.errors['field_errors'] == {
            'nested_field': {
                'code': 'err_api_exception',
                'field_errors': {},
                'non_field_errors': [
                    {'code': 'nested-non-field-error'}
                ]
            },
            'nested_field_unformatted': {
                'code': 'err_api_exception',
                'field_errors': {},
                'non_field_errors': [
                    {'code': 'nested-non-field-error'}
                ]
            },
            'nested_list_field': [
                {
                    'code': 'err_api_exception',
                    'field_errors': {},
                    'non_field_errors': [
                        {'code': 'nested-non-field-error'}
                    ]
                }
            ],
            'nested_list_field_unformatted': [
                {
                    'code': 'err_api_exception',
                    'field_errors': {},
                    'non_field_errors': [
                        {'code': 'nested-non-field-error'}
                    ]
                }
            ]
        })
