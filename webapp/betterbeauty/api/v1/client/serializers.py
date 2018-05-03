from rest_framework import serializers

from client.models import Client


class ClientSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    phone = serializers.CharField(source='user.phone')

    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'phone', 'id', ]
