from rest_framework import permissions


class StylistRegisterUpdatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method.lower() == 'post':
            return True
        return request.user.is_stylist()


class StylistUpdatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_stylist()
