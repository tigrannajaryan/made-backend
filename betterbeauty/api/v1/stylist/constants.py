MAX_SERVICE_TEMPLATE_PREVIEW_COUNT = 50

MAX_APPOINTMENTS_PER_REQUEST = 100


class ErrorMessages:
    UNIQUE_STYLIST_PHONE = ('The phone number is registered to another stylist.'
                            'Please contact us if you have any questions')
    UNIQUE_CLIENT_PHONE = 'The phone number belongs to existing client'
    UNIQUE_CLIENT_NAME = 'A client with the name already exists'
    INVALID_QUERY_FOR_HOME = "Query should be one of 'upcoming', 'past' or 'today'"
