import logging

import requests
from django.conf import settings
from django.contrib.gis.geos import Point

from api.v1.client.constants import NEW_YORK_LOCATION


logger = logging.getLogger(__name__)


def get_lat_lng_for_ip_address(ip_addr: str) -> Point:

    api_address = 'http://api.ipstack.com/{0}?access_key={1}'.format(
        ip_addr, settings.IPSTACK_API_KEY)
    try:
        response = requests.get(api_address)
    except requests.RequestException as e:
        logger.exception(str(e))
        return NEW_YORK_LOCATION
    json_response = response.json()
    latitude = json_response.get('latitude', None)
    longitude = json_response.get('longitude', None)
    if latitude and longitude:
        return Point((longitude, latitude))
    else:
        return NEW_YORK_LOCATION
