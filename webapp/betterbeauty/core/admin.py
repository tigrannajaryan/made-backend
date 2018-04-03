from django.contrib import admin

from core.models import User


class UserAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'email', 'is_staff', 'is_superuser',
                    'is_active',)
    list_filter = ('is_staff', 'is_superuser', 'is_active', )
    search_fields = ('email', 'first_name', 'last_name', )


admin.site.register(User, UserAdmin)
