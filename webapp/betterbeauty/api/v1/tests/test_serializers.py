import pytest

from api.v1 import serializers


@pytest.fixture
def test_data():
    return {
        'foo': 'my test string',
        'bar': 15
    }


# generic test function to verify pytest
def test_test_serializer(test_data):
    s = serializers.TestSerializer(
        data=test_data
    )
    s.is_valid()
    data = s.validated_data

    assert(data['foo'] == 'my test string')
    assert(data['bar'] == 15)
