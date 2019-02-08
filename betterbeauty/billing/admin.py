from django.contrib import admin

from billing.models import Charge, PaymentMethod


class ChargeAdmin(admin.ModelAdmin):
    search_fields = [
        'client__user__first_name', 'client__user__last_name', 'client__user__phone',
        'stripe_id', 'payment_method__stripe_id'
    ]
    list_display = [
        'client', 'amount', 'created_at', 'charged_at', 'status', 'appointment'
    ]
    raw_id_fields = ['appointment', 'client', ]
    list_filter = ['status', ]


class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['client', 'is_active', 'card_brand', ]
    search_fields = [
        'client__user__first_name', 'client__user__last_name', 'client__user__phone',
        'last_four_digits', 'stripe_id',
    ]
    raw_id_fields = ['client', ]
    list_filter = ['is_active', ]


admin.site.register(Charge, ChargeAdmin)
admin.site.register(PaymentMethod, PaymentMethodAdmin)
