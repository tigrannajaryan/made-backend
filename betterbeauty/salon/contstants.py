import datetime

DEFAULT_SERVICE_GAP_TIME_MINUTES = 30

NINE_AM = datetime.time(9, 0, 0)

TWELVE_PM = datetime.time(12, 0, 0)

FIVE_PM = datetime.time(17, 0, 0)

SEVEN_PM = datetime.time(19, 0, 0)

DEFAULT_WORKING_HOURS = {
    1: (TWELVE_PM, SEVEN_PM, True),
    2: (None, None, False),
    3: (TWELVE_PM, SEVEN_PM, True),
    4: (TWELVE_PM, SEVEN_PM, True),
    5: (TWELVE_PM, SEVEN_PM, True),
    6: (NINE_AM, FIVE_PM, True),
    7: (NINE_AM, FIVE_PM, True)
}
