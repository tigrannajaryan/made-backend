from rest_framework import permissions


class StylistRegisterUpdatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method.lower() in ['post', 'put']:
            return True
        return request.user.is_authenticated and request.user.is_stylist()


class StylistPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_stylist()
