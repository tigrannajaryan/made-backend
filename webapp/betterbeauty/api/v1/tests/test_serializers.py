import datetime
import pytest
import pytz

from psycopg2.extras import DateRange

from django_dynamic_fixture import G

from api.v1.stylist.serializers import (
    StylistSerializer,
    StylistServiceSerializer,
    StylistProfileStatusSerializer,
)
from core.choices import USER_ROLE
from core.models import User
from salon.models import (
    Salon,
    Stylist,
    StylistAvailableDay,
    StylistDateRangeDiscount,
    StylistFirstTimeBookDiscount,
    StylistEarlyRebookDiscount,
    StylistService,
    StylistWeekdayDiscount,
)


@pytest.fixture
def stylist_data() -> Stylist:
    salon = G(
        Salon,
        name='Test salon', address='2000 Rilma Lane', city='Los Altos', state='CA',
        zip_code='94022', latitude=37.4009997, longitude=-122.1185007
    )

    stylist_user = G(
        User,
        is_staff=False, is_superuser=False, email='test_stylist@example.com',
        first_name='Fred', last_name='McBob', phone='(650) 350-1111',
        role=USER_ROLE.stylist,
    )
    stylist = G(
        Stylist,
        salon=salon, user=stylist_user,
        work_start_at=datetime.time(8, 0), work_end_at=datetime.time(15, 0),
    )

    return stylist


class TestStylistSerializer(object):
    @pytest.mark.django_db
    def test_stylist_serializer_representation(self, stylist_data: Stylist):
        serializer = StylistSerializer(instance=stylist_data)
        data = serializer.data
        assert(data['first_name'] == 'Fred' and data['last_name'] == 'McBob')
        assert(data['salon_name'] == 'Test salon')
        assert(data['id'] == stylist_data.id)

    @pytest.mark.django_db
    def test_stylist_serializer_update(self, stylist_data: Stylist):
        data = {
            'first_name': 'Jane',
            'last_name': 'McBob',
            'phone': '(650) 350-1111',
            'salon_name': 'Janes beauty',
            'salon_address': '1234 Front Street',
            # TODO: uncomment below lines when we enable address splitting
            # 'salon_city': 'Menlo Park',
            # 'salon_zipcode': '12345',
            # 'salon_state': 'CA',
        }
        serializer = StylistSerializer(
            instance=stylist_data, data=data, context={'user': stylist_data.user}
        )
        serializer.is_valid(raise_exception=True)
        stylist = serializer.save()
        assert(stylist.user.first_name == 'Jane')
        assert(stylist.salon.name == 'Janes beauty')

    @pytest.mark.django_db
    def test_stylist_create(self):
        user: User = G(
            User,
            email='stylist@example.com',
            role=USER_ROLE.stylist,
        )
        assert(user.is_stylist() is True)
        data = {
            'first_name': 'Jane',
            'last_name': 'McBob',
            'phone': '(650) 350-1111',
            'salon_name': 'Test salon',
            'salon_address': '1234 Front Street',
            # TODO: uncomment below lines when we enable address splitting
            # 'salon_city': 'Menlo Park',
            # 'salon_zipcode': '12345',
            # 'salon_state': 'CA',
        }
        serializer = StylistSerializer(data=data, context={'user': user})
        serializer.is_valid(raise_exception=True)
        stylist: Stylist = serializer.save()
        assert(stylist is not None)
        assert(stylist.user.id == user.id)
        assert(stylist.salon.name == 'Test salon')
        assert(stylist.salon.timezone == pytz.timezone('America/New_York'))
        assert(stylist.user.first_name == 'Jane')


class TestStylistServiceSerializer(object):
    @pytest.mark.django_db
    def test_create(self):
        stylist = G(Stylist)
        data = [
            {
                'name': 'service 1',
                'duration_minutes': 10,
                'base_price': 20,
                'is_enabled': True
            }
        ]
        serializer = StylistServiceSerializer(
            data=data,
            context={'stylist': stylist},
            many=True
        )
        assert(serializer.is_valid(raise_exception=True))

        serializer.save()
        assert(StylistService.objects.count() == 1)
        service = StylistService.objects.last()
        assert(service.name == 'service 1')
        assert(service.duration == datetime.timedelta(minutes=10))
        assert(service.base_price == 20)

    @pytest.mark.django_db
    def test_update(self):
        stylist = G(Stylist)
        stylist_service = G(
            StylistService,
            stylist=stylist,
            name='old name',
            duration=datetime.timedelta(0),
            base_price=10,
            is_enabled=True,
            deleted_at=None
        )
        data = [
            {
                'id': stylist_service.id,
                'name': 'new name',
                'duration_minutes': 10,
                'base_price': 20,
                'is_enabled': True
            }
        ]
        serializer = StylistServiceSerializer(
            data=data,
            context={'stylist': stylist},
            many=True
        )
        assert (serializer.is_valid(raise_exception=True))

        serializer.save()
        assert (StylistService.objects.count() == 1)
        service = StylistService.objects.last()
        assert (service.name == 'new name')
        assert (service.duration == datetime.timedelta(minutes=10))
        assert (service.base_price == 20)


class TestStylistProfileCompletenessSerializer(object):
    @pytest.mark.django_db
    def test_completed_profile(self, stylist_data: Stylist):
        user = stylist_data.user
        assert(
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_personal_data'] is True
        )
        user.first_name = ''
        user.last_name = ''
        user.phone = ''
        user.save()
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_personal_data'] is False
        )
        user.phone = '12345'
        user.save()
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_personal_data'] is False
        )
        user.first_name = 'Fred'
        user.save()
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_personal_data'] is True
        )
        salon = stylist_data.salon
        salon.address = ''
        salon.save()
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_personal_data'] is False
        )

    @pytest.mark.django_db
    def test_profile_picture(self, stylist_data: Stylist):
        user = stylist_data.user
        user.photo = None
        user.save()
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_picture_set'] is False
        )
        user.photo = 'http://example.com/1.jpg'
        user.save()
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_picture_set'] is True
        )

    @pytest.mark.django_db
    def test_services_set(self, stylist_data: Stylist):
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_services_set'] is False
        )
        G(StylistService, stylist=stylist_data, duration=datetime.timedelta(0))
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_services_set'] is True
        )

    @pytest.mark.django_db
    def test_business_hours_set(self, stylist_data: Stylist):
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_business_hours_set'] is False
        )
        G(StylistAvailableDay, stylist=stylist_data)
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_business_hours_set'] is True
        )

    @pytest.mark.django_db
    def test_weekday_discounts_set(self, stylist_data: Stylist):
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_weekday_discounts_set'] is False
        )
        G(StylistWeekdayDiscount, stylist=stylist_data)
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_weekday_discounts_set'] is True
        )

    @pytest.mark.django_db
    def test_other_discounts_set(self, stylist_data: Stylist):
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_other_discounts_set'] is False
        )
        discount = G(
            StylistEarlyRebookDiscount,
            stylist=stylist_data, minrebook_interval=datetime.timedelta(0)
        )
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_other_discounts_set'] is True
        )
        discount.delete()
        discount = G(StylistFirstTimeBookDiscount, stylist=stylist_data)
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_other_discounts_set'] is True
        )
        discount.delete()
        discount = G(
            StylistDateRangeDiscount, stylist=stylist_data,
            dates=DateRange(datetime.date(2018, 4, 8), datetime.date(2018, 4, 10))
        )
        assert (
            StylistProfileStatusSerializer(
                instance=stylist_data).data['has_other_discounts_set'] is True
        )
