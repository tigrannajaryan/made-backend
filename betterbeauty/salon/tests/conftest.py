import pytest

from api.v1.tests.conftest import stylist_data as stylist_data_fixture


@pytest.fixture()
def stylist_data(db):
    return stylist_data_fixture(db)
