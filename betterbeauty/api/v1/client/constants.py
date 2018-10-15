from django.contrib.gis.geos import Point

NEW_YORK_LOCATION: Point = Point((-74.0060, 40.7128))


class ErrorMessages:
    ERR_STYLIST_IS_ALREADY_IN_PREFERENCE = "err_stylist_is_already_in_preference"
    ERR_INVALID_STYLIST_UUID = "err_invalid_stylist_uuid"
    ERR_UNIQUE_CLIENT_EMAIL = "err_unique_client_email"
    ERR_PRIVACY_SETTING_PRIVATE = "err_privacy_setting_private"
