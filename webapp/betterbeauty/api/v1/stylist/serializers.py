from rest_framework import serializers

from salon.models import Salon, Stylist


class SalonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Salon
        fields = ['id', 'name', 'get_full_address']


class StylistSerializer(serializers.ModelSerializer):
    salon = SalonSerializer(read_only=True)

    class Meta:
        model = Stylist
        fields = ['id', 'first_name', 'last_name', 'salon', ]
