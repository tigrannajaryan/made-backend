import datetime

from rest_framework import fields


class DurationMinuteField(fields.DurationField):

    def to_representation(self, value: datetime.timedelta):
        return int(value.total_seconds() / 60)

    def to_internal_value(self, value: int):
        return datetime.timedelta(minutes=value)
