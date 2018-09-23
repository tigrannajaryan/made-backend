import datetime
from typing import Tuple

import pytest
import pytz
from django.contrib.gis.geos import Point

from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework_jwt.settings import api_settings

from api.v1.auth.utils import create_client_profile_from_phone

from client.models import Client
from core.choices import USER_ROLE
from core.models import PhoneSMSCodes, User
from core.types import UserRole, Weekday
from salon.models import Salon, Stylist
from salon.utils import create_stylist_profile_for_user


@pytest.fixture()
def stylist_data(db) -> Stylist:
    salon = G(
        Salon,
        name='Test salon', address='2000 Rilma Lane', city='Los Altos', state='CA',
        zip_code='94022', location=Point(x=-122.1185007, y=37.4009997),
        timezone=pytz.utc
    )
    stylist_user = G(
        User,
        is_staff=False, is_superuser=False, email='test_stylist@example.com',
        first_name='Fred', last_name='McBob', phone='(650) 350-1111'
    )
    stylist: Stylist = create_stylist_profile_for_user(
        stylist_user,
        salon=salon,
        service_time_gap=datetime.timedelta(minutes=30)
    )
    monday_discount = stylist.get_or_create_weekday_discount(
        weekday=Weekday.MONDAY
    )
    monday_discount.discount_percent = 50
    monday_discount.save()
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


@pytest.fixture
def authorized_client_user(client) -> Tuple[User, str]:
    user = create_client_profile_from_phone('+19876543210')
    code = PhoneSMSCodes.create_or_update_phone_sms_code('+19876543210')
    auth_url = reverse('api:v1:auth:verify-code')
    data = client.post(
        auth_url, data={
            'phone': '+19876543210',
            'code': code.code,
        }
    ).data
    token = data['token']
    auth_token = 'Token {0}'.format(token)
    return user, auth_token


@pytest.fixture
def authorized_stylist_user(client) -> Tuple[User, str]:
    user = G(
        User,
        role=[UserRole.STYLIST, ]
    )
    create_stylist_profile_for_user(user)
    jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
    jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
    payload = jwt_payload_handler(user)
    token = jwt_encode_handler(payload)
    auth_token = 'Token {0}'.format(token)
    return user, auth_token
