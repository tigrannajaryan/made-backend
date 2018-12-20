from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Appointment, AppointmentService


class AppointmentServiceAdminForm(forms.ModelForm):
    class Meta:
        model = AppointmentService
        fields = '__all__'

    def clean_service_uuid(self):
        service_uuid = self.cleaned_data.get('service_uuid')
        appointment = self.cleaned_data.get('appointment')
        if not appointment.stylist.services.filter(
                uuid=service_uuid
        ).exists():
            raise forms.ValidationError(
                "Appointment's service_uuid must match `uuid` "
                "of any of the stylist's services"
            )
        return service_uuid


class AppointmentAdmin(admin.ModelAdmin):
    search_fields = [
        'stylist__user__first_name', 'stylist__user__last_name', 'stylist__user__phone',
        'client__user__first_name', 'client__user__last_name', 'client__user__phone',
    ]

    def created(self, obj):
        return obj.created_at.strftime('%b %d, %Y')

    def in_client_cal(self, obj) -> bool:
        return bool(obj.client_google_calendar_id)
    in_client_cal.boolean = True  # type: ignore
    in_client_cal.admin_order_field = 'client_google_calendar_id'  # type: ignore

    def in_stylist_cal(self, obj) -> bool:
        return bool(obj.stylist_google_calendar_id)
    in_stylist_cal.boolean = True  # type: ignore
    in_stylist_cal.admin_order_field = 'stylist_google_calendar_id'  # type: ignore

    def notification_sent(self, obj) -> bool:
        return bool(obj.stylist_new_appointment_notification)
    notification_sent.boolean = True  # type: ignore
    notification_sent.admin_order_field = 'stylist_new_appointment_notification'  # type: ignore

    def services(self, obj):
        try:
            service_names = format_html(
                '<br />'.join([s.service_name for s in obj.services.all()]))
        except KeyError:
            service_names = ''
        return service_names

    readonly_fields = [
        'deleted_at', 'deleted_by', 'created_at', 'created_by',
    ]
    list_display = [
        'created', 'stylist', 'client', 'services', 'datetime_start_at', 'status',
        'in_client_cal', 'in_stylist_cal', 'notification_sent',
    ]
    list_display_links = ['created', 'stylist', 'client']
    raw_id_fields = ['stylist', 'client', ]

    class Meta:
        model = Appointment

    def get_form(self, request, *args, **kwargs):
        form = super(AppointmentAdmin, self).get_form(request, *args, **kwargs)
        form.current_user = request.user
        return form


class AppointmentServiceAdmin(admin.ModelAdmin):
    form = AppointmentServiceAdminForm

    class Meta:
        model = AppointmentService


admin.site.register(Appointment, AppointmentAdmin)
admin.site.register(AppointmentService, AppointmentServiceAdmin)
