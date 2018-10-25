import json
import logging

from typing import NamedTuple, Optional

import googlemaps

from django.conf import settings
from django.contrib.gis.geos import Point

from api.v1.stylist.constants import MIN_VALID_ADDR_LEN

logger = logging.getLogger(__name__)


class GeoCodedAddress(NamedTuple):
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    location: Optional[Point]
    country: Optional[str]


class GeoCode:

    def __init__(self, str_to_geocode):
        self.str_to_geocode = str_to_geocode

    def is_geocodable_string(self):
        if self.str_to_geocode:
            return True
        return False

    def geo_code(self, country=None):
        if not settings.IS_GEOCODING_ENABLED:
            return None
        if not self.is_geocodable_string():
            return None
        gmaps = googlemaps.Client(key=settings.GOOGLE_GEOCODING_API_KEY)
        if country:
            logger.info("Geocoding in country {0}".format(country))
            geocode_results = gmaps.geocode(
                address=self.str_to_geocode, components={'country': country})
        else:
            geocode_results = gmaps.geocode(
                address=self.str_to_geocode)
        logger.info("Geocoding result: {0}".format(json.dumps(geocode_results)))
        if len(geocode_results) != 1:
            return None
        geocode_result = geocode_results[0]
        if 'country' in geocode_result['types'] or (
                'partial_match' in geocode_result and geocode_result['partial_match']):
            return None
        address_components = geocode_result['address_components']
        # address_components is a list of dicts with type containing array of types.
        locality = None
        sublocality_level_1 = None
        country = None
        zip_code = None
        state = None
        # We iterate the address_components to find the specific items that matches required type.
        for item in address_components:
            if 'locality' in item["types"]:
                locality = item['short_name']
            if 'sublocality_level_1' in item["types"]:
                sublocality_level_1 = item['short_name']
            if 'country' in item["types"]:
                country = item['short_name']
            if 'postal_code' in item["types"]:
                zip_code = item['short_name']
            if 'administrative_area_level_1' in item['types']:
                state = item['short_name']
        # city is either returned in 'locality' or 'sublocality_level_1'
        city = locality if locality else sublocality_level_1
        if not (country and city):
            return None
        lat = geocode_result['geometry']['location']['lat']
        lng = geocode_result['geometry']['location']['lng']

        location = Point(x=lng, y=lat)

        return GeoCodedAddress(
            city=city,
            state=state,
            zip_code=zip_code,
            lat=lat,
            lng=lng,
            location=location,
            country=country
        )


class GeocodeValidAddress(GeoCode):

    def is_geocodable_string(self):
        if len(self.str_to_geocode) < MIN_VALID_ADDR_LEN:
            return False
        return True
