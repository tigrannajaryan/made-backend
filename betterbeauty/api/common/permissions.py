import os

from django.conf import settings
from rest_framework import permissions

from core.constants import EnvLevel


class StylistRegisterUpdatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method.lower() in ['post', 'put']:
            return True
        return request.user.is_authenticated and request.user.is_stylist()


class StylistPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_stylist()


class ClientPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_client()


class BackdoorPermission(permissions.BasePermission):
    @staticmethod
    def _get_backdoor_api_key():
        key = os.environ.get('BACKDOOR_API_KEY', '').strip()
        if len(key) < 20:
            return None
        return key

    @staticmethod
    def _get_header_api_key(request):
        auth = request.META.get('HTTP_AUTHORIZATION', '').split()
        if not auth or auth[0].lower() != 'secret' or len(auth) != 2:
            return None
        return auth[1]

    def has_permission(self, request, view):
        if settings.LEVEL not in [EnvLevel.STAGING, EnvLevel.TESTS]:
            return False
        api_key = self._get_backdoor_api_key()
        header_key = self._get_header_api_key(request)

        return all([
            api_key,
            header_key,
            header_key == api_key
        ])
