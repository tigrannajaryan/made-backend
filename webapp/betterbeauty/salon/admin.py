from django.contrib import admin

from .models import (
    Salon,
    ServiceTemplate,
    Stylist,
    StylistAvailableDay,
    StylistDateRangeDiscount,
    StylistEarlyRebookDiscount,
    StylistFirstTimeBookDiscount,
    StylistService,
    StylistServicePhotoSample,
    StylistWeekdayDiscount,
)


class ServiceTemplateAdmin(admin.ModelAdmin):
    # TODO: decide on filter/search fields
    pass


class SalonAdmin(admin.ModelAdmin):
    # TODO: decide on filter/search fields
    pass


class StylistAdmin(admin.ModelAdmin):
    class StylistFirstTimeBookDiscountInline(admin.StackedInline):
        model = StylistFirstTimeBookDiscount
        extra = 1

    class StylistDateRangeDiscountInline(admin.StackedInline):
        model = StylistDateRangeDiscount
        extra = 0

    class StylistEarlyRebookDiscount(admin.StackedInline):
        model = StylistEarlyRebookDiscount
        extra = 0

    class StylistAvailableDayInline(admin.TabularInline):
        model = StylistAvailableDay
        extra = 1

    class StylistWeekdayDiscount(admin.StackedInline):
        model = StylistWeekdayDiscount
        extra = 0

    class StylistServiceInline(admin.StackedInline):
        model = StylistService
        extra = 0
        # TODO: add custom form here, to add photo samples

    class StylistServicePhotosampleInline(admin.TabularInline):
        model = StylistServicePhotoSample
        extra = 0

    inlines = [
        StylistFirstTimeBookDiscountInline,
        StylistDateRangeDiscountInline,
        StylistEarlyRebookDiscount,
        StylistWeekdayDiscount,
        StylistAvailableDayInline,
        StylistServiceInline,
    ]


admin.site.register(Salon, SalonAdmin)
admin.site.register(ServiceTemplate, ServiceTemplateAdmin)
admin.site.register(Stylist, StylistAdmin)
