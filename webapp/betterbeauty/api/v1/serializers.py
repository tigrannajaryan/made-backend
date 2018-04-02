from rest_framework import serializers


class TestSerializer(serializers.Serializer):
    foo = serializers.CharField(max_length=16)
    bar = serializers.IntegerField()
