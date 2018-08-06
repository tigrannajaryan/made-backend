from typing import NamedTuple, Optional

import googlemaps

from django.conf import settings
from django.contrib.gis.geos import Point


class GeoCodedAddress(NamedTuple):
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    location: Optional[Point]


def geo_code(full_address: str):
    if not settings.IS_GEOCODING_ENABLED:
        return None
    gmaps = googlemaps.Client(key=settings.GOOGLE_GEOCODING_API_KEY)
    geocode_results = gmaps.geocode(
        address=full_address, region='us', components={'country': 'US'})
    if len(geocode_results) != 1:
        return None
    geocode_result = geocode_results[0]
    if 'country' in geocode_result['types'] or (
            'partial_match' in geocode_result and geocode_result['partial_match']):
        # Since we are filtering by US, if address is not found, US itself comes as the result.
        # So returning None if that happens.
        return None
    address_components = geocode_result['address_components']
    # city is either returned in 'locality' or 'sublocality_level_1'
    city = next((item['short_name'] for item in address_components
                 if 'locality' in item["types"]),
                next((item['short_name']
                      for item in address_components
                      if 'sublocality_level_1' in item["types"]), None))
    state = next((item['short_name']
                  for item in address_components
                  if 'administrative_area_level_1' in item["types"]), None)
    zip_code = next((item['short_name']
                     for item in address_components if 'postal_code' in item["types"]), None)
    lat = geocode_result['geometry']['location']['lat']
    lng = geocode_result['geometry']['location']['lng']

    location = Point(x=lng, y=lat)

    return GeoCodedAddress(
        city=city,
        state=state,
        zip_code=zip_code,
        lat=lat,
        lng=lng,
        location=location
    )
