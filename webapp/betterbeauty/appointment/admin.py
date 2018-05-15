from django.contrib import admin

from .models import Appointment


class AppointmentAdmin(admin.ModelAdmin):
    readonly_fields = [
        'deleted_at', 'deleted_by', 'status_updated_by', 'status_updated_at',
    ]

    class Meta:
        model = Appointment


admin.site.register(Appointment, AppointmentAdmin)
