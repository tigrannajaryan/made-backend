import pytest
import pytz
from django_dynamic_fixture import G

from api.v1.auth.utils import create_client_profile_from_phone
from client.models import Client
from core.choices import USER_ROLE
from core.models import User
from salon.models import Salon, Stylist
from salon.utils import create_stylist_profile_for_user


@pytest.fixture()
def stylist_data(db) -> Stylist:
    salon = G(
        Salon,
        name='Test salon', address='2000 Rilma Lane', city='Los Altos', state='CA',
        zip_code='94022', latitude=37.4009997, longitude=-122.1185007, timezone=pytz.utc
    )

    stylist_user = G(
        User,
        is_staff=False, is_superuser=False, email='test_stylist@example.com',
        first_name='Fred', last_name='McBob', phone='(650) 350-1111',
        role=[USER_ROLE.stylist],
    )

    stylist = create_stylist_profile_for_user(
        stylist_user,
        salon=salon,
    )

    return stylist


@pytest.fixture()
def client_data(db) -> Client:
    user = G(
        User,
        is_staff=False, is_superuser=False, email='test_client@example.com',
        first_name='Fred', last_name='McBob', phone='+11234567890',
        role=[USER_ROLE.client],
    )
    client_user = create_client_profile_from_phone(phone='+11234567890', user=user)

    return client_user.client
