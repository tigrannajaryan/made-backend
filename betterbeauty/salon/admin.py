import datetime

from django import forms
from django.contrib import admin

from .models import (
    Invitation,
    Salon,
    ServiceCategory,
    ServiceTemplate,
    ServiceTemplateSet,
    Speciality,
    Stylist,
    StylistAvailableWeekDay,
    StylistService,
    StylistServicePhotoSample,
    StylistWeekdayDiscount,
)


class ServiceTemplateAdmin(admin.ModelAdmin):
    # TODO: decide on filter/search fields
    list_filter = ['templateset__name', 'category', ]
    list_display = ['name', 'category', 'templateset', 'regular_price', 'duration', ]
    search_fields = ['name', 'description', ]


class ServiceTemplateSetAdmin(admin.ModelAdmin):
    search_fields = ['name', 'description', 'templates__name', 'templates__description', ]
    list_display = ['name', 'sort_weight', ]


class SalonAdmin(admin.ModelAdmin):
    search_fields = ['name', 'address', 'stylist__user__first_name', 'stylist__user__last_name',
                     'stylist__user__phone']
    list_display = ['name', 'address']


class StylistAvailableDayForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(StylistAvailableDayForm, self).__init__(*args, **kwargs)
        self.fields['work_start_at'].required = False
        self.fields['work_end_at'].required = False

    class Meta:
        model = StylistAvailableWeekDay
        fields = ['weekday', 'work_start_at', 'work_end_at', 'is_available', ]

    def clean(self):
        cleaned_data = super(StylistAvailableDayForm, self).clean()
        is_available: bool = cleaned_data.get('is_available')
        form_errors = {}
        if is_available:
            work_start_at: datetime.time = cleaned_data.get('work_start_at', None)
            work_end_at: datetime.time = cleaned_data.get('work_end_at', None)
            if not work_start_at:
                form_errors.update(
                    {'work_start_at': 'Day is set to available, so start time is required'}
                )
            if not work_end_at:
                form_errors.update(
                    {'work_end_at': 'Day is set to available, so end time is required'})
            if work_start_at and work_end_at and work_start_at > work_end_at:
                form_errors.update(
                    {'work_end_at': 'End time cannot be before start time'}
                )
        if form_errors:
            raise forms.ValidationError(form_errors)
        return cleaned_data


class StylistAdmin(admin.ModelAdmin):
    search_fields = ['user__first_name', 'user__last_name',
                     'user__phone']
    list_display = ['__str__', 'user_name', 'user_phone']
    raw_id_fields = ['user', 'salon']

    def user_phone(self, obj):
        return obj.user.phone

    def user_name(self, obj):
        return obj.user.get_full_name()

    class StylistAvailableDayInline(admin.TabularInline):
        model = StylistAvailableWeekDay
        extra = 1
        form = StylistAvailableDayForm

    class StylistWeekdayDiscount(admin.StackedInline):
        model = StylistWeekdayDiscount
        extra = 0

    class StylistServiceInline(admin.StackedInline):
        model = StylistService
        extra = 0
        readonly_fields = ['deleted_at', 'uuid', ]
        # TODO: add custom form here, to add photo samples

        def get_queryset(self, request):
            return super(StylistAdmin.StylistServiceInline, self).get_queryset(
                request).select_related('stylist__user', 'category')

    class StylistServicePhotosampleInline(admin.TabularInline):
        model = StylistServicePhotoSample
        extra = 0

    fieldsets = (
        (None, {'fields': ('user', 'salon', 'deactivated_at', 'specialities')}),
        ('Discounts', {'fields': ('first_time_book_discount_percent',
                                  'rebook_within_1_week_discount_percent',
                                  'rebook_within_2_weeks_discount_percent',
                                  'rebook_within_3_weeks_discount_percent',
                                  'rebook_within_4_weeks_discount_percent',
                                  'is_discount_configured')
                       }
         ),
    )

    inlines = [
        StylistWeekdayDiscount,
        StylistAvailableDayInline,
        StylistServiceInline,
    ]


class InvitationAdmin(admin.ModelAdmin):
    list_display = [
        'stylist', 'phone', 'created_client', 'status', 'accepted_at',
    ]
    list_filter = ['status', ]
    readonly_fields = ['delivered_at', 'accepted_at', 'created_client', ]
    search_fields = [
        'phone', 'stylist__user__first_name', 'stylist__user__last_name',
        'created_client__user__first_name', 'created_client__user__last_name',
    ]


admin.site.register(Invitation, InvitationAdmin)
admin.site.register(Salon, SalonAdmin)
admin.site.register(ServiceCategory)
admin.site.register(Speciality)
admin.site.register(ServiceTemplate, ServiceTemplateAdmin)
admin.site.register(ServiceTemplateSet, ServiceTemplateSetAdmin)
admin.site.register(Stylist, StylistAdmin)
